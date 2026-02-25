# hotspot_api/admin.py - CLEANED UP VERSION

from django.contrib import admin
from django.utils.html import format_html
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import (
    Voucher, MpesaTransaction, AccessPoint,
    Device, UsageData, HotspotCustomer, HotspotPlan
)

# -------------------------------
# Helper: Find customer
# -------------------------------
def get_customer_account(phone_number):
    formatted_phone = f"254{str(phone_number)[-9:]}"
    try:
        return HotspotCustomer.objects.get(phone=formatted_phone)
    except HotspotCustomer.DoesNotExist:
        return None

# -------------------------------
# HotspotPlan Admin
# -------------------------------
@admin.register(HotspotPlan)
class HotspotPlanAdmin(admin.ModelAdmin):
    list_display = (
        'plan_name', 'code', 'is_unlimited',
        'data_limit_mb', 'speed_limit',
        'validity_minutes', 'price', 'is_active'
    )
    list_filter = ('is_unlimited', 'is_active')
    search_fields = ('plan_name', 'code')
    readonly_fields = ('code', 'created_at')
    ordering = ('price', '-validity_minutes')

# -------------------------------
# HotspotCustomer Admin
# -------------------------------
@admin.register(HotspotCustomer)
class HotspotCustomerAdmin(admin.ModelAdmin):
    list_display = (
        'account_no', 'display_phone', 'expenditure',
        'account_balance', 'joined', 'display_user_link'
    )
    search_fields = ('phone', 'account_no', 'user__username')
    list_filter = ('joined',)
    readonly_fields = ('account_no', 'joined')
    ordering = ('-joined',)

    def display_phone(self, obj):
        if obj.phone and obj.phone.startswith('254') and len(obj.phone) == 12:
            return '0' + obj.phone[3:]
        return obj.phone
    display_phone.short_description = 'Phone'

    def display_user_link(self, obj):
        if obj.user:
            return format_html('<a href="/admin/auth/user/{}/">{}</a>',
                               obj.user.pk, obj.user.username)
        return "-"
    display_user_link.short_description = 'User'

# -------------------------------
# ✅ FIXED MpesaTransaction Admin (NO DUPLICATES)
# -------------------------------
@admin.register(MpesaTransaction)
class MpesaTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'get_transaction_id',
        'display_customer_account',
        'display_voucher_code',
        'display_local_phone',
        'amount', 
        'status', 
        'created_at', 
        'action_buttons'
    )
    list_filter = ('status', 'created_at')
    search_fields = (
        'phone_number', 
        'transaction_id', 
        'mpesa_receipt_number',
        'checkout_request_id',
        'merchant_request_id'
    )
    readonly_fields = (
        'checkout_request_id', 
        'merchant_request_id', 
        'transaction_id',
        'mpesa_receipt_number',
        'created_at',
        'updated_at'
    )
    ordering = ('-created_at',)
    
    # ✅ Admin actions
    actions = ['mark_as_failed', 'retry_voucher_creation']
    
    def get_transaction_id(self, obj):
        """Display transaction ID"""
        tid = obj.transaction_id or obj.mpesa_receipt_number or '-'
        
        if tid != '-':
            color = 'green' if obj.status == 'COMPLETED' else 'blue'
            return format_html('<span style="color: {};">{}</span>', color, tid)
        elif obj.status == 'PENDING':
            return format_html('<span style="color: orange;">⏳ Pending</span>')
        else:
            return '-'
    
    get_transaction_id.short_description = 'Transaction ID'
    get_transaction_id.admin_order_field = 'transaction_id'

    def display_customer_account(self, obj):
        customer = get_customer_account(obj.phone_number)
        if customer:
            return format_html(
                '<a href="/admin/hotspot_api/hotspotcustomer/{}/change/">{}</a>',
                customer.pk,
                customer.account_no
            )
        return format_html('<span style="color: red;">Unassociated</span>')
    display_customer_account.short_description = 'Customer'

    def display_voucher_code(self, obj):
        """Show actual linked voucher code"""
        if obj.voucher:
            return format_html(
                '<a href="/admin/hotspot_api/voucher/{}/change/" style="color: blue;">{}</a>',
                obj.voucher.pk,
                obj.voucher.code
            )
        elif obj.status == 'COMPLETED':
            return format_html('<span style="color: orange;">⚠️ No Voucher</span>')
        else:
            return '-'
    display_voucher_code.short_description = 'Code'

    def display_local_phone(self, obj):
        if obj.phone_number and obj.phone_number.startswith('254') and len(obj.phone_number) == 12:
            return '0' + obj.phone_number[3:]
        return obj.phone_number
    display_local_phone.short_description = 'Phone'

    def action_buttons(self, obj):
        """Action buttons for transaction status"""
        if obj.status == 'COMPLETED' and obj.voucher:
            return format_html('<span style="color: green;">✅ Voucher Created</span>')
        elif obj.status == 'COMPLETED' and not obj.voucher:
            return format_html('<span style="color: orange;">⚠️ Create Voucher</span>')
        elif obj.status == 'PENDING':
            return format_html('<span style="color: gray;">⏳ Waiting...</span>')
        else:
            return format_html('<span style="color: red;">❌ Failed</span>')
    action_buttons.short_description = 'Action'
    
    def mark_as_failed(self, request, queryset):
        """Mark selected pending transactions as failed"""
        updated = queryset.filter(status='PENDING').update(status='FAILED')
        self.message_user(request, f'{updated} transactions marked as failed.')
    mark_as_failed.short_description = '❌ Mark selected as Failed'
    
    def retry_voucher_creation(self, request, queryset):
        """Retry voucher creation for completed transactions without vouchers"""
        from .views import create_voucher_for_transaction
        count = 0
        errors = 0
        
        for transaction in queryset.filter(status='COMPLETED', voucher__isnull=True):
            voucher = create_voucher_for_transaction(transaction)
            if voucher:
                transaction.voucher = voucher
                transaction.save()
                count += 1
            else:
                errors += 1
        
        if count > 0:
            self.message_user(request, f'✅ {count} voucher(s) created successfully.')
        if errors > 0:
            self.message_user(request, f'❌ {errors} voucher(s) failed to create.', level='ERROR')
    retry_voucher_creation.short_description = '🎫 Retry voucher creation'


