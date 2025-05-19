from django.urls import path
from .views import (
    FetchVenuesView,
    BookingTableView,
    JoinTableView,
    SendWaiterNotificationView,
    AcceptBookingView,
    CallWaiterView,
    AddItemToCartView,
    GenerateBillView,
    EndBookingView,
    VenueMenuView,
    GetCurrentBookingDetailsView, 
    PresenceCheckInView, 
    PresenceLocationCheckView
)

urlpatterns = [
    path('venues/fetch/', FetchVenuesView.as_view(), name='fetch_venues'),
    path('bookings/book_table/', BookingTableView.as_view(), name='book_table'),
    path('bookings/join_table/', JoinTableView.as_view(), name='join_table'),
    path('waiters/notify/', SendWaiterNotificationView.as_view(), name='send_waiter_notification'),
    path('bookings/accept/', AcceptBookingView.as_view(), name='accept_booking'),
    path('waiters/call/', CallWaiterView.as_view(), name='call_waiter'),
    path('cart/add_item/', AddItemToCartView.as_view(), name='add_item_to_cart'),
    path('cart/generate_bill/', GenerateBillView.as_view(), name='generate_bill'),
    path('bookings/end/', EndBookingView.as_view(), name='end_booking'),
    path('<str:venue_id>/menu_view/', VenueMenuView.as_view(), name='menu_view'),
    path('get_current_booking/', GetCurrentBookingDetailsView.as_view(), name='current_booking_details'),
    path('presence/check-in/', PresenceCheckInView.as_view(), name='presence-check-in'),
    path('presence/location-check/', PresenceLocationCheckView.as_view(), name='presence-location-check')
]
