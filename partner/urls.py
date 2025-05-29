from django.urls import path
from .views import (
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
    path('venue/<str:venue_id>/update/', UpdateVenueAPIView.as_view(), name='venue-update'),
    path('venue/<str:venue_id>/tables/', VenueTablesAPIView.as_view(), name='get_tables'),
    path('venue/<str:venue_id>/menu/add/', AddMenuItemAPIView.as_view(), name='add_menu_item'),
    path('venue/<str:venue_id>/menu/update/', UpdateMenuItemAPIView.as_view(), name='update_menu_item'),
    path('table/<str:qr_code>/occupancy/', UpdateTableOccupancyAPIView.as_view(), name='update_table_occupancy'),
    path('venue/occupancy_stats/', VenueTableStatsAPIView.as_view(), name='venue-stats'),
    path('venue/active_offers/', VenueActiveOffersAPIView.as_view(), name='venue-active-offers'),
    path('venue/create_offer/', CreateOfferAPIView.as_view(), name='create-offer'),
    path('venue/deactivate_offer/', DeactivateOfferAPIView.as_view(), name='deactivate-offer'),
]
