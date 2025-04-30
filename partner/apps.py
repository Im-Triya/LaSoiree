from django.apps import AppConfig


class PartnerConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'partner'

    def ready(self):
        # Import models here to avoid circular imports
        from django.db import models
        from partner.models import Venue
        
        # Add the M2M relationship dynamically after both apps are loaded
        # This avoids circular dependency during migrations
        if not hasattr(Venue, 'owners'):
            owners_field = models.ManyToManyField(
                'authentication.Owner',
                related_name='venues'
            )
            Venue.add_to_class('owners', owners_field)
