from django.utils import timezone
from django.db import models
from django.conf import settings
import uuid
from partner.models import Venue, Table,  Menu
from authentication.models import Waiter, CustomUser

class Booking(models.Model):
    booking_id =  models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name='bookings')
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name='bookings')
    qr_code = models.CharField(max_length=255)
    is_ongoing = models.BooleanField(default=True)
    date = models.DateField(default=timezone.now, editable=False)
    waiter = models.ForeignKey(Waiter, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')
    users = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='bookings')
    total_bill = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    def __str__(self):
        return f"Booking {self.booking_id} at {self.venue.name}, Table {self.table.table_number}"


class Cart(models.Model):
    cart_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='cart')
    total_bill = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    def __str__(self):
        return f"Cart {self.cart_id} for Booking {self.booking.booking_id}"


class CartItem(models.Model):
    cart_item_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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


class Presence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    venue = models.ForeignKey('partner.Venue', on_delete=models.CASCADE, related_name='presences')
    user = models.ForeignKey('authentication.CustomUser', on_delete=models.CASCADE, related_name='presences')
    time_in = models.DateTimeField(default=timezone.now)
    time_out = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('venue', 'user', 'time_out') 

    def __str__(self):
        return f'{self.user} at {self.venue} from {self.time_in} to {self.time_out or "now"}'