from rest_framework import serializers
from .models import Booking, Cart, CartItem
from partner.models import  Menu, Table, Venue
from authentication.models import Waiter
from partner.serializers import VenueSerializer, TableSerializer, MenuSerializer
from authentication.serializers import WaiterSerializer
from django.contrib.auth import get_user_model
from django.utils import timezone


class BookingSerializer(serializers.ModelSerializer):
    venue = VenueSerializer()
    table = TableSerializer()
    waiter = WaiterSerializer()
    users = serializers.PrimaryKeyRelatedField(queryset=get_user_model().objects.all(), many=True)

    class Meta:
        model = Booking
        fields = ['booking_id', 'venue', 'table', 'qr_code', 'is_ongoing', 'waiter', 'users', 'total_bill']

    def create(self, validated_data):
        venue_data = validated_data.pop('venue')
        table_data = validated_data.pop('table')
        waiter_data = validated_data.pop('waiter')
        users_data = validated_data.pop('users')
        
        venue = Venue.objects.create(**venue_data)
        table = Table.objects.create(**table_data)
        waiter = Waiter.objects.create(**waiter_data)
        
        booking = Booking.objects.create(
            venue=venue, 
            table=table, 
            waiter=waiter, 
            **validated_data
        )
        booking.users.set(users_data)
        return booking


class CartSerializer(serializers.ModelSerializer):
    booking = BookingSerializer()

    class Meta:
        model = Cart
        fields = ['cart_id', 'booking', 'total_bill']


class CartItemSerializer(serializers.ModelSerializer):
    cart = CartSerializer()
    menu_item = MenuSerializer()

    class Meta:
        model = CartItem
        fields = ['cart_item_id', 'cart', 'menu_item', 'quantity', 'total_price']

    def create(self, validated_data):
        cart_data = validated_data.pop('cart')
        menu_item_data = validated_data.pop('menu_item')
        
        cart = Cart.objects.create(**cart_data)
        menu_item = Menu.objects.create(**menu_item_data)
        
        cart_item = CartItem.objects.create(
            cart=cart, 
            menu_item=menu_item, 
            **validated_data
        )
        return cart_item

    def update(self, instance, validated_data):
        instance.quantity = validated_data.get('quantity', instance.quantity)
        instance.total_price = instance.menu_item.price * instance.quantity
        instance.save()
        return instance

class VisitorSerializer(serializers.ModelSerializer):
    """
    Serializer for visitor information based on table and booking data.
    """
    table_number = serializers.IntegerField(source='table.table_number')
    visitors = serializers.SerializerMethodField()
    dishes_ordered = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    total_bill = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    time_elapsed = serializers.SerializerMethodField()
    cart_id = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = ['booking_id', 'table_number', 'visitors', 'dishes_ordered', 
                  'status', 'total_bill', 'time_elapsed', 'cart_id']

    def get_visitors(self, obj):
        return [{'user_id': user.id, 'name': user.name} for user in obj.users.all()]

    def get_dishes_ordered(self, obj):
        try:
            cart = Cart.objects.get(booking=obj)
            return cart.items.count()
        except Cart.DoesNotExist:
            return 0

    def get_status(self, obj):
        if not obj.is_ongoing:
            return "Bill closed"
        elif obj.is_ongoing and obj.table.is_occupied:
            return "At table"
        else:
            return "Waiting for table"

    def get_time_elapsed(self, obj):
        if obj.created_at:
            current_time = timezone.now()
            elapsed_minutes = (current_time - obj.created_at).total_seconds() // 60
            return f"{int(elapsed_minutes)} mins"
        return "0 mins"

    def get_cart_id(self, obj):
        try:
            cart = Cart.objects.get(booking=obj)
            return str(cart.cart_id)
        except Cart.DoesNotExist:
            return None
