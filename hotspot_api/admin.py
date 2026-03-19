# hotspot_api/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.db.models import Sum

from .models import (
    Voucher, MpesaTransaction, AccessPoint,
    Device, UsageData, HotspotCustomer, HotspotPlan,
    KopaTransaction, CustomerPoints, PointsTransaction,
)


def get_customer_account(phone_number):
    formatted = f"254{str(phone_number)[-9:]}"
    try:
        return HotspotCustomer.objects.get(phone=formatted)
    except HotspotCustomer.DoesNotExist:
        return None


# ─────────────────────────────────────────────────────
# HotspotPlan
# ─────────────────────────────────────────────────────

@admin.register(HotspotPlan)
class HotspotPlanAdmin(admin.ModelAdmin):
    list_display  = ('plan_name', 'code', 'is_unlimited', 'data_limit_mb',
                      'speed_limit', 'validity_minutes', 'price', 'is_active')
    list_filter   = ('is_unlimited', 'is_active')
    search_fields = ('plan_name', 'code')
    readonly_fields = ('code', 'created_at')
    ordering = ('price', '-validity_minutes')


# ─────────────────────────────────────────────────────
# HotspotCustomer
# ─────────────────────────────────────────────────────

@admin.register(HotspotCustomer)
class HotspotCustomerAdmin(admin.ModelAdmin):
    list_display  = ('account_no', 'display_phone', 'expenditure',
                      'account_balance', 'joined', 'display_user_link')
    search_fields = ('phone', 'account_no', 'user__username')
    list_filter   = ('joined',)
    readonly_fields = ('account_no', 'joined')
    ordering = ('-joined',)

    def display_phone(self, obj):
        if obj.phone and obj.phone.startswith('254') and len(obj.phone) == 12:
            return '0' + obj.phone[3:]
        return obj.phone
    display_phone.short_description = 'Phone'

    def display_user_link(self, obj):
        if obj.user:
            return format_html('<a href="/admin/auth/user/{}/">{}</a>', obj.user.pk, obj.user.username)
        return "-"
    display_user_link.short_description = 'User'


# ─────────────────────────────────────────────────────
# MpesaTransaction
# ─────────────────────────────────────────────────────

