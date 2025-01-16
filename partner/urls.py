from django.urls import path
from .views import RegisterVenueAPIView, VenueTablesAPIView, AddMenuItemAPIView

urlpatterns = [
    path('register/', RegisterVenueAPIView.as_view(), name='register_venue'),
    path('<str:venue_id>/tables/', VenueTablesAPIView.as_view(), name='get_tables'),
     path('venues/<str:venue_id>/menu/add/', AddMenuItemAPIView.as_view(), name='add_menu_item'),
]
