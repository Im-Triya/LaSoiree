from django.db import models
from django.conf import settings
from partner.models import Venue, Table, Menu

class TableReservation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    table = models.OneToOneField(Table, on_delete=models.CASCADE, related_name="reservation")
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Reservation by {self.user} for {self.table}"

class Order(models.Model):
    reservation = models.ForeignKey(TableReservation, on_delete=models.CASCADE, related_name="orders")
    menu_item = models.ForeignKey(Menu, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order: {self.menu_item.item_name} x {self.quantity} for Reservation {self.reservation.id}"
