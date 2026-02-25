from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import random
import string


# Utility function to generate unique codes
def generate_account_no(length=8):
    """Generates a random string of uppercase letters and digits."""
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))


class HotspotPlan(models.Model):
    """
    Wi-Fi plans offered by the hotspot.
    Used in the 'Plan Setup' dashboard.
    """
    plan_name = models.CharField(max_length=100, unique=True, verbose_name="Plan Name")
    code = models.CharField(max_length=10, unique=True, editable=False) 
    is_unlimited = models.BooleanField(default=False, verbose_name="Unlimited") 
    data_limit_mb = models.IntegerField(default=0, help_text="Data limit in MB (0 for unlimited)")
    speed_limit = models.CharField(max_length=20, default="3M/3M", verbose_name="Upload/Download Speed") 
    validity_minutes = models.IntegerField(default=60, help_text="Time validity in minutes")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Price (Ksh)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Hotspot Plan"
        verbose_name_plural = "Hotspot Plans"
        ordering = ['price', 'validity_minutes']

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_account_no(length=7)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.plan_name} ({self.price} Ksh)"

    @property
    def data_limit_gb(self):
        if self.data_limit_mb:
            return round(self.data_limit_mb / 1024, 2)
        return None

    @property
    def validity(self):
        if self.validity_minutes >= 1440:  # 24h+
            days = self.validity_minutes // 1440
            if days == 1:
                return "24 hours"
            elif days == 7:
                return "7 days"
            elif days == 30:
                return "30 days"
            return f"{days} days"
        elif self.validity_minutes >= 60:
            return f"{self.validity_minutes // 60} hours"
        return f"{self.validity_minutes} minutes"


class Voucher(models.Model):
    """
    Voucher codes for Wi-Fi access
    """
    code = models.CharField(max_length=12, unique=True, editable=False, verbose_name="Voucher Code")
    plan_name = models.CharField(max_length=100, verbose_name="Plan Name")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    data_limit_mb = models.IntegerField(null=True, blank=True)
    expiry_date = models.DateTimeField(null=True, blank=True, verbose_name="Expires On")
    phone_number = models.CharField(max_length=15, blank=True, verbose_name="Customer Phone")
    created_by_transaction = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=200, blank=True, verbose_name="Description")
    used_at = models.DateTimeField(null=True, blank=True, verbose_name="Used At")
    used_by_device = models.CharField(max_length=17, blank=True)
    data_used_mb = models.IntegerField(default=0)
    last_activity = models.DateTimeField(null=True, blank=True, verbose_name="Last Activity")
    
    # NEW FIELDS
    mac_address = models.CharField(max_length=17, blank=True, null=True, verbose_name="MAC Address")
    validity_hours = models.IntegerField(null=True, blank=True, verbose_name="Validity (Hours)")

    class Meta:
        verbose_name = "Voucher"
        verbose_name_plural = "Vouchers"
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_account_no(length=12)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.plan_name}"

    @property
    def is_expired(self):
        return bool(self.expiry_date and timezone.now() > self.expiry_date)

    @property
    def is_used(self):
        return self.used_at is not None

    @property
    def remaining_data_mb(self):
        if self.data_limit_mb is None:  # Unlimited
            return None
        return max(0, self.data_limit_mb - self.data_used_mb)

    @property
    def status(self):
        if not self.is_active:
            return "Inactive"
        elif self.is_expired:
            return "Expired"
        elif self.is_used and self.remaining_data_mb == 0:
            return "Depleted"
        elif self.is_used:
            return "In Use"
        return "Available"
    
    @property
    def phone_formatted(self):
        """Format phone number for display"""
        if self.phone_number:
            phone = str(self.phone_number)
            if phone.startswith('254'):
                return f"0{phone[3:]}"
        return self.phone_number or "Not assigned"


