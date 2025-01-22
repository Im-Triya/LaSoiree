from django.urls import path
from .views import (
    RegisterVenueAPIView,
    VenueTablesAPIView,
    AddMenuItemAPIView,
    UpdateTableOccupancyAPIView,
    UpdateVenueAPIView,
)

urlpatterns = [
    path('register/', RegisterVenueAPIView.as_view(), name='register_venue'),
    path('venues/<str:venue_id>/tables/', VenueTablesAPIView.as_view(), name='get_tables'),
    path('venues/<str:venue_id>/menu/add/', AddMenuItemAPIView.as_view(), name='add_menu_item'),
    path('tables/<str:qr_code>/occupancy/', UpdateTableOccupancyAPIView.as_view(), name='update_table_occupancy'),
    path('venues/<str:venue_id>/update/', UpdateVenueAPIView.as_view(), name='update_venue'),
]
