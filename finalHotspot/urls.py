# finalHotspot/urls.py
from django.contrib import admin
from django.urls import path, include
from hotspot_api.views import admin_dashboard, mpesa_callback

# Configure default admin site
admin.site.site_header = "Kirepanet ADMIN"
admin.site.site_title = "Kirepanet ADMIN"
admin.site.index_title = "Welcome to Kirepanet Administration"

# Make dashboard the admin homepage
admin.site.index = admin_dashboard

urlpatterns = [
    # ✅ CRITICAL: Callback MUST be BEFORE admin/ route
    path('admin/hotspot_api/mpesa/callback/', mpesa_callback, name='mpesa_callback'),
    
    # Admin routes
    path("admin/", admin.site.urls),
    
    # API routes
    path("api/", include("hotspot_api.urls")),
    path("", include("hotspot_api.urls")),
]