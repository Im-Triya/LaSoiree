from rest_framework import serializers
from .models import Venue, Table, Menu

class VenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = ['venue_id', 'name', 'city', 'geo_location', 'number_of_tables']


class TableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Table
        fields = ['table_number', 'qr_code', 'qr_image']

class MenuSerializer(serializers.ModelSerializer):
    class Meta:
        model = Menu
        fields = ['id', 'venue', 'item_name', 'price', 'is_veg', 'tag']
