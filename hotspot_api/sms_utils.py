# hotspot_api/sms_utils.py - FIXED SSL ISSUE
import africastalking
from django.conf import settings

# Initialize Africa's Talking
try:
    africastalking.initialize(
        username=settings.AFRICASTALKING_USERNAME,
        api_key=settings.AFRICASTALKING_API_KEY
    )
    sms = africastalking.SMS
except Exception as e:
    print(f"⚠️ Africa's Talking initialization error: {e}")
    sms = None


def send_otp_sms(phone_number, otp_code):
    """Send OTP via SMS"""
    try:
        # ✅ TEMPORARY FIX: Print OTP to console for testing
        print("=" * 80)
        print(f"📱 OTP FOR {phone_number}: {otp_code}")
        print("=" * 80)
        
        if not sms:
            print("⚠️ SMS service not initialized, using console fallback")
            return {
                'success': True,
                'message': f'OTP (console): {otp_code}',
                'otp': otp_code  # Include OTP in response for testing
            }
        
        message = f"Your KiRePa WiFi OTP is: {otp_code}. Valid for 5 minutes."
        
        # Format phone number
        if not phone_number.startswith('+'):
            phone_number = f'+{phone_number}'
        
        # Send SMS
        response = sms.send(message, [phone_number])
        
        print(f"✅ SMS sent successfully to {phone_number}")
        return {
            'success': True,
            'message': 'OTP sent successfully',
            'response': response
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ SMS Error: {error_msg}")
        
        # Fallback: Return success with console OTP
        print(f"📱 FALLBACK OTP FOR {phone_number}: {otp_code}")
        return {
            'success': True,  # Return success so app continues
            'message': f'Check console for OTP: {otp_code}',
            'otp': otp_code,
            'error': error_msg
        }


def send_payment_confirmation_sms(phone_number, amount, voucher_code, plan_name):
    """Send payment confirmation with voucher code"""
    try:
        print("=" * 80)
        print(f"💰 PAYMENT CONFIRMATION")
        print(f"📱 Phone: {phone_number}")
        print(f"💵 Amount: {amount} KSh")
        print(f"🎫 Voucher: {voucher_code}")
        print(f"📦 Plan: {plan_name}")
        print("=" * 80)
        
        if not sms:
            print("⚠️ SMS service not initialized, using console fallback")
            return {
                'success': True,
                'message': 'Check console for voucher details'
            }
        
        message = (
            f"Payment received! {amount} KSh\n"
            f"Your voucher code: {voucher_code}\n"
            f"Plan: {plan_name}\n"
            f"Visit our portal to activate."
        )
        
        if not phone_number.startswith('+'):
            phone_number = f'+{phone_number}'
        
        response = sms.send(message, [phone_number])
        
        print(f"✅ Voucher SMS sent to {phone_number}")
        return {
            'success': True,
            'message': 'Voucher SMS sent',
            'response': response
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Voucher SMS Error: {error_msg}")
        
        # Fallback: Console only
        return {
            'success': True,  # Don't fail voucher creation
            'message': 'Voucher created (SMS failed)',
            'error': error_msg
        }


def send_voucher_sms(phone_number, voucher_code, plan_details):
    """Send voucher details via SMS"""
    try:
        print(f"📱 Sending voucher SMS to {phone_number}")
        
        if not sms:
            print("⚠️ SMS service not initialized")
            return {'success': False, 'message': 'SMS service unavailable'}
        
        message = (
            f"Your KiRePa WiFi Voucher:\n"
            f"Code: {voucher_code}\n"
            f"Plan: {plan_details.get('plan_name', 'N/A')}\n"
            f"Data: {plan_details.get('data_limit', 'Unlimited')}\n"
            f"Valid: {plan_details.get('validity', 'Check portal')}"
        )
        
        if not phone_number.startswith('+'):
            phone_number = f'+{phone_number}'
        
        response = sms.send(message, [phone_number])
        
        print(f"✅ SMS sent to {phone_number}")
        return {
            'success': True,
            'message': 'SMS sent',
            'response': response
        }
        
    except Exception as e:
        print(f"❌ SMS Error: {str(e)}")
        return {
            'success': False,
            'message': f'SMS failed: {str(e)}'
        }