@admin.register(MpesaTransaction)
class MpesaTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'get_transaction_id', 'display_customer_account', 'display_voucher_code',
        'display_local_phone', 'amount', 'status', 'created_at', 'action_buttons'
    )
    list_filter   = ('status', 'created_at')
    search_fields = ('phone_number', 'transaction_id', 'mpesa_receipt_number',
                     'checkout_request_id', 'merchant_request_id')
    readonly_fields = ('checkout_request_id', 'merchant_request_id', 'transaction_id',
                       'mpesa_receipt_number', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    actions  = ['mark_as_failed', 'retry_voucher_creation']

    def get_transaction_id(self, obj):
        tid = obj.transaction_id or obj.mpesa_receipt_number or '-'
        if tid != '-':
            color = 'green' if obj.status == 'COMPLETED' else 'blue'
            return format_html('<span style="color:{};">{}</span>', color, tid)
        elif obj.status == 'PENDING':
            return format_html('<span style="color:orange;">⏳ Pending</span>')
        return '-'
    get_transaction_id.short_description = 'Transaction ID'

    def display_customer_account(self, obj):
        customer = get_customer_account(obj.phone_number)
        if customer:
            return format_html('<a href="/admin/hotspot_api/hotspotcustomer/{}/change/">{}</a>',
                               customer.pk, customer.account_no)
        return format_html('<span style="color:red;">Unassociated</span>')
    display_customer_account.short_description = 'Customer'

    def display_voucher_code(self, obj):
        if obj.voucher:
            return format_html('<a href="/admin/hotspot_api/voucher/{}/change/" style="color:blue;">{}</a>',
                               obj.voucher.pk, obj.voucher.code)
        elif obj.status == 'COMPLETED':
            return format_html('<span style="color:orange;">⚠️ No Voucher</span>')
        return '-'
    display_voucher_code.short_description = 'Code'

    def display_local_phone(self, obj):
        if obj.phone_number and obj.phone_number.startswith('254'):
            return '0' + obj.phone_number[3:]
        return obj.phone_number
    display_local_phone.short_description = 'Phone'

    def action_buttons(self, obj):
        if obj.status == 'COMPLETED' and obj.voucher:
            return format_html('<span style="color:green;">✅ Voucher Created</span>')
        elif obj.status == 'COMPLETED' and not obj.voucher:
            return format_html('<span style="color:orange;">⚠️ Create Voucher</span>')
        elif obj.status == 'PENDING':
            return format_html('<span style="color:gray;">⏳ Waiting...</span>')
        return format_html('<span style="color:red;">❌ Failed</span>')
    action_buttons.short_description = 'Action'

    def mark_as_failed(self, request, queryset):
        updated = queryset.filter(status='PENDING').update(status='FAILED')
        self.message_user(request, f'{updated} transactions marked as failed.')
    mark_as_failed.short_description = '❌ Mark selected as Failed'

    def retry_voucher_creation(self, request, queryset):
        from .views import create_voucher_for_transaction
        count, errors = 0, 0
        for txn in queryset.filter(status='COMPLETED', voucher__isnull=True):
            v = create_voucher_for_transaction(txn)
            if v:
                txn.voucher = v; txn.save(); count += 1
            else:
                errors += 1
        if count:  self.message_user(request, f'✅ {count} voucher(s) created.')
        if errors: self.message_user(request, f'❌ {errors} failed.', level='ERROR')
    retry_voucher_creation.short_description = '🎫 Retry voucher creation'


# ─────────────────────────────────────────────────────
# Voucher
# ─────────────────────────────────────────────────────

@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display  = ('code', 'plan_name', 'display_phone', 'is_active',
                      'display_status', 'created_at')
    list_filter   = ('is_active', 'plan_name', 'used_at')
    search_fields = ('code', 'phone_number')
    readonly_fields = ('code', 'created_at', 'used_at', 'last_activity')
    ordering = ('-created_at',)

    fieldsets = (
        ('Voucher Details',   {'fields': ('code', 'plan_name', 'description', 'is_active')}),
        ('Plan Config',       {'fields': ('data_limit_mb', 'validity_hours', 'expiry_date')}),
        ('Customer Info',     {'fields': ('phone_number', 'mac_address')}),
        ('Usage Tracking',    {'fields': ('used_at', 'used_by_device', 'data_used_mb', 'last_activity')}),
        ('Transaction Link',  {'fields': ('created_by_transaction',)}),
        ('Timestamps',        {'fields': ('created_at',)}),
    )

    def display_phone(self, obj):
        if obj.phone_number and obj.phone_number.startswith('254'):
            return '0' + obj.phone_number[3:]
        return obj.phone_number or '-'
    display_phone.short_description = 'Phone'

    def display_status(self, obj):
        colors = {'Available': 'green', 'In Use': 'blue', 'Expired': 'red',
                  'Depleted': 'orange', 'Inactive': 'gray'}
        return format_html('<span style="color:{};font-weight:bold;">{}</span>',
                           colors.get(obj.status, 'black'), obj.status)
    display_status.short_description = 'Status'


# ─────────────────────────────────────────────────────
# AccessPoint / Device / UsageData
# ─────────────────────────────────────────────────────

@admin.register(AccessPoint)
class AccessPointAdmin(admin.ModelAdmin):
    list_display  = ('name', 'location', 'ip_address', 'ssid', 'mac_address', 'is_online', 'installation_date')
    search_fields = ('name', 'location', 'ip_address', 'ssid')
    list_filter   = ('is_online',)


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display  = ('device_name', 'mac_address', 'user')
    search_fields = ('device_name', 'mac_address', 'user__username')


@admin.register(UsageData)
class UsageDataAdmin(admin.ModelAdmin):
    list_display = ('user', 'access_point', 'data_used_gb', 'login_time', 'logout_time')
    list_filter  = ('access_point',)
    search_fields = ('user__username',)


# ─────────────────────────────────────────────────────
# ★ KopaTransaction Admin
# ─────────────────────────────────────────────────────

@admin.register(KopaTransaction)
class KopaTransactionAdmin(admin.ModelAdmin):
    list_display  = (
        'display_phone', 'data_mb', 'amount_ksh', 'fee_ksh',
        'total_owed_display', 'display_status', 'created_at',
        'confirmed_at', 'repaid_at'
    )
    list_filter   = ('status', 'created_at')
    search_fields = ('phone_number',)
    readonly_fields = ('created_at', 'confirmed_at', 'repaid_at')
    ordering = ('-created_at',)
    actions  = ['mark_as_expired', 'manually_mark_repaid']

    fieldsets = (
        ('Borrow Details', {'fields': ('phone_number', 'data_mb', 'amount_ksh', 'fee_ksh', 'status')}),
        ('Links',          {'fields': ('voucher', 'repaid_via')}),
        ('Timestamps',     {'fields': ('created_at', 'confirmed_at', 'repaid_at')}),
    )

    def display_phone(self, obj):
        return obj.phone_formatted
    display_phone.short_description = 'Phone'

    def total_owed_display(self, obj):
        return format_html('<strong>{} Ksh</strong>', float(obj.total_owed))
    total_owed_display.short_description = 'Total Owed'

    def display_status(self, obj):
        colors = {'PENDING': 'orange', 'ACTIVE': 'red', 'REPAID': 'green', 'EXPIRED': 'gray'}
        icons  = {'PENDING': '⏳', 'ACTIVE': '🔴', 'REPAID': '✅', 'EXPIRED': '💀'}
        return format_html(
            '<span style="color:{};font-weight:bold;">{} {}</span>',
            colors.get(obj.status, 'black'), icons.get(obj.status, ''), obj.get_status_display()
        )
    display_status.short_description = 'Status'

    def mark_as_expired(self, request, queryset):
        updated = queryset.filter(status='PENDING').update(status='EXPIRED')
        self.message_user(request, f'{updated} Kopa transactions marked as expired.')
    mark_as_expired.short_description = '💀 Mark selected as Expired'

    def manually_mark_repaid(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(status='ACTIVE').update(status='REPAID', repaid_at=timezone.now())
        self.message_user(request, f'✅ {updated} Kopa transactions marked as repaid.')
    manually_mark_repaid.short_description = '✅ Manually mark as Repaid'


# ─────────────────────────────────────────────────────
# ★ CustomerPoints Admin
# ─────────────────────────────────────────────────────

@admin.register(CustomerPoints)
class CustomerPointsAdmin(admin.ModelAdmin):
    list_display  = (
        'display_phone', 'total_points', 'lifetime_earned',
        'lifetime_redeemed', 'total_spent_ksh', 'updated_at'
    )
    search_fields = ('phone_number',)
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-total_points',)

    def display_phone(self, obj):
        return obj.phone_formatted
    display_phone.short_description = 'Phone'


# ─────────────────────────────────────────────────────
# ★ PointsTransaction Admin
# ─────────────────────────────────────────────────────

@admin.register(PointsTransaction)
class PointsTransactionAdmin(admin.ModelAdmin):
    list_display  = ('display_phone', 'display_points', 'transaction_type', 'description', 'created_at')
    list_filter   = ('transaction_type', 'created_at')
    search_fields = ('phone_number', 'description')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)

    def display_phone(self, obj):
        p = str(obj.phone_number)
        return f"0{p[3:]}" if p.startswith('254') else p
    display_phone.short_description = 'Phone'

    def display_points(self, obj):
        color = 'green' if obj.points > 0 else 'red'
        sign  = '+' if obj.points > 0 else ''
        return format_html('<span style="color:{};font-weight:bold;">{}{}</span>',
                           color, sign, obj.points)
    display_points.short_description = 'Points'


# ─────────────────────────────────────────────────────
# Extended User Admin
# ─────────────────────────────────────────────────────

class HotspotCustomerInline(admin.StackedInline):
    model = HotspotCustomer
    can_delete = False
    verbose_name_plural = "Hotspot Customer"
    fk_name = "user"


class UserAdmin(BaseUserAdmin):
    inlines = (HotspotCustomerInline,)
    list_display = BaseUserAdmin.list_display + ('get_phone', 'get_balance')

    def get_phone(self, obj):
        try:    return obj.hotspotcustomer.phone
        except: return "-"
    get_phone.short_description = 'Phone'

    def get_balance(self, obj):
        try:    return obj.hotspotcustomer.account_balance
        except: return 0
    get_balance.short_description = 'Balance'


admin.site.unregister(User)
admin.site.register(User, UserAdmin)