class MpesaTransaction(models.Model):
    """
    Stores M-Pesa transaction details
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]

    transaction_id = models.CharField(max_length=30, unique=True, null=True, blank=True)
    phone_number = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    checkout_request_id = models.CharField(max_length=100, unique=True)
    merchant_request_id = models.CharField(max_length=100, blank=True, null=True)
    mpesa_receipt_number = models.CharField(max_length=50, blank=True, null=True)
    voucher = models.ForeignKey(Voucher, on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    account_reference = models.CharField(max_length=100, blank=True)
    transaction_desc = models.CharField(max_length=200, blank=True)
    customer_credited = models.BooleanField(default=False, help_text="True if customer expenditure has been updated.")

    class Meta:
        verbose_name = "M-Pesa Transaction"
        verbose_name_plural = "M-Pesa Transactions"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.mpesa_receipt_number or self.transaction_id or 'No ID'} - {self.phone_number}"

    @property
    def customer_phone_formatted(self):
        phone = str(self.phone_number)
        if phone.startswith('254'):
            return f"0{phone[3:]}"
        return phone

    def save(self, *args, **kwargs):
        # ✅ FIXED: Always update transaction_id if we have a receipt number
        if self.mpesa_receipt_number:
            self.transaction_id = self.mpesa_receipt_number
        
        super().save(*args, **kwargs)


class HotspotCustomer(models.Model):
    """
    Stores hotspot customer info
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    account_no = models.CharField(max_length=10, unique=True, editable=False)
    phone = models.CharField(max_length=15, unique=True)
    expenditure = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    account_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    joined = models.DateTimeField(auto_now_add=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    last_login = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Hotspot Customer"
        verbose_name_plural = "Hotspot Customers"
        ordering = ['-joined']

    def save(self, *args, **kwargs):
        if not self.account_no:
            self.account_no = generate_account_no(length=8)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.account_no} - {self.phone}"

    @property
    def phone_formatted(self):
        phone = str(self.phone)
        if phone.startswith('254'):
            return f"0{phone[3:]}"
        return phone


class AccessPoint(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField()
    ssid = models.CharField(max_length=50)
    mac_address = models.CharField(max_length=17, unique=True)
    firmware_version = models.CharField(max_length=50, blank=True)
    is_online = models.BooleanField(default=False)
    installation_date = models.DateField(auto_now_add=True)
    max_clients = models.IntegerField(default=50)
    current_clients = models.IntegerField(default=0)
    total_data_gb = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    last_reboot = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Access Point"
        verbose_name_plural = "Access Points"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.location})"

    @property
    def status_display(self):
        return "Online" if self.is_online else "Offline"

    @property
    def client_utilization_percentage(self):
        if self.max_clients > 0:
            return round((self.current_clients / self.max_clients) * 100, 1)
        return 0


class Device(models.Model):
    DEVICE_TYPE_CHOICES = [
        ('PHONE', 'Mobile Phone'),
        ('LAPTOP', 'Laptop'),
        ('TABLET', 'Tablet'),
        ('DESKTOP', 'Desktop Computer'),
        ('OTHER', 'Other Device'),
    ]

    device_name = models.CharField(max_length=100)
    mac_address = models.CharField(max_length=17, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    customer = models.ForeignKey(HotspotCustomer, on_delete=models.CASCADE, null=True, blank=True)
    device_type = models.CharField(max_length=10, choices=DEVICE_TYPE_CHOICES, default='OTHER')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    is_online = models.BooleanField(default=False)
    total_sessions = models.IntegerField(default=0)
    total_data_mb = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Device"
        verbose_name_plural = "Devices"
        ordering = ['-last_seen']

    def __str__(self):
        return f"{self.device_name} ({self.mac_address})"

    @property
    def total_data_gb(self):
        return round(self.total_data_mb / 1024, 2) if self.total_data_mb else 0


class UsageData(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    customer = models.ForeignKey(HotspotCustomer, on_delete=models.CASCADE, null=True, blank=True)
    access_point = models.ForeignKey(AccessPoint, on_delete=models.CASCADE)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, null=True, blank=True)
    voucher = models.ForeignKey(Voucher, on_delete=models.SET_NULL, null=True, blank=True)
    data_used_mb = models.IntegerField(default=0)
    session_duration_minutes = models.IntegerField(default=0)
    login_time = models.DateTimeField()
    logout_time = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    mac_address = models.CharField(max_length=17, blank=True)
    signal_strength = models.IntegerField(null=True, blank=True)
    download_speed_mbps = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    upload_speed_mbps = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "Usage Session"
        verbose_name_plural = "Usage Sessions"
        ordering = ['-login_time']

    def __str__(self):
        user_display = self.customer.phone if self.customer else (self.user.username if self.user else "Unknown")
        return f"Session by {user_display} at {self.access_point.name}"

    @property
    def data_used_gb(self):
        return round(self.data_used_mb / 1024, 2) if self.data_used_mb else 0

    @property
    def is_active(self):
        return self.logout_time is None

    def save(self, *args, **kwargs):
        if self.logout_time and self.login_time:
            duration = self.logout_time - self.login_time
            self.session_duration_minutes = int(duration.total_seconds() // 60)
        super().save(*args, **kwargs)


class OTP(models.Model):
    """
    Stores OTPs for phone verification
    """
    phone_number = models.CharField(max_length=15)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    class Meta:
        verbose_name = "OTP"
        verbose_name_plural = "OTPs"
        ordering = ['-created_at']

    def is_expired(self):
        return (timezone.now() - self.created_at).seconds > 300  # 5 min expiry

    def __str__(self):
        return f"OTP for {self.phone_number} - {self.code}"