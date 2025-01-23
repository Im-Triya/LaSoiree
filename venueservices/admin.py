from django.contrib import admin
from .models import Booking, Cart, CartItem

admin.site.register(Booking)
admin.site.register(Cart)
admin.site.register(CartItem)
