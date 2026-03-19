import json, urllib.request, urllib.parse, urllib.error, ssl
from django.conf import settings

AT_USERNAME  = getattr(settings, 'AFRICASTALKING_USERNAME', 'sandbox')
AT_API_KEY   = getattr(settings, 'AFRICASTALKING_API_KEY', '')
AT_SENDER_ID = getattr(settings, 'AFRICASTALKING_SENDER_ID', 'KIREPA')
IS_SANDBOX   = AT_USERNAME == 'sandbox'
AT_SMS_URL   = 'http://api.sandbox.africastalking.com/version1/messaging' if IS_SANDBOX else 'https://api.africastalking.com/version1/messaging'

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode    = ssl.CERT_NONE

def send_sms(phone_number, message):
    if not phone_number.startswith('+'): phone_number = f'+{phone_number}'
    print(f"📤 SMS → {phone_number} | URL: {AT_SMS_URL}")
    payload = {'username': AT_USERNAME, 'to': phone_number, 'message': message}
    if not IS_SANDBOX and AT_SENDER_ID: payload['from'] = AT_SENDER_ID
    data = urllib.parse.urlencode(payload).encode('utf-8')
    headers = {'apiKey': AT_API_KEY, 'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'}
    req = urllib.request.Request(AT_SMS_URL, data=data, headers=headers, method='POST')
    try:
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=_SSL_CTX)) if AT_SMS_URL.startswith('https') else urllib.request.build_opener()
        with opener.open(req, timeout=15) as resp:
            raw = resp.read().decode('utf-8').strip()
        print(f"📥 AT raw: {raw[:300]}")
        if not raw or raw.startswith('<'):
            return {'success': True, 'message': 'Queued'}
        result = json.loads(raw)
        recipients = result.get('SMSMessageData', {}).get('Recipients', [])
        if recipients and recipients[0].get('statusCode') in (100, 101, 102):
            print(f"✅ SMS sent to {phone_number}")
            return {'success': True, 'message': 'Sent'}
        return {'success': False, 'message': result.get('SMSMessageData', {}).get('Message', str(result))}
    except Exception as e:
        print(f"❌ SMS Error: {e}")
        return {'success': False, 'message': str(e)}

def send_otp_sms(phone_number, otp_code):
    print(f"{'='*80}\n📱 OTP FOR {phone_number}: {otp_code}\n{'='*80}")
    result = send_sms(phone_number, f"Your KiRePa Wi-Fi OTP is: {otp_code}. Valid for 5 minutes.")
    if not result['success']:
        print(f"📱 FALLBACK OTP FOR {phone_number}: {otp_code}")
    return {'success': True, 'message': 'OTP ready', 'otp': otp_code}

def send_payment_confirmation_sms(phone_number, amount, voucher_code, plan_name):
    print(f"💰 PAYMENT | {phone_number} | Voucher: {voucher_code}")
    send_sms(phone_number, f"KiRePa Wi-Fi: Payment of {amount} KSh received!\nVoucher: {voucher_code}\nPlan: {plan_name}\nHelp: 0792701147")
    return {'success': True, 'message': 'Processed'}

def send_voucher_sms(phone_number, amount, voucher_code, plan_name):
    print(f"📱 Voucher SMS → {phone_number} | Code: {voucher_code}")
    send_sms(phone_number, f"KiRePa Wi-Fi: Your voucher is ready!\nCode: {voucher_code}\nPlan: {plan_name}\nHelp: 0792701147")
    return {'success': True, 'message': 'Processed'}
