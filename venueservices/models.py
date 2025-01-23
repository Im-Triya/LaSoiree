from django.db import models
from django.conf import settings
import uuid
from partner.models import Venue, Table, Waiter, Menu

class Booking(models.Model):
    booking_id =  models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='bookings')
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name='bookings')
    qr_code = models.CharField(max_length=255)
    is_occupied = models.BooleanField(default=False)
    waiter = models.ForeignKey(Waiter, on_delete=models.CASCADE, related_name='bookings')
    users = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='bookings')
    total_bill = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    def __str__(self):
        return f"Booking {self.booking_id} at {self.venue.name}, Table {self.table.table_number}"


class Cart(models.Model):
    cart_id = models.CharField(max_length=50, unique=True)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='cart')
    total_bill = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    def __str__(self):
        return f"Cart {self.cart_id} for Booking {self.booking.booking_id}"


class CartItem(models.Model):
    cart_item_id = models.CharField(max_length=50, unique=True)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    menu_item = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name='cart_items')
    quantity = models.IntegerField()
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"CartItem {self.cart_item_id} for Cart {self.cart.cart_id}"

    def save(self, *args, **kwargs):
        # Calculate total price as price * quantity before saving
        self.total_price = self.menu_item.price * self.quantity
        super().save(*args, **kwargs)
