# hotspot_api/apps.py

from django.apps import AppConfig


class HotspotApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hotspot_api'
    
    # 💥 ADD THIS METHOD 💥
    def ready(self):
        # Import your signals file to ensure the receiver functions are registered
        import hotspot_api.signals