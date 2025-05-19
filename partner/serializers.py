from rest_framework import serializers
from .models import Venue, Table, Menu, Offer


class VenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = ['venue_id', 'name', 'city', 'geo_location', 'number_of_tables', 'venue_image', 'owners', 'category', 'description', 'gst_number', 'pan_number', 'total_capacity', 'current_strength', 'qr_code']


class TableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Table
        fields = ['id', 'venue', 'table_number', 'qr_code', 'qr_image', 'is_occupied']


class MenuSerializer(serializers.ModelSerializer):
    class Meta:
        model = Menu
        fields = ['menu_item_id', 'venue', 'item_name', 'price', 'is_veg', 'tag', 'image']

class OfferSerializer(serializers.ModelSerializer):
    offer_type_display = serializers.CharField(source='get_offer_type_display', read_only=True)
    level_display = serializers.CharField(source='get_level_display', read_only=True)
    venue = serializers.PrimaryKeyRelatedField(queryset=Venue.objects.all())

    class Meta:
        model = Offer
        fields = [
            'offer_id',
            'venue',
            'user',
            'offer_type',
            'offer_type_display',
            'description',
            'level',
            'level_display',
            'start_date',
            'end_date',
            'discount_percentage',
            'is_entry_fee_required',
            'created_at',
            'updated_at'
        ]