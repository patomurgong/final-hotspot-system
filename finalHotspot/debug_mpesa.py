# Save this as debug_mpesa.py in your project root
# Run with: python debug_mpesa.py

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'finalHotspot.settings')
django.setup()

from django.conf import settings
from django.urls import get_resolver

print("=" * 80)
print("🔍 M-PESA CONFIGURATION CHECK")
print("=" * 80)

# Check settings
print("\n📋 Settings Configuration:")
print(f"MPESA_CALLBACK_URL: {settings.MPESA_CALLBACK_URL}")
print(f"MPESA_CONSUMER_KEY: {settings.MPESA_CONSUMER_KEY[:20]}...")
print(f"MPESA_BUSINESS_SHORTCODE: {settings.MPESA_BUSINESS_SHORTCODE}")

# Check URL patterns
print("\n🔗 Registered URL Patterns:")
resolver = get_resolver()

def show_urls(urllist, depth=0):
    for entry in urllist:
        if hasattr(entry, 'url_patterns'):
            print("  " * depth + f"📁 {entry.pattern}")
            show_urls(entry.url_patterns, depth + 1)
        else:
            print("  " * depth + f"📄 {entry.pattern} -> {entry.callback.__name__ if hasattr(entry, 'callback') else 'N/A'}")

show_urls(resolver.url_patterns)

print("\n" + "=" * 80)
print("✅ CHECK COMPLETE")
print("=" * 80)
print("\n⚠️ Make sure:")
print("1. MPESA_CALLBACK_URL matches one of the URL patterns above")
print("2. Django has been RESTARTED after code changes")
print("3. ngrok is pointing to the correct port (8002)")
print("=" * 80)