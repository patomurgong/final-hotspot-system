"""
hotspot_api/kopa_views.py
─────────────────────────────────────────────────────
All endpoints for the Kopa (data-borrowing) feature.

Endpoints
---------
POST /api/kopa/check/           — eligibility + outstanding balance
POST /api/kopa/request/         — initiate borrow (send OTP)
POST /api/kopa/confirm/         — verify OTP → create voucher
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
    KopaTransaction, Voucher, MpesaTransaction,
    OTP, generate_account_no
)
from .sms_utils import send_otp_sms, send_voucher_sms


# ─────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────

# Each package: data_mb, principal_ksh, fee_ksh
KOPA_PACKAGES = {
    10:  {'data_mb': 50,   'fee': 2,  'label': '50MB'},
    20:  {'data_mb': 100,  'fee': 3,  'label': '100MB'},
    50:  {'data_mb': 250,  'fee': 5,  'label': '250MB'},
}

# Kopa limit per customer spend tier
def _get_kopa_limit(phone_number):
    """
    Returns how much (Ksh) a customer is allowed to borrow.
    Based on their total completed payment history.
    """
    total_spent = MpesaTransaction.objects.filter(
        phone_number=phone_number, status='COMPLETED'
    ).aggregate(total=__import__('django.db.models', fromlist=['Sum']).Sum('amount'))['total'] or 0

    total_spent = float(total_spent)
    if total_spent >= 500:
        return 50   # up to 50MB package
    elif total_spent >= 200:
        return 20   # up to 100MB package
    elif total_spent >= 50:
        return 10   # up to 50MB package
    return 0        # not eligible


def _normalize_phone(phone):
    if phone.startswith('0'):
        return '254' + phone[1:]
    elif phone.startswith('+254'):
        return phone[1:]
    elif not phone.startswith('254'):
        return '254' + phone
    return phone


# ─────────────────────────────────────────────────────
# 1. CHECK  —  GET eligibility & outstanding balance
# ─────────────────────────────────────────────────────

@api_view(['POST'])
def kopa_check(request):
    """
    Returns:
        outstanding_amount  – total Ksh owed (0 if none)
        kopa_status         – 'ACTIVE' | 'CLEAR'
        kopa_limit          – max Ksh the customer can borrow
        eligible            – bool
        packages            – list of available packages
    """
    phone = request.data.get('phone_number', '').strip()
    if not phone:
        return JsonResponse({'success': False, 'message': 'Phone number is required'}, status=400)

    phone = _normalize_phone(phone)

    # Check for any active (unpaid) Kopa
    active_kopa = KopaTransaction.objects.filter(
        phone_number=phone, status='ACTIVE'
    ).first()

    outstanding = float(active_kopa.total_owed) if active_kopa else 0
    kopa_status = 'ACTIVE' if active_kopa else 'CLEAR'

    kopa_limit = _get_kopa_limit(phone)
    eligible   = kopa_limit > 0 and not active_kopa

    # Filter packages to those within the limit
    available_packages = [
        {
            'amount':  amt,
            'data_mb': pkg['data_mb'],
            'fee':     pkg['fee'],
            'label':   pkg['label'],
            'total':   amt + pkg['fee'],
        }
        for amt, pkg in KOPA_PACKAGES.items()
        if amt <= kopa_limit
    ]

    return JsonResponse({
        'success':            True,
        'outstanding_amount': outstanding,
        'kopa_status':        kopa_status,
        'kopa_limit':         kopa_limit,
        'eligible':           eligible,
        'packages':           available_packages,
        'message':            'Active Kopa found — repay before borrowing again.' if active_kopa
                              else 'You are eligible to Kopa.' if eligible
                              else 'Spend at least 50 Ksh to unlock Kopa.',
    })


# ─────────────────────────────────────────────────────
# 2. REQUEST  —  Initiate borrow → send OTP
# ─────────────────────────────────────────────────────

@api_view(['POST'])
def kopa_request(request):
    """
    Validates eligibility, creates a PENDING KopaTransaction, sends OTP.
    """
    phone  = request.data.get('phone_number', '').strip()
    amount = request.data.get('amount', 0)

    if not phone:
        return JsonResponse({'success': False, 'message': 'Phone number is required'}, status=400)

    try:
        amount = int(amount)
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'message': 'Invalid amount'}, status=400)

    if amount not in KOPA_PACKAGES:
        return JsonResponse({'success': False, 'message': 'Invalid Kopa package selected'}, status=400)

    phone = _normalize_phone(phone)
    pkg   = KOPA_PACKAGES[amount]

    # 1. Check for existing active Kopa
    if KopaTransaction.objects.filter(phone_number=phone, status='ACTIVE').exists():
        return JsonResponse({
            'success': False,
            'message': 'You have an unpaid Kopa balance. Please repay before borrowing again.'
        }, status=400)

    # 2. Eligibility
    kopa_limit = _get_kopa_limit(phone)
    if kopa_limit == 0:
        return JsonResponse({
            'success': False,
            'message': 'You are not yet eligible for Kopa. Spend at least 50 Ksh first.'
        }, status=403)

    if amount > kopa_limit:
        return JsonResponse({
            'success': False,
            'message': f'You can only borrow up to {kopa_limit} Ksh worth of data.'
        }, status=403)

    # 3. Expire any stale PENDING kopas
    KopaTransaction.objects.filter(
        phone_number=phone,
        status='PENDING',
        created_at__lt=timezone.now() - timedelta(minutes=10)
    ).update(status='EXPIRED')

    # 4. Create PENDING Kopa record
    kopa = KopaTransaction.objects.create(
        phone_number=phone,
        amount_ksh=Decimal(str(amount)),
        fee_ksh=Decimal(str(pkg['fee'])),
        data_mb=pkg['data_mb'],
        status='PENDING',
    )

    # 5. Generate and cache OTP
    otp_code = str(random.randint(100000, 999999))
    OTP.objects.create(phone_number=phone, code=otp_code)
    cache.set(f'kopa_otp_{phone}', otp_code, timeout=300)
    cache.set(f'kopa_pending_id_{phone}', kopa.id, timeout=300)

    # 6. Send SMS
    sms_result = send_otp_sms(phone, otp_code)
    if sms_result.get('success'):
        print(f"✅ Kopa OTP sent to {phone}: {otp_code}")
    else:
        print(f"❌ Kopa OTP SMS failed: {sms_result.get('message')}")

    return JsonResponse({
        'success': True,
        'message': 'OTP sent. Enter it to confirm your Kopa.',
        'kopa_id': kopa.id,
        'data_mb': pkg['data_mb'],
        'label':   pkg['label'],
        'total_owed': amount + pkg['fee'],
    })


# ─────────────────────────────────────────────────────
# 3. CONFIRM  —  Verify OTP → activate voucher
# ─────────────────────────────────────────────────────

@api_view(['POST'])
def kopa_confirm(request):
    """
    Verifies OTP, activates the PENDING KopaTransaction,
    creates a Voucher, and sends the voucher code via SMS.
    """
    phone  = request.data.get('phone_number', '').strip()
    otp    = request.data.get('otp', '').strip()
    amount = request.data.get('amount', 0)

    if not phone or not otp:
        return JsonResponse({'success': False, 'message': 'Phone and OTP are required'}, status=400)

    phone = _normalize_phone(phone)

    # 1. Verify OTP
    cached_otp = cache.get(f'kopa_otp_{phone}')
    if not cached_otp or cached_otp != otp:
        # Fallback: check DB
        try:
            otp_obj = OTP.objects.filter(
                phone_number=phone, code=otp, is_verified=False
            ).latest('created_at')
            if otp_obj.is_expired():
                return JsonResponse({'success': False, 'message': 'OTP expired. Please try again.'}, status=400)
            otp_obj.is_verified = True
            otp_obj.save()
        except OTP.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Invalid OTP'}, status=400)

    cache.delete(f'kopa_otp_{phone}')

    # 2. Find the PENDING kopa
    kopa_id = cache.get(f'kopa_pending_id_{phone}')
    kopa    = None
    if kopa_id:
        kopa = KopaTransaction.objects.filter(id=kopa_id, status='PENDING').first()
    if not kopa:
        # Fallback: find most recent pending
        kopa = KopaTransaction.objects.filter(phone_number=phone, status='PENDING').order_by('-created_at').first()
    if not kopa:
        return JsonResponse({'success': False, 'message': 'No pending Kopa request found. Please start again.'}, status=404)

    # 3. Create voucher + activate kopa atomically
    with db_transaction.atomic():
        # Generate unique voucher code
        voucher_code = None
        for _ in range(10):
            code = generate_account_no(length=12)
            if not Voucher.objects.filter(code=code).exists():
                voucher_code = code
                break

        if not voucher_code:
            return JsonResponse({'success': False, 'message': 'Could not generate voucher. Try again.'}, status=500)

        expiry = timezone.now() + timedelta(hours=24)
        voucher = Voucher.objects.create(
            code=voucher_code,
            plan_name=f'Kopa {kopa.data_mb}MB',
            data_limit_mb=kopa.data_mb,
            expiry_date=expiry,
            validity_hours=24,
            is_active=True,
            phone_number=phone,
            description=f'Kopa voucher — repay {float(kopa.total_owed)} Ksh',
        )

        kopa.status       = 'ACTIVE'
        kopa.confirmed_at = timezone.now()
        kopa.voucher      = voucher
        kopa.save()

    cache.delete(f'kopa_pending_id_{phone}')

    # 4. Send SMS
    phone_local = f"0{phone[3:]}" if phone.startswith('254') else phone
    try:
        send_voucher_sms(
            phone,
            float(kopa.amount_ksh),
            voucher_code,
            f'Kopa {kopa.data_mb}MB'
        )
        # Also send repayment reminder
        from .sms_utils import send_sms
        send_sms(
            phone,
            f"KiRePa Wi-Fi: Your Kopa voucher is {voucher_code} ({kopa.data_mb}MB). "
            f"You owe {float(kopa.total_owed)} Ksh — this will be deducted automatically on your next purchase. "
            f"Call 0792701147 for help."
        )
    except Exception as e:
        print(f"⚠️ Kopa SMS error (non-critical): {e}")

    return JsonResponse({
        'success': True,
        'message': f'Kopa confirmed! Your {kopa.data_mb}MB voucher is ready.',
        'voucher_code': voucher_code,
        'data_mb':      kopa.data_mb,
        'total_owed':   float(kopa.total_owed),
        'expires':      expiry.strftime('%Y-%m-%d %H:%M'),
    })