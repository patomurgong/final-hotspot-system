# hotspot_api/urls.py
from django.urls import path, include
from rest_framework import routers
from . import views
from .views import (
    CustomerListView, HotspotPlanListView, TransactionListView,
    HotspotPlanViewSet,
)
from . import kopa_views, points_views

router = routers.DefaultRouter()
router.register(r'users',             views.UserViewSet)
router.register(r'accesspoints',      views.AccessPointViewSet)
router.register(r'devices',           views.DeviceViewSet)
router.register(r'usagedata',         views.UsageDataViewSet)
router.register(r'vouchers',          views.VoucherViewSet)
router.register(r'plans',             HotspotPlanViewSet, basename='hotspotplan')
router.register(r'mpesa-transactions',views.MpesaTransactionViewSet)

urlpatterns = [
    # REST Framework router
    path('', include(router.urls)),

    # Admin Dashboard
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),

    # Dashboard views
    path('payments/',       TransactionListView.as_view(),  name='transaction_list'),
    path('plan-setup/',     HotspotPlanListView.as_view(),  name='plan_list'),
    path('customers/',      CustomerListView.as_view(),      name='customer_list'),
    path('dashboard/',      views.dashboard_view,            name='dashboard_view'),
    path('usage-data-chart/', views.usage_data_chart,        name='usage_data_chart'),
    path('customers/top/', views.top_customers, name='top-customers'),

    # ──────────────────────────────────────────────────────────
    # M-Pesa Payment Endpoints
    # ──────────────────────────────────────────────────────────
    path('initiate-mpesa-payment/', views.initiate_mpesa_payment, name='initiate-mpesa-payment'),
    path('mpesa/callback/',         views.mpesa_callback,          name='mpesa_callback'),
    path('mpesa/webhook-health/',   views.mpesa_webhook_health,    name='mpesa_webhook_health'),

    # ──────────────────────────────────────────────────────────
    # OTP
    # ──────────────────────────────────────────────────────────
    path('otp/send/',   views.send_otp,   name='send-otp'),
    path('otp/verify/', views.verify_otp, name='verify-otp'),

    # ──────────────────────────────────────────────────────────
    # Voucher
    # ──────────────────────────────────────────────────────────
    path('voucher/lookup/',        views.lookup_voucher,  name='lookup-voucher'),
    path('voucher/enter/',         views.enter_voucher,   name='enter-voucher'),
    path('voucher/activate/',      views.activate_voucher,name='activate-voucher'),
    path('voucher/check-balance/', views.check_balance,   name='check-balance'),
    path('voucher/login/',         views.login_voucher,   name='login-voucher'),
    path('voucher/create/',        views.create_voucher,  name='create-voucher'),

    # ──────────────────────────────────────────────────────────
    # ★ Kopa (data borrowing)
    # ──────────────────────────────────────────────────────────
    path('kopa/check/',   kopa_views.kopa_check,   name='kopa-check'),
    path('kopa/request/', kopa_views.kopa_request, name='kopa-request'),
    path('kopa/confirm/', kopa_views.kopa_confirm, name='kopa-confirm'),

    # ──────────────────────────────────────────────────────────
    # ★ Reward Points
    # ──────────────────────────────────────────────────────────
    path('points/check/',          points_views.points_check,          name='points-check'),
    path('points/redeem/',         points_views.points_redeem,         name='points-redeem'),
    path('points/redeem/confirm/', points_views.points_redeem_confirm, name='points-redeem-confirm'),
    path('customers/top/', views.top_customers, name='top-customers'),
]