# hotspot_api/views.py - COMPLETE FIXED VERSION WITH AUTO VOUCHER CREATION

from django.shortcuts import render
from django.views.generic import ListView
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction as db_transaction

from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

import json
import urllib.request
import urllib.parse
import urllib.error
import base64
import random
from datetime import datetime, timedelta
from decimal import Decimal

from .models import (
    Voucher, MpesaTransaction, AccessPoint,
    Device, UsageData, HotspotCustomer, HotspotPlan,
    generate_account_no, OTP
)

from .serializers import (
    UserSerializer, AccessPointSerializer, DeviceSerializer,
    UsageDataSerializer, VoucherSerializer, HotspotPlanSerializer,
    MpesaTransactionSerializer
)

from .sms_utils import send_otp_sms, send_voucher_sms, send_payment_confirmation_sms


# -----------------------------------------------------------------
# --- REST Framework ViewSets (API Endpoints)
# -----------------------------------------------------------------

class HotspotPlanViewSet(viewsets.ModelViewSet):
    queryset = HotspotPlan.objects.filter(is_active=True).order_by('price', 'validity_minutes')
    serializer_class = HotspotPlanSerializer


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class AccessPointViewSet(viewsets.ModelViewSet):
    queryset = AccessPoint.objects.all()
    serializer_class = AccessPointSerializer


class DeviceViewSet(viewsets.ModelViewSet):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer


class UsageDataViewSet(viewsets.ModelViewSet):
    queryset = UsageData.objects.all()
    serializer_class = UsageDataSerializer


class VoucherViewSet(viewsets.ModelViewSet):
    queryset = Voucher.objects.all()
    serializer_class = VoucherSerializer


class MpesaTransactionViewSet(viewsets.ModelViewSet):
    queryset = MpesaTransaction.objects.all()
    serializer_class = MpesaTransactionSerializer


# -----------------------------------------------------------------
# --- Dashboard Pages
# -----------------------------------------------------------------

class TransactionListView(ListView):
    model = MpesaTransaction
    template_name = 'hotspot_api/transaction_list.html'
    context_object_name = 'transactions'

    def get_queryset(self):
        return MpesaTransaction.objects.all().order_by('-created_at')


class HotspotPlanListView(ListView):
    model = HotspotPlan
    template_name = 'hotspot_api/plan_list.html'
    context_object_name = 'plans'

    def get_queryset(self):
        return HotspotPlan.objects.filter(is_active=True).order_by('price', 'validity_minutes')


class CustomerListView(ListView):
    model = HotspotCustomer
    template_name = 'hotspot_api/customer_list.html'
    context_object_name = 'customers'

    def get_queryset(self):
        return HotspotCustomer.objects.all().order_by('-joined')


def dashboard_view(request):
    return render(request, 'hotspot_api/dashboard.html')


# -----------------------------------------------------------------
# --- ADMIN DASHBOARD WITH SPARKLINES
# -----------------------------------------------------------------

