from rest_framework import serializers
from .models import Booking, Cart, CartItem
from partner.models import Waiter, Menu, Table, Venue
from partner.serializers import VenueSerializer, TableSerializer, WaiterSerializer, MenuSerializer
from django.contrib.auth import get_user_model


class BookingSerializer(serializers.ModelSerializer):
    venue = VenueSerializer()
    table = TableSerializer()
    waiter = WaiterSerializer()
    users = serializers.PrimaryKeyRelatedField(queryset=get_user_model().objects.all(), many=True)

    class Meta:
        model = Booking
        fields = ['booking_id', 'venue', 'table', 'qr_code', 'is_occupied', 'waiter', 'users', 'total_bill']

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
        booking.users.set(users_data)  # Adding multiple users
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
