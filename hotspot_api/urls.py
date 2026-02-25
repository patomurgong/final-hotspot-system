# hotspot_api/urls.py - FIXED WITH M-PESA CALLBACK
from django.urls import path, include
from rest_framework import routers
from . import views
from .views import (
    CustomerListView, HotspotPlanListView, TransactionListView,
    HotspotPlanViewSet,
)

router = routers.DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'accesspoints', views.AccessPointViewSet)
router.register(r'devices', views.DeviceViewSet)
router.register(r'usagedata', views.UsageDataViewSet)
router.register(r'vouchers', views.VoucherViewSet)
router.register(r'plans', HotspotPlanViewSet, basename='hotspotplan')
router.register(r'mpesa-transactions', views.MpesaTransactionViewSet)

urlpatterns = [
    # REST Framework API routes
    path('', include(router.urls)),

    # Admin Dashboard
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),

    # Dashboard views
    path('payments/', TransactionListView.as_view(), name='transaction_list'),
    path('plan-setup/', HotspotPlanListView.as_view(), name='plan_list'),
    path('customers/', CustomerListView.as_view(), name='customer_list'),
    path('dashboard/', views.dashboard_view, name='dashboard_view'),
    path('usage-data-chart/', views.usage_data_chart, name='usage_data_chart'),

    # ============================================================
    # 🚨 CRITICAL: M-Pesa Payment Endpoints
    # ============================================================
    # This endpoint receives payment requests FROM your frontend/mobile app
    path('initiate-mpesa-payment/', views.initiate_mpesa_payment, name='initiate-mpesa-payment'),
    
    # ✅ THIS IS ESSENTIAL - M-Pesa calls this after user pays!
    path('mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
    
    # 🏥 Health check to verify callback URL is reachable
    path('mpesa/webhook-health/', views.mpesa_webhook_health, name='mpesa_webhook_health'),

    # OTP Management endpoints
    path('otp/send/', views.send_otp, name='send-otp'),
    path('otp/verify/', views.verify_otp, name='verify-otp'),

    # Voucher Management endpoints
    path('voucher/lookup/', views.lookup_voucher, name='lookup-voucher'),
    path('voucher/enter/', views.enter_voucher, name='enter-voucher'),
    path('voucher/activate/', views.activate_voucher, name='activate-voucher'),
    path('voucher/check-balance/', views.check_balance, name='check-balance'),
    path('voucher/login/', views.login_voucher, name='login-voucher'),
    path('voucher/create/', views.create_voucher, name='create-voucher'),
]