@staff_member_required
def admin_dashboard(request):
    """Custom admin dashboard showing revenue statistics and customer metrics"""
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)
    
    cleanup_expired_transactions()
    
    # Customer Stats
    total_customers = HotspotCustomer.objects.count()
    customers_today = HotspotCustomer.objects.filter(joined__gte=today_start).count()
    customers_this_week = HotspotCustomer.objects.filter(joined__gte=week_start).count()
    customers_this_month = HotspotCustomer.objects.filter(joined__gte=month_start).count()
    active_customers = HotspotCustomer.objects.filter(is_active=True).count()
    
    # Revenue Stats
    total_revenue = MpesaTransaction.objects.filter(status='COMPLETED').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    revenue_today = MpesaTransaction.objects.filter(status='COMPLETED', created_at__gte=today_start).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    revenue_this_week = MpesaTransaction.objects.filter(status='COMPLETED', created_at__gte=week_start).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    revenue_this_month = MpesaTransaction.objects.filter(status='COMPLETED', created_at__gte=month_start).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Transaction Stats
    total_transactions = MpesaTransaction.objects.count()
    completed_transactions = MpesaTransaction.objects.filter(status='COMPLETED').count()
    pending_transactions = MpesaTransaction.objects.filter(status='PENDING').count()
    failed_transactions = MpesaTransaction.objects.filter(status='FAILED').count()
    
    # Voucher Stats
    total_vouchers = Voucher.objects.count()
    active_vouchers = Voucher.objects.filter(is_active=True, used_at__isnull=True).count()
    used_vouchers = Voucher.objects.filter(used_at__isnull=False).count()
    vouchers_created_today = Voucher.objects.filter(created_at__gte=today_start).count()
    
    # Access Point Stats
    total_access_points = AccessPoint.objects.count()
    online_access_points = AccessPoint.objects.filter(is_online=True).count()
    
    # Recent Transactions
    recent_transactions = MpesaTransaction.objects.select_related('voucher').order_by('-created_at')[:10]
    
    # Revenue Trend (last 7 days)
    revenue_trend = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        daily_revenue = MpesaTransaction.objects.filter(
            status='COMPLETED', 
            created_at__gte=day_start, 
            created_at__lt=day_end
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        revenue_trend.append({'date': day.strftime('%b %d'), 'amount': float(daily_revenue)})
    
    # Customer Trend (last 7 days)
    customer_trend = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        daily_customers = HotspotCustomer.objects.filter(
            joined__gte=day_start, 
            joined__lt=day_end
        ).count()
        customer_trend.append({'date': day.strftime('%b %d'), 'count': daily_customers})
    
    # Transactions Trend (last 7 days)
    transactions_trend = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        daily_transactions = MpesaTransaction.objects.filter(
            created_at__gte=day_start, 
            created_at__lt=day_end
        ).count()
        transactions_trend.append({'date': day.strftime('%b %d'), 'count': daily_transactions})
    
    # Vouchers Trend (last 7 days)
    vouchers_trend = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        daily_vouchers = Voucher.objects.filter(
            created_at__gte=day_start, 
            created_at__lt=day_end
        ).count()
        vouchers_trend.append({'date': day.strftime('%b %d'), 'count': daily_vouchers})
    
    context = {
        'total_customers': total_customers, 
        'customers_today': customers_today,
        'customers_this_week': customers_this_week, 
        'customers_this_month': customers_this_month,
        'active_customers': active_customers, 
        'total_revenue': total_revenue,
        'revenue_today': revenue_today, 
        'revenue_this_week': revenue_this_week,
        'revenue_this_month': revenue_this_month, 
        'total_transactions': total_transactions,
        'completed_transactions': completed_transactions, 
        'pending_transactions': pending_transactions,
        'failed_transactions': failed_transactions, 
        'total_vouchers': total_vouchers,
        'active_vouchers': active_vouchers, 
        'used_vouchers': used_vouchers,
        'vouchers_created_today': vouchers_created_today, 
        'total_access_points': total_access_points,
        'online_access_points': online_access_points, 
        'recent_transactions': recent_transactions,
        'revenue_trend': revenue_trend, 
        'customer_trend': customer_trend,
        'transactions_trend': transactions_trend,
        'vouchers_trend': vouchers_trend,
    }
    
    return render(request, 'hotspot_api/dashboard.html', context)


def cleanup_expired_transactions():
    """Mark pending transactions older than 10 minutes as FAILED"""
    expiry_time = timezone.now() - timedelta(minutes=10)
    expired_count = MpesaTransaction.objects.filter(
        status='PENDING',
        created_at__lt=expiry_time
    ).update(status='FAILED')
    
    if expired_count > 0:
        print(f"✅ Cleaned up {expired_count} expired pending transactions")
    
    return expired_count


# -----------------------------------------------------------------
# --- OTP & Voucher APIs (keeping your existing code)
# -----------------------------------------------------------------

@api_view(['POST'])
def send_otp(request):
    phone_number = request.data.get("phone_number")
    if not phone_number:
        return JsonResponse({"success": False, "message": "Phone number is required"}, status=400)

    if phone_number.startswith('0'):
        phone_number = '254' + phone_number[1:]
    elif not phone_number.startswith('254'):
        phone_number = '254' + phone_number

    vouchers = Voucher.objects.filter(phone_number=phone_number, is_active=True)
    
    if not vouchers.exists():
        return JsonResponse({"success": False, "message": "No vouchers found for this phone number"}, status=404)

    otp_code = str(random.randint(100000, 999999))
    OTP.objects.create(phone_number=phone_number, code=otp_code)
    cache.set(f'otp_{phone_number}', otp_code, timeout=300)

    sms_result = send_otp_sms(phone_number, otp_code)
    
    if sms_result['success']:
        print(f"✅ OTP sent via SMS to {phone_number}: {otp_code}")
    else:
        print(f"❌ SMS failed: {sms_result['message']}")

    return JsonResponse({"success": True, "message": "OTP sent successfully", "vouchers_count": vouchers.count()})


@api_view(['POST'])
def verify_otp(request):
    phone_number = request.data.get("phone_number")
    code = request.data.get("code")

    if not phone_number or not code:
        return JsonResponse({"success": False, "message": "Phone number and OTP are required"}, status=400)

    if phone_number.startswith('0'):
        phone_number = '254' + phone_number[1:]
    elif not phone_number.startswith('254'):
        phone_number = '254' + phone_number

    cached_otp = cache.get(f'otp_{phone_number}')
    
    if cached_otp and cached_otp == code:
        cache.delete(f'otp_{phone_number}')
        cache.set(f'verified_{phone_number}', True, timeout=600)
        
        # ✅ FIXED: Removed 'status' field that doesn't exist
        vouchers = Voucher.objects.filter(phone_number=phone_number, is_active=True).values(
            'code', 'plan_name', 'data_limit_mb', 'expiry_date', 'used_at', 'is_active'
        )
        
        return JsonResponse({"success": True, "message": "OTP verified successfully", "vouchers": list(vouchers)})
    
    try:
        otp = OTP.objects.filter(phone_number=phone_number, code=code, is_verified=False).latest('created_at')
        
        if otp.is_expired():
            return JsonResponse({"success": False, "message": "OTP expired. Please request a new one."}, status=400)
        
        otp.is_verified = True
        otp.save()
        cache.set(f'verified_{phone_number}', True, timeout=600)
        
        # ✅ FIXED: Removed 'status' field that doesn't exist
        vouchers = Voucher.objects.filter(phone_number=phone_number, is_active=True).values(
            'code', 'plan_name', 'data_limit_mb', 'expiry_date', 'used_at', 'is_active'
        )
        
        return JsonResponse({"success": True, "message": "OTP verified successfully", "vouchers": list(vouchers)})
        
    except OTP.DoesNotExist:
        return JsonResponse({"success": False, "message": "Invalid OTP"}, status=400)


@api_view(['POST'])
def lookup_voucher(request):
    phone_number = request.data.get("phone_number")

    if not phone_number:
        return JsonResponse({"success": False, "message": "Phone number is required"}, status=400)

    if phone_number.startswith('0'):
        phone_number = '254' + phone_number[1:]
    elif not phone_number.startswith('254'):
        phone_number = '254' + phone_number

    vouchers = Voucher.objects.filter(phone_number=phone_number, is_active=True)
    
    if not vouchers.exists():
        return JsonResponse({"success": False, "message": "No active vouchers found for this number"}, status=404)

    otp_code = str(random.randint(100000, 999999))
    OTP.objects.create(phone_number=phone_number, code=otp_code)
    cache.set(f'otp_{phone_number}', otp_code, timeout=300)

    sms_result = send_otp_sms(phone_number, otp_code)
    
    if sms_result['success']:
        print(f"✅ Lookup OTP sent via SMS to {phone_number}: {otp_code}")
    else:
        print(f"❌ SMS failed: {sms_result['message']}")

    return JsonResponse({"success": True, "message": "OTP sent to your phone", "vouchers_count": vouchers.count()})


@api_view(['POST'])
def enter_voucher(request):
    phone_number = request.data.get("phone_number")
    voucher_code = request.data.get("voucher_code")

    if not phone_number or not voucher_code:
        return JsonResponse({"success": False, "message": "Phone number and voucher code are required"}, status=400)

    if phone_number.startswith('0'):
        phone_number = '254' + phone_number[1:]
    elif not phone_number.startswith('254'):
        phone_number = '254' + phone_number

    try:
        voucher = Voucher.objects.get(code=voucher_code)
        
        if voucher.used_at:
            return JsonResponse({"success": False, "message": "This voucher has already been used"}, status=400)
        
        if voucher.expiry_date and voucher.expiry_date < timezone.now():
            return JsonResponse({"success": False, "message": "This voucher has expired"}, status=400)
        
        if not voucher.phone_number:
            voucher.phone_number = phone_number
            voucher.save()
        
        if voucher.phone_number != phone_number:
            return JsonResponse({"success": False, "message": "This voucher is assigned to a different phone number"}, status=403)
        
        otp_code = str(random.randint(100000, 999999))
        OTP.objects.create(phone_number=phone_number, code=otp_code)
        cache.set(f'voucher_otp_{phone_number}_{voucher_code}', otp_code, timeout=300)
        
        sms_result = send_otp_sms(phone_number, otp_code)
        
        if sms_result['success']:
            print(f"✅ Voucher OTP sent via SMS to {phone_number}: {otp_code}")
        else:
            print(f"❌ SMS failed: {sms_result['message']}")
        
        return JsonResponse({
            "success": True,
            "message": "OTP sent for voucher activation",
            "voucher_details": {
                "code": voucher.code,
                "plan": voucher.plan_name,
                "data_limit": f"{voucher.data_limit_mb}MB" if voucher.data_limit_mb else "Unlimited",
                "expiry": voucher.expiry_date.strftime('%Y-%m-%d %H:%M') if voucher.expiry_date else None
            }
        })
        
    except Voucher.DoesNotExist:
        return JsonResponse({"success": False, "message": "Invalid voucher code"}, status=404)


@api_view(['POST'])
def activate_voucher(request):
    phone_number = request.data.get("phone_number")
    voucher_code = request.data.get("voucher_code")
    otp = request.data.get("otp")
    mac_address = request.data.get("mac_address")

    if not all([phone_number, voucher_code, otp]):
        return JsonResponse({"success": False, "message": "Phone number, voucher code, and OTP are required"}, status=400)

    if phone_number.startswith('0'):
        phone_number = '254' + phone_number[1:]
    elif not phone_number.startswith('254'):
        phone_number = '254' + phone_number

    cached_otp = cache.get(f'voucher_otp_{phone_number}_{voucher_code}')
    
    if not cached_otp or cached_otp != otp:
        return JsonResponse({"success": False, "message": "Invalid or expired OTP"}, status=400)

    try:
        voucher = Voucher.objects.get(code=voucher_code, phone_number=phone_number)
        
        voucher.used_at = timezone.now()
        voucher.last_activity = timezone.now()
        
        if mac_address:
            voucher.mac_address = mac_address
            voucher.used_by_device = mac_address
        
        voucher.save()
        cache.delete(f'voucher_otp_{phone_number}_{voucher_code}')
        
        return JsonResponse({
            "success": True,
            "message": "Voucher activated successfully!",
            "session_details": {
                "data_limit": f"{voucher.data_limit_mb}MB" if voucher.data_limit_mb else "Unlimited",
                "valid_until": voucher.expiry_date.strftime('%Y-%m-%d %H:%M') if voucher.expiry_date else None,
                "plan": voucher.plan_name
            }
        })
        
    except Voucher.DoesNotExist:
        return JsonResponse({"success": False, "message": "Voucher not found"}, status=404)


# -----------------------------------------------------------------
# --- M-PESA INTEGRATION WITH AUTO VOUCHER CREATION
# -----------------------------------------------------------------

@api_view(['POST'])
def initiate_mpesa_payment(request):
    try:
        data = json.loads(request.body)
        phone_number = data.get('phone_number', '').strip()
        amount = data.get('amount', 0)
        plan_name = data.get('plan', 'Hotspot Plan')
        
        print("=" * 80)
        print(f"🔄 INITIATING M-PESA PAYMENT")
        print(f"📱 Phone: {phone_number}")
        print(f"💰 Amount: {amount}")
        print(f"📦 Plan: {plan_name}")
        print(f"🕐 Time: {timezone.now()}")
        print("=" * 80)
        
        if not phone_number or not amount:
            return JsonResponse({'success': False, 'message': 'Phone number and amount are required'})
        
        if phone_number.startswith('0'):
            phone_number = '254' + phone_number[1:]
        elif phone_number.startswith('+254'):
            phone_number = phone_number[1:]
        elif not phone_number.startswith('254'):
            phone_number = '254' + phone_number
            
        print(f"📱 Formatted phone: {phone_number}")
        
        auth_url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
        stk_push_url = 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
        
        consumer_key = settings.MPESA_CONSUMER_KEY
        consumer_secret = settings.MPESA_CONSUMER_SECRET
        
        print(f"🔑 Consumer Key: {consumer_key[:10]}...")
        
        credentials = base64.b64encode(f"{consumer_key}:{consumer_secret}".encode()).decode()
        auth_request = urllib.request.Request(auth_url, headers={'Authorization': f'Basic {credentials}'})
        
        print("🔑 Requesting M-Pesa access token...")
        try:
            with urllib.request.urlopen(auth_request) as auth_response:
                auth_data = json.loads(auth_response.read().decode())
                access_token = auth_data.get('access_token')
                print(f"✅ Access token obtained")
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            print(f"❌ Auth failed: {e.code}")
            return JsonResponse({'success': False, 'message': 'Failed to get M-Pesa access token'})
        
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        business_shortcode = settings.MPESA_BUSINESS_SHORTCODE
        passkey = settings.MPESA_PASSKEY
        callback_url = settings.MPESA_CALLBACK_URL
        
        print(f"🔗 Callback URL: {callback_url}")
        
        password_string = f"{business_shortcode}{passkey}{timestamp}"
        password = base64.b64encode(password_string.encode()).decode()
        
        stk_payload = {
            "BusinessShortCode": business_shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": phone_number,
            "PartyB": business_shortcode,
            "PhoneNumber": phone_number,
            "CallBackURL": callback_url,
            "AccountReference": f"Hotspot-{plan_name}",
            "TransactionDesc": f"Payment for {plan_name}"
        }
        
        print("📤 Sending STK Push...")
        stk_data = json.dumps(stk_payload).encode('utf-8')
        stk_request = urllib.request.Request(stk_push_url, data=stk_data,
            headers={'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'})
        
        try:
            with urllib.request.urlopen(stk_request) as stk_response:
                response_data = json.loads(stk_response.read().decode())
                print(f"📥 STK Response: {response_data.get('ResponseCode')}")
                
                if response_data.get('ResponseCode') == '0':
                    try:
                        transaction = MpesaTransaction.objects.create(
                            checkout_request_id=response_data.get('CheckoutRequestID', ''),
                            merchant_request_id=response_data.get('MerchantRequestID', ''),
                            phone_number=phone_number,
                            amount=amount,
                            status='PENDING',
                            account_reference=f"Hotspot-{plan_name}",
                            transaction_desc=f"Payment for {plan_name}"
                        )
                        print(f"✅ Transaction saved: CheckoutID={transaction.checkout_request_id}")
                        print("⏳ Waiting for M-Pesa callback...")
                    except Exception as db_error:
                        print(f"❌ DB save error: {db_error}")
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'STK Push sent! Check your phone.',
                        'transactionId': response_data.get('CheckoutRequestID'),
                        'customerMessage': response_data.get('CustomerMessage')
                    })
                else:
                    return JsonResponse({'success': False, 'message': response_data.get('errorMessage', 'STK Push failed')})
                    
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            print(f"❌ STK Push failed: {e.code}")
            return JsonResponse({'success': False, 'message': f'Payment failed: HTTP {e.code}'})
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': f'Payment failed: {str(e)}'})