# -------------------------------
# Voucher Admin
# -------------------------------
@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = (
        'code', 
        'plan_name', 
        'display_phone',
        'is_active', 
        'display_status',
        'created_at'
    )
    list_filter = ('is_active', 'plan_name', 'used_at')
    search_fields = ('code', 'phone_number')
    readonly_fields = ('code', 'created_at', 'used_at', 'last_activity')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Voucher Details', {
            'fields': ('code', 'plan_name', 'description', 'is_active')
        }),
        ('Plan Configuration', {
            'fields': ('data_limit_mb', 'validity_hours', 'expiry_date')
        }),
        ('Customer Info', {
            'fields': ('phone_number', 'mac_address')
        }),
        ('Usage Tracking', {
            'fields': (
                'used_at',
                'used_by_device',
                'data_used_mb',
                'last_activity'
            )
        }),
        ('Transaction Link', {
            'fields': ('created_by_transaction',)
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
    
    def display_phone(self, obj):
        if obj.phone_number and obj.phone_number.startswith('254'):
            return '0' + obj.phone_number[3:]
        return obj.phone_number or '-'
    display_phone.short_description = 'Phone'
    
    def display_status(self, obj):
        status = obj.status
        colors = {
            'Available': 'green',
            'In Use': 'blue',
            'Expired': 'red',
            'Depleted': 'orange',
            'Inactive': 'gray'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(status, 'black'),
            status
        )
    display_status.short_description = 'Status'


# -------------------------------
# AccessPoint Admin
# -------------------------------
@admin.register(AccessPoint)
class AccessPointAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'location', 'ip_address',
        'ssid', 'mac_address', 'is_online', 'installation_date'
    )
    search_fields = ('name', 'location', 'ip_address', 'ssid')
    list_filter = ('is_online',)

# -------------------------------
# Device Admin
# -------------------------------
@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('device_name', 'mac_address', 'user')
    search_fields = ('device_name', 'mac_address', 'user__username')

# -------------------------------
# UsageData Admin
# -------------------------------
@admin.register(UsageData)
class UsageDataAdmin(admin.ModelAdmin):
    list_display = ('user', 'access_point', 'data_used_gb', 'login_time', 'logout_time')
    list_filter = ('access_point',)
    search_fields = ('user__username',)

# -------------------------------
# Extend Django User
# -------------------------------
class HotspotCustomerInline(admin.StackedInline):
    model = HotspotCustomer
    can_delete = False
    verbose_name_plural = "Hotspot Customer"
    fk_name = "user"

class UserAdmin(BaseUserAdmin):
    inlines = (HotspotCustomerInline,)
    list_display = BaseUserAdmin.list_display + ('get_phone', 'get_balance')

    def get_phone(self, obj):
        try:
            return obj.hotspotcustomer.phone
        except HotspotCustomer.DoesNotExist:
            return "-"
    get_phone.short_description = 'Phone'

    def get_balance(self, obj):
        try:
            return obj.hotspotcustomer.account_balance
        except HotspotCustomer.DoesNotExist:
            return 0
    get_balance.short_description = 'Balance'

# Unregister default User admin and register custom one
admin.site.unregister(User)
admin.site.register(User, UserAdmin)