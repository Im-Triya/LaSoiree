from django.utils import timezone
from django.db import models
from django.conf import settings
import uuid
from django.core.validators import MinValueValidator
from django.db import transaction
from partner.models import Venue, Table, Menu
from authentication.models import Waiter

class Booking(models.Model):
    booking_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    venue = models.ForeignKey(
        Venue, 
        on_delete=models.CASCADE, 
        related_name='bookings',
        db_index=True
    )
    table = models.ForeignKey(
        Table, 
        on_delete=models.CASCADE, 
        related_name='bookings',
        db_index=True
    )
    qr_code = models.CharField(max_length=255, db_index=True)
    is_ongoing = models.BooleanField(default=False, db_index=True)
    waiter = models.ForeignKey(
        Waiter, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='bookings',
        db_index=True
    )
    total_bill = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.0,
        validators=[MinValueValidator(0)]
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['venue', 'is_ongoing']),
            models.Index(fields=['table', 'is_ongoing']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['table'],
                condition=models.Q(is_ongoing=True),
                name='unique_ongoing_booking_per_table'
            )
        ]

    def __str__(self):
        return f"Booking {self.booking_id} at {self.venue.name}, Table {self.table.table_number}"

    def save(self, *args, **kwargs):
        if not self.qr_code and self.table:
            self.qr_code = f"BOOKING::{self.venue.venue_id}::{self.table.table_number}::{self.booking_id}"
        super().save(*args, **kwargs)


class Cart(models.Model):
    cart_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(
        Booking, 
        on_delete=models.CASCADE, 
        related_name='cart',
        db_index=True
    )
    total_bill = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.0,
        validators=[MinValueValidator(0)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Cart'
        verbose_name_plural = 'Carts'

    def __str__(self):
        return f"Cart {self.cart_id} for Booking {self.booking.booking_id}"

    def update_total(self):
        """Recalculates the cart total from all items"""
        self.total_bill = sum(item.total_price for item in self.items.all())
        self.save()


class CartItem(models.Model):
    cart_item_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(
        Cart, 
        on_delete=models.CASCADE, 
        related_name='items',
        db_index=True
    )
    menu_item = models.ForeignKey(
        Menu, 
        on_delete=models.CASCADE, 
        related_name='cart_items',
        db_index=True
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )
    total_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Cart Item'
        verbose_name_plural = 'Cart Items'

    def __str__(self):
        return f"CartItem {self.cart_item_id} for Cart {self.cart.cart_id}"

    def save(self, *args, **kwargs):
        # Calculate total price before saving
        self.total_price = self.menu_item.price * self.quantity
        super().save(*args, **kwargs)
        
        # Update the parent cart total
        self.cart.update_total()

    def delete(self, *args, **kwargs):
        cart = self.cart
        super().delete(*args, **kwargs)
        cart.update_total()