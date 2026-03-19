"""
hotspot_api/points_views.py
─────────────────────────────────────────────────────
All endpoints for the Reward Points feature.

Earning rule:   10 Ksh spent  →  1 point  (auto-awarded on every completed M-Pesa payment)
Redeem tiers:   50 pts → 50MB free data
               100 pts → 150MB
               200 pts → 400MB
               500 pts → 1 GB

Endpoints
---------
POST /api/points/check/             — fetch balance + history
POST /api/points/redeem/            — initiate redemption (send OTP)
POST /api/points/redeem/confirm/    — verify OTP → issue free voucher
"""

from django.http import JsonResponse
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction as db_transaction

from rest_framework.decorators import api_view
from decimal import Decimal
import random
from datetime import timedelta

from .models import (
    CustomerPoints, PointsTransaction, Voucher,
    OTP, generate_account_no
)
from .sms_utils import send_otp_sms, send_voucher_sms


# ─────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────

POINTS_PER_KSH   = 10        # 10 Ksh = 1 point
MIN_REDEEM_PTS   = 50

REDEEM_TIERS = [
    {'pts': 50,   'data_mb': 50,   'label': '50MB',  'validity_hours': 6},
    {'pts': 100,  'data_mb': 150,  'label': '150MB', 'validity_hours': 12},
    {'pts': 200,  'data_mb': 400,  'label': '400MB', 'validity_hours': 24},
    {'pts': 500,  'data_mb': 1024, 'label': '1GB',   'validity_hours': 48},
]


def _normalize_phone(phone):
    if phone.startswith('0'):
        return '254' + phone[1:]
    elif phone.startswith('+254'):
        return phone[1:]
    elif not phone.startswith('254'):
        return '254' + phone
    return phone


def _find_tier(pts):
    """Return the best redeem tier that fits within pts."""
    for tier in reversed(REDEEM_TIERS):
        if pts >= tier['pts']:
            return tier
    return None


# ─────────────────────────────────────────────────────
# HELPER: award points (called from mpesa_callback)
# ─────────────────────────────────────────────────────

def award_points_for_payment(phone_number, amount_ksh, mpesa_transaction=None):
    """
    Called automatically after a successful M-Pesa payment.
    Creates / updates CustomerPoints and logs a PointsTransaction.
    Returns the number of points awarded.
    """
    try:
        pts_awarded = int(float(amount_ksh)) // POINTS_PER_KSH
        if pts_awarded <= 0:
            return 0

        cp, _ = CustomerPoints.objects.get_or_create(phone_number=phone_number)
        cp.total_points     += pts_awarded
        cp.lifetime_earned  += pts_awarded
        cp.total_spent_ksh  += Decimal(str(amount_ksh))
        cp.save(update_fields=['total_points', 'lifetime_earned', 'total_spent_ksh', 'updated_at'])

        PointsTransaction.objects.create(
            phone_number=phone_number,
            points=pts_awarded,
            transaction_type='EARN',
            description=f'Purchased data — {amount_ksh} Ksh',
            mpesa_transaction=mpesa_transaction,
        )

        print(f"⭐ Awarded {pts_awarded} points to {phone_number} (spent {amount_ksh} Ksh)")
        return pts_awarded

    except Exception as e:
        print(f"❌ Points award error: {e}")
        return 0


# ─────────────────────────────────────────────────────
# 1. CHECK  —  Fetch balance & recent history
# ─────────────────────────────────────────────────────

@api_view(['POST'])
def points_check(request):
    """
    Returns the customer's current points balance and transaction history.
    """
    phone = request.data.get('phone_number', '').strip()
    if not phone:
        return JsonResponse({'success': False, 'message': 'Phone number is required'}, status=400)

    phone = _normalize_phone(phone)

    cp = CustomerPoints.objects.filter(phone_number=phone).first()
    if not cp:
        # No transactions yet — return zero state
        return JsonResponse({
            'success':          True,
            'points':           0,
            'total_spent':      0,
            'redeemed_points':  0,
            'lifetime_earned':  0,
            'redeem_tiers':     REDEEM_TIERS,
            'recent_history':   [],
            'message':          'No points yet. Buy a plan to start earning!',
        })

    # Recent 10 transactions
    history = list(
        PointsTransaction.objects.filter(phone_number=phone)
        .order_by('-created_at')[:10]
        .values('points', 'transaction_type', 'description', 'created_at')
    )
    # Make datetimes JSON-serializable
    for h in history:
        h['created_at'] = h['created_at'].strftime('%Y-%m-%d %H:%M')

    # Annotate tiers with canRedeem flag
    tiers = []
    for t in REDEEM_TIERS:
        tiers.append({**t, 'can_redeem': cp.total_points >= t['pts']})

    return JsonResponse({
        'success':          True,
        'points':           cp.total_points,
        'total_spent':      float(cp.total_spent_ksh),
        'redeemed_points':  cp.lifetime_redeemed,
        'lifetime_earned':  cp.lifetime_earned,
        'redeem_tiers':     tiers,
        'recent_history':   history,
        'message':          'Points fetched successfully.',
    })


# ─────────────────────────────────────────────────────
# 2. REDEEM (initiate)  —  Send OTP
# ─────────────────────────────────────────────────────

