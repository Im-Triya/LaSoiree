from django.urls import path
from .views import BookTableAPIView, PlaceOrderAPIView, BillingAPIView

urlpatterns = [
    path('book-table/<str:qr_code>/', BookTableAPIView.as_view(), name='book_table'),
    path('place-order/<int:reservation_id>/', PlaceOrderAPIView.as_view(), name='place_order'),
    path('billing/<int:reservation_id>/', BillingAPIView.as_view(), name='billing'),
]
