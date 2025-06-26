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
    item_name = serializers.CharField(required=True)
    price = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2,
        required=True
    )
    tag = serializers.ChoiceField(
        choices=[
            ('chef_special', 'Chef Special'),
            ('starter', 'Starter'),
            ('main_course', 'Main Course'),
            ('liquor', 'Liquor'),
            ('beverage', 'Beverage'),
            ('tobacco', 'Tobacco')
        ],
        required=True
    )
    is_veg = serializers.BooleanField(required=False, default=False)
    image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Menu
        fields = ['menu_item_id', 'venue', 'item_name', 'price', 'is_veg', 'tag', 'image']
        extra_kwargs = {
            'venue': {'required': False},  # Will be set in the view
            'menu_item_id': {'read_only': True}
        }

    def to_internal_value(self, data):
        # Handle form-data case where values might come as lists
        processed_data = {}
        for key, value in data.items():
            if isinstance(value, list):
                if len(value) == 1:
                    processed_data[key] = value[0]
                else:
                    processed_data[key] = value
            else:
                processed_data[key] = value
        
        # Convert price to Decimal if it's a string
        if 'price' in processed_data and isinstance(processed_data['price'], str):
            try:
                processed_data['price'] = Decimal(processed_data['price'])
            except (InvalidOperation, ValueError):
                pass
        
        return super().to_internal_value(processed_data)

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