@api_view(['POST'])
def points_redeem(request):
    """
    Validates the redemption request and sends an OTP for confirmation.
    """
    phone = request.data.get('phone_number', '').strip()
    pts   = request.data.get('points', 0)

    if not phone:
        return JsonResponse({'success': False, 'message': 'Phone number is required'}, status=400)

    try:
        pts = int(pts)
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'message': 'Invalid points value'}, status=400)

    phone = _normalize_phone(phone)

    # 1. Find matching tier
    tier = next((t for t in REDEEM_TIERS if t['pts'] == pts), None)
    if not tier:
        return JsonResponse({'success': False, 'message': 'Invalid redemption tier'}, status=400)

    # 2. Check balance
    cp = CustomerPoints.objects.filter(phone_number=phone).first()
    if not cp or cp.total_points < pts:
        available = cp.total_points if cp else 0
        return JsonResponse({
            'success': False,
            'message': f'Insufficient points. You have {available} pts, need {pts} pts.'
        }, status=400)

    # 3. Generate OTP
    otp_code = str(random.randint(100000, 999999))
    OTP.objects.create(phone_number=phone, code=otp_code)
    cache.set(f'redeem_otp_{phone}',  otp_code, timeout=300)
    cache.set(f'redeem_pts_{phone}',  pts,       timeout=300)

    sms_result = send_otp_sms(phone, otp_code)
    if sms_result.get('success'):
        print(f"✅ Redeem OTP sent to {phone}: {otp_code}")
    else:
        print(f"❌ Redeem OTP SMS failed: {sms_result.get('message')}")

    return JsonResponse({
        'success': True,
        'message': f'OTP sent. Confirm to redeem {pts} pts for {tier["label"]} free data.',
        'tier':    tier,
    })


# ─────────────────────────────────────────────────────
# 3. REDEEM CONFIRM  —  Verify OTP → issue voucher
# ─────────────────────────────────────────────────────

@api_view(['POST'])
def points_redeem_confirm(request):
    """
    Verifies OTP, deducts points, creates a free voucher, sends SMS.
    """
    phone = request.data.get('phone_number', '').strip()
    otp   = request.data.get('otp', '').strip()
    pts   = request.data.get('points', 0)

    if not phone or not otp:
        return JsonResponse({'success': False, 'message': 'Phone and OTP are required'}, status=400)

    try:
        pts = int(pts)
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'message': 'Invalid points value'}, status=400)

    phone = _normalize_phone(phone)

    # 1. Verify OTP
    cached_otp  = cache.get(f'redeem_otp_{phone}')
    cached_pts  = cache.get(f'redeem_pts_{phone}')

    otp_valid = cached_otp and cached_otp == otp
    if not otp_valid:
        try:
            otp_obj = OTP.objects.filter(
                phone_number=phone, code=otp, is_verified=False
            ).latest('created_at')
            if otp_obj.is_expired():
                return JsonResponse({'success': False, 'message': 'OTP expired. Please try again.'}, status=400)
            otp_obj.is_verified = True
            otp_obj.save()
            otp_valid = True
        except OTP.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Invalid OTP'}, status=400)

    cache.delete(f'redeem_otp_{phone}')
    cache.delete(f'redeem_pts_{phone}')

    # 2. Find tier
    tier = next((t for t in REDEEM_TIERS if t['pts'] == pts), None)
    if not tier:
        return JsonResponse({'success': False, 'message': 'Invalid redemption tier'}, status=400)

    # 3. Deduct points + create voucher atomically
    with db_transaction.atomic():
        cp = CustomerPoints.objects.select_for_update().filter(phone_number=phone).first()
        if not cp or cp.total_points < pts:
            available = cp.total_points if cp else 0
            return JsonResponse({
                'success': False,
                'message': f'Insufficient points ({available} available).'
            }, status=400)

        # Deduct
        cp.total_points      -= pts
        cp.lifetime_redeemed += pts
        cp.save(update_fields=['total_points', 'lifetime_redeemed', 'updated_at'])

        # Generate unique voucher code
        voucher_code = None
        for _ in range(10):
            code = generate_account_no(length=12)
            if not Voucher.objects.filter(code=code).exists():
                voucher_code = code
                break

        if not voucher_code:
            return JsonResponse({'success': False, 'message': 'Could not generate voucher. Try again.'}, status=500)

        expiry  = timezone.now() + timedelta(hours=tier['validity_hours'])
        voucher = Voucher.objects.create(
            code=voucher_code,
            plan_name=f'Reward {tier["label"]}',
            data_limit_mb=tier['data_mb'],
            expiry_date=expiry,
            validity_hours=tier['validity_hours'],
            is_active=True,
            phone_number=phone,
            description=f'Redeemed {pts} reward points',
        )

        # Log the points transaction
        PointsTransaction.objects.create(
            phone_number=phone,
            points=-pts,
            transaction_type='REDEEM',
            description=f'Redeemed {pts} pts for {tier["label"]} free data',
            voucher=voucher,
        )

    # 4. Send SMS
    try:
        from .sms_utils import send_sms
        phone_local = f"0{phone[3:]}" if phone.startswith('254') else phone
        send_sms(
            phone,
            f"KiRePa Wi-Fi: 🎉 You've redeemed {pts} points for {tier['label']} free data! "
            f"Your voucher code is {voucher_code}. "
            f"Expires: {expiry.strftime('%d %b %Y %H:%M')}. "
            f"Call 0792701147 for help."
        )
    except Exception as e:
        print(f"⚠️ Redeem SMS error (non-critical): {e}")

    return JsonResponse({
        'success':          True,
        'message':          f'🎉 {tier["label"]} free data unlocked!',
        'voucher_code':     voucher_code,
        'data_mb':          tier['data_mb'],
        'pts_used':         pts,
        'remaining_points': cp.total_points,
        'expires':          expiry.strftime('%Y-%m-%d %H:%M'),
    })