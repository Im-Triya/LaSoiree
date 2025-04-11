from django.urls import path
from .views import (
    RegisterVenueAPIView,
    VenueTablesAPIView,
    AddMenuItemAPIView,
    UpdateMenuItemAPIView,
    UpdateTableOccupancyAPIView,
    UpdateVenueAPIView,
    VenueTableStatsAPIView,
    VenueActiveOffersAPIView,
    CreateOfferAPIView,
    DeactivateOfferAPIView
)

urlpatterns = [
    path('register/', RegisterVenueAPIView.as_view(), name='register_venue'),
    path('venues/<str:venue_id>/tables/', VenueTablesAPIView.as_view(), name='get_tables'),
    path('venues/<str:venue_id>/menu/add/', AddMenuItemAPIView.as_view(), name='add_menu_item'),
    path('venues/<str:venue_id>/menu/update/', UpdateMenuItemAPIView.as_view(), name='update_menu_item'),
    path('tables/<str:qr_code>/occupancy/', UpdateTableOccupancyAPIView.as_view(), name='update_table_occupancy'),
    path('venues/<str:venue_id>/update/', UpdateVenueAPIView.as_view(), name='update_venue'),
    path('venue/occupancy_stats/', VenueTableStatsAPIView.as_view(), name='venue-stats'),
    path('venues/active_offers/', VenueActiveOffersAPIView.as_view(), name='venue-active-offers'),
    path('venue/create_offer/', CreateOfferAPIView.as_view(), name='create-offer'),
    path('venue/deactivate_offer/', DeactivateOfferAPIView.as_view(), name='deactivate-offer'),
]
