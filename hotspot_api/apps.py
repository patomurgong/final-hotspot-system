# hotspot_api/apps.py
from django.apps import AppConfig

class HotspotApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hotspot_api'

    def ready(self):
        import hotspot_api.signals  # noqa