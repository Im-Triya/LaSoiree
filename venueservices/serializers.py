from rest_framework import serializers
from .models import TableReservation, Order
from partner.models import Menu, Table

class TableReservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TableReservation
        fields = ['id', 'user', 'table', 'start_time', 'end_time']

class OrderSerializer(serializers.ModelSerializer):
    menu_item_name = serializers.CharField(source='menu_item.item_name', read_only=True)
    price = serializers.DecimalField(source='menu_item.price', max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'reservation', 'menu_item', 'menu_item_name', 'price', 'quantity', 'created_at']

class TableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Table
        fields = ['id', 'venue', 'table_number', 'is_occupied']