@csrf_exempt
@api_view(['POST'])
def mpesa_callback(request):
    """
    ⚡ CRITICAL: This handles M-Pesa payment callbacks
    This is called by M-Pesa servers when payment is completed
    """
    try:
        callback_data = json.loads(request.body)
        print("=" * 80)
        print(f"📞 M-PESA CALLBACK RECEIVED at {timezone.now()}")
        print(json.dumps(callback_data, indent=2))
        print("=" * 80)
        
        stk_callback = callback_data.get('Body', {}).get('stkCallback', {})
        result_code = stk_callback.get('ResultCode')
        checkout_request_id = stk_callback.get('CheckoutRequestID')
        merchant_request_id = stk_callback.get('MerchantRequestID')
        result_desc = stk_callback.get('ResultDesc', '')
        
        print(f"🔍 Result Code: {result_code}")
        print(f"🔍 Checkout ID: {checkout_request_id}")
        
        if result_code == 0:
            # ✅ PAYMENT SUCCESS
            callback_metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])
            transaction_details = {item.get('Name'): item.get('Value') for item in callback_metadata}
            
            mpesa_receipt_number = transaction_details.get('MpesaReceiptNumber', '')
            amount = transaction_details.get('Amount', 0)
            phone_number = str(transaction_details.get('PhoneNumber', ''))
            
            print("✅ PAYMENT SUCCESS!")
            print(f"   📧 Receipt: {mpesa_receipt_number}")
            print(f"   💰 Amount: {amount}")
            print(f"   📱 Phone: {phone_number}")
            
            # Use database transaction to ensure atomicity
            with db_transaction.atomic():
                try:
                    # Find the transaction
                    mpesa_txn = MpesaTransaction.objects.select_for_update().filter(
                        checkout_request_id=checkout_request_id
                    ).first()
                    
                    if not mpesa_txn:
                        print(f"⚠️ Transaction NOT FOUND for: {checkout_request_id}")
                        return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted but transaction not found'})
                    
                    # Update transaction
                    mpesa_txn.status = 'COMPLETED'
                    mpesa_txn.mpesa_receipt_number = mpesa_receipt_number
                    mpesa_txn.transaction_id = mpesa_receipt_number
                    mpesa_txn.merchant_request_id = merchant_request_id
                    if amount:
                        mpesa_txn.amount = Decimal(str(amount))
                    mpesa_txn.save()
                    
                    print(f"✅ Transaction updated: {mpesa_txn.id}")
                    
                    # ⚡ AUTO CREATE VOUCHER
                    if not mpesa_txn.voucher:
                        print("🎟️ Creating voucher automatically...")
                        voucher = create_voucher_for_transaction(mpesa_txn)
                        
                        if voucher:
                            mpesa_txn.voucher = voucher
                            mpesa_txn.save()
                            print(f"✅ Voucher created: {voucher.code}")
                            print(f"✅ Voucher linked to transaction!")
                        else:
                            print(f"❌ VOUCHER CREATION FAILED!")
                            # Log to help debug
                            print(f"   Transaction ID: {mpesa_txn.id}")
                            print(f"   Amount: {mpesa_txn.amount}")
                            print(f"   Phone: {mpesa_txn.phone_number}")
                    else:
                        print(f"✅ Voucher already exists: {mpesa_txn.voucher.code}")
                    
                except Exception as db_error:
                    print(f"❌ DB Error: {db_error}")
                    import traceback
                    traceback.print_exc()
                    # Re-raise to rollback transaction
                    raise
                    
        else:
            # ❌ PAYMENT FAILED
            print("❌ PAYMENT FAILED!")
            print(f"   Code: {result_code}")
            print(f"   Desc: {result_desc}")
            
            try:
                mpesa_txn = MpesaTransaction.objects.filter(
                    checkout_request_id=checkout_request_id
                ).first()
                
                if mpesa_txn:
                    mpesa_txn.status = 'FAILED'
                    mpesa_txn.merchant_request_id = merchant_request_id
                    mpesa_txn.save()
                    print(f"✅ Marked as FAILED")
                    
            except Exception as e:
                print(f"❌ Error marking failed: {e}")
        
        print("=" * 80)
        return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})
        
    except Exception as e:
        print(f"❌ CALLBACK ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Failed'})


def create_voucher_for_transaction(transaction):
    """
    ⚡ AUTO CREATE VOUCHER for completed M-Pesa transaction
    Returns voucher object or None
    """
    try:
        print(f"🎫 Starting voucher creation for transaction {transaction.id}")
        
        # Check if voucher already exists
        existing = Voucher.objects.filter(
            created_by_transaction=transaction.checkout_request_id
        ).first()
        
        if existing:
            print(f"⚠️ Voucher already exists: {existing.code}")
            return existing
        
        # Generate unique code
        max_attempts = 10
        voucher_code = None
        
        for attempt in range(max_attempts):
            code = generate_account_no(length=12)
            if not Voucher.objects.filter(code=code).exists():
                voucher_code = code
                break
        
        if not voucher_code:
            print(f"❌ Failed to generate unique voucher code after {max_attempts} attempts")
            return None
        
        print(f"✅ Generated code: {voucher_code}")
        
        # Get plan details based on amount
        amount = float(transaction.amount)
        print(f"💰 Amount: {amount} KSh")
        
        plan_mapping = {
            1.0: {'data_limit_mb': 50, 'validity_hours': 1, 'description': '50MB Test'},
            10.0: {'data_limit_mb': None, 'validity_hours': 24 * 365, 'description': 'Unlimited'},
            50.0: {'data_limit_mb': 1024, 'validity_hours': 24, 'description': '1GB Daily'},
            100.0: {'data_limit_mb': 2048, 'validity_hours': 24 * 3, 'description': '2GB - 3 Days'},
            200.0: {'data_limit_mb': 5120, 'validity_hours': 24 * 7, 'description': '5GB Weekly'},
            500.0: {'data_limit_mb': 15360, 'validity_hours': 24 * 30, 'description': '15GB Monthly'},
        }
        
        plan_details = plan_mapping.get(amount)
        
        if not plan_details:
            print(f"⚠️ No exact plan match for {amount} KSh, using default")
            plan_details = {
                'data_limit_mb': int(amount * 10),  # 10MB per KSh
                'validity_hours': 24,
                'description': f'Custom Plan - {amount} KSh'
            }
        
        print(f"📦 Plan: {plan_details['description']}")
        print(f"💾 Data: {plan_details['data_limit_mb']}MB" if plan_details['data_limit_mb'] else "💾 Data: Unlimited")
        print(f"⏰ Valid: {plan_details['validity_hours']} hours")
        
        # Calculate expiry
        expiry_date = timezone.now() + timedelta(hours=plan_details['validity_hours'])
        print(f"📅 Expires: {expiry_date}")
        
        # Create voucher
        voucher = Voucher.objects.create(
            code=voucher_code,
            plan_name=plan_details['description'],
            data_limit_mb=plan_details['data_limit_mb'],
            expiry_date=expiry_date,
            validity_hours=plan_details['validity_hours'],
            is_active=True,
            created_by_transaction=transaction.checkout_request_id,
            phone_number=transaction.phone_number,
            description=plan_details['description']
        )
        
        print(f"✅ VOUCHER CREATED SUCCESSFULLY!")
        print(f"   Code: {voucher.code}")
        print(f"   ID: {voucher.id}")
        print(f"   Phone: {voucher.phone_number}")
        
        # Send SMS
        try:
            sms_result = send_payment_confirmation_sms(
                transaction.phone_number,
                amount,
                voucher_code,
                plan_details['description']
            )
            
            if sms_result and sms_result.get('success'):
                print(f"✅ SMS sent successfully")
            else:
                print(f"⚠️ SMS failed: {sms_result.get('message', 'Unknown error')}")
        except Exception as sms_error:
            print(f"⚠️ SMS error (non-critical): {sms_error}")
        
        return voucher
        
    except Exception as e:
        print(f"❌ VOUCHER CREATION ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


# -----------------------------------------------------------------
# --- M-PESA WEBHOOK HEALTH CHECK
# -----------------------------------------------------------------

@csrf_exempt
def mpesa_webhook_health(request):
    """Health check for M-Pesa webhook"""
    return JsonResponse({
        'status': 'ok',
        'timestamp': timezone.now().isoformat(),
        'message': 'M-Pesa webhook is reachable',
        'callback_url': settings.MPESA_CALLBACK_URL
    })


# -----------------------------------------------------------------
# --- Other API Endpoints
# -----------------------------------------------------------------

@api_view(['GET'])
def usage_data_chart(request):
    return JsonResponse({'message': 'Chart data endpoint.'})


@api_view(['GET'])
def check_balance(request):
    return JsonResponse({'message': 'Check balance endpoint.'})


@api_view(['POST'])
def login_voucher(request):
    return JsonResponse({'message': 'Voucher login endpoint.'})


@api_view(['POST'])
def create_voucher(request):
    return JsonResponse({'message': 'Voucher creation endpoint.'})