from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from rest_framework import status
from decimal import Decimal
from django.contrib.auth import get_user_model
from partner.models import Venue, Table, Menu
from authentication.models import Waiter
from .models import Booking, Cart, CartItem
from geopy.distance import geodesic
import uuid

class FetchVenuesView(APIView):
    def post(self, request, *args, **kwargs):
        user_id = request.data.get('user_id')

        try:
            user = get_user_model().objects.get(id=user_id)
        except get_user_model().DoesNotExist:
            raise NotFound({"message": "User not found."})

        venues = Venue.objects.all()

        def get_geo(venue):
            """Helper function to safely extract latitude & longitude."""
            venue_geo = venue.geo_location or {}  # Ensure it's not None
            return (
                venue_geo.get("latitude", 0),  # Default value avoids errors
                venue_geo.get("longitude", 0),
            )

        # Check if user's location permission is granted
        if user.is_location_permission_granted:
            user_geo = user.location or {}  # Ensure it's not None
            user_lat = user_geo.get("latitude")
            user_lon = user_geo.get("longitude")

            # Validate that user location exists before sorting
            if user_lat is not None and user_lon is not None:
                user_location = (user_lat, user_lon)

                # Sort venues based on distance from user
                venues = sorted(
                    venues, key=lambda venue: geodesic(user_location, get_geo(venue)).kilometers
                )

        # Construct response
        venue_data = [
            {
                "venue_id": venue.venue_id,
                "name": venue.name,
                "city": venue.city,
                "geo_location": {
                    "latitude": venue.geo_location.get("latitude", 0),
                    "longitude": venue.geo_location.get("longitude", 0),
                },
                "number_of_tables": venue.number_of_tables,
                "venue_image": venue.venue_image.url if venue.venue_image else None,
            }
            for venue in venues
        ]

        return Response({"venues": venue_data})

class BookingTableView(APIView):
    def post(self, request, *args, **kwargs):
        qr_code = request.data.get('qr_code')
        user_id = request.data.get('user_id')

        try:
            user = get_user_model().objects.get(id=user_id)
        except get_user_model().DoesNotExist:
            raise NotFound({"message": "User not found."})

        try:
            venue_id, table_no = qr_code.split("::")
            venue = Venue.objects.get(venue_id=venue_id)
            table = Table.objects.get(qr_code=qr_code)
        except (Venue.DoesNotExist, Table.DoesNotExist):
            raise NotFound({"message": "Invalid QR code.", "errors": "Venue or Table not found."})

        if table.is_occupied:
            return Response({"message": "Failed to book table.", "errors": "Table already occupied."}, status=status.HTTP_400_BAD_REQUEST)

        booking = Booking.objects.create(
            booking_id=uuid.uuid4(),
            venue=venue,
            table=table,
            waiter=None,
            qr_code=qr_code,
            is_ongoing=True
        )
        
        booking.users.add(user)
        booking.save()

        table.is_occupied = True
        table.save()

        users_data = [{"user_id": u.id, "name": u.name} for u in booking.users.all()]

        return Response({
            "message": "Table booked successfully.",
            "booking_id": booking.booking_id,
            "table": {
                "venue_name": venue.name,
                "table_number": table.table_number,
                "is_occupied": table.is_occupied
            },
            "users": users_data
        })

class JoinTableView(APIView):
    def post(self, request, *args, **kwargs):
        qr_code = request.data.get('qr_code')
        user_id = request.data.get('user_id')

        try:
            user = get_user_model().objects.get(id=user_id)
        except get_user_model().DoesNotExist:
            raise NotFound({"message": "User not found."})

        try:
            venue_id, table_no = qr_code.split("::")
            venue = Venue.objects.get(venue_id=venue_id)
            table = Table.objects.get(qr_code=qr_code)
        except (Venue.DoesNotExist, Table.DoesNotExist):
            raise NotFound({"message": "Invalid QR code.", "errors": "Venue or Table not found."})

        if table.is_occupied:
            booking = Booking.objects.get(venue=venue, table=table, is_ongoing=True)
            booking.users.add(user)
            booking.save()

            users_data = [{"user_id": u.id, "name": u.name} for u in booking.users.all()]
            return Response({
                "message": "Successfully joined the table.",
                "booking_id": booking.booking_id,
                "venue" : venue.name,
                "table": table_no,
                "users": users_data
            })
        else:
            return Response({"message": "Failed to join table.", "errors": "Table not available."}, status=status.HTTP_400_BAD_REQUEST)


class SendWaiterNotificationView(APIView):
    def post(self, request, *args, **kwargs):
        booking_id = request.data.get('booking_id')
        venue_id = request.data.get('venue_id')

        try:
            venue = Venue.objects.get(venue_id=venue_id)
            booking = Booking.objects.get(booking_id=booking_id, venue=venue)
        except Venue.DoesNotExist or Booking.DoesNotExist:
            raise NotFound({"message": "Booking or Venue not found."})

        waiters = Waiter.objects.filter(venue=venue)
        if not waiters:
            return Response({"message": "Failed to send waiter notifications.", "errors": "No available waiters."}, status=status.HTTP_400_BAD_REQUEST)

        # Notification system to be implemented here
        return Response({"message": "Notifications to waiters sent successfully."})

class AcceptBookingView(APIView):
    def post(self, request, *args, **kwargs):
        booking_id = request.data.get('booking_id')
        waiter_id = request.data.get('waiter_id')

        try:
            booking = Booking.objects.get(booking_id=booking_id)
            waiter = Waiter.objects.get(waiter_id=waiter_id, venue=booking.venue)
        except Booking.DoesNotExist or Waiter.DoesNotExist:
            raise NotFound({"message": "Booking or Waiter not found."})

        if booking.waiter:
            return Response({"message": "Failed to accept booking.", "errors": "Booking already assigned."}, status=status.HTTP_400_BAD_REQUEST)

        booking.waiter = waiter
        booking.save()

        return Response({
            "message": "Booking accepted by waiter.",
            "booking": {
                "booking_id": booking.booking_id,
                "table_number": booking.table.table_number, 
                "waiter": {
                    "waiter_id": waiter.waiter_id,
                    "name": waiter.name
                }
            }
        })

class CallWaiterView(APIView):
    def post(self, request, *args, **kwargs):
        booking_id = request.data.get('booking_id')
        user_id = request.data.get('user_id')

        try:
            booking = Booking.objects.get(booking_id=booking_id)
            user = get_user_model().objects.get(id=user_id)
        except Booking.DoesNotExist or get_user_model().DoesNotExist:
            raise NotFound({"message": "Booking or User not found."})

        waiter = booking.waiter
        if not waiter:
            return Response({"message": "Failed to notify waiter.", "errors": "Waiter not assigned."}, status=status.HTTP_400_BAD_REQUEST)

        #call to waiter to be sent here
        return Response({
            "message": "Waiter notified successfully.",
            "table_number": booking.table.table_number, 
            "waiter": {
                "waiter_id": waiter.waiter_id,
                "name": waiter.name
            }
        })

# class MarkServiceAsServicedView(APIView):
#     def put(self, request, *args, **kwargs):
#         service_call_id = request.data.get('service_call_id')
#         waiter_id = request.data.get('waiter_id')

#         try:
#             service_call = ServiceCall.objects.get(id=service_call_id)
#             waiter = Waiter.objects.get(waiter_id=waiter_id)
#         except ServiceCall.DoesNotExist or Waiter.DoesNotExist:
#             raise NotFound({"message": "Service call or Waiter not found."})

#         service_call.status = 'Serviced'
#         service_call.save()

#         return Response({"message": "Service call marked as serviced."})

class AddItemToCartView(APIView):
    def post(self, request, *args, **kwargs):
        booking_id = request.data.get('booking_id')
        menu_item_id = request.data.get('menu_item_id')
        quantity = request.data.get('quantity')

        try:
            booking = Booking.objects.get(booking_id=booking_id)
            menu_item = Menu.objects.get(menu_item_id=menu_item_id)
        except Booking.DoesNotExist or Menu.DoesNotExist:
            raise NotFound({"message": "Booking or Menu item not found."})

        cart, created = Cart.objects.get_or_create(booking=booking)
        cart_item, item_created = CartItem.objects.get_or_create(cart=cart, menu_item=menu_item, defaults={
            "quantity": quantity,
            "total_price": menu_item.price * quantity
        })

        if not item_created:
            cart_item.quantity += quantity
            cart_item.total_price = menu_item.price * cart_item.quantity
            cart_item.save()

        cart.total_bill = Decimal(cart.total_bill) + cart_item.total_price
        cart.save()

        booking.total_bill = cart.total_bill
        booking.save()

        cart_items = cart.items.all() 
        items_data = [
            {
                "item_name": cart_item.menu_item.item_name,
                "quantity": cart_item.quantity
            }
            for cart_item in cart_items
        ]

        return Response({
            "message": "Item added to cart successfully.",
            "cart": {
                "cart_id": cart.cart_id,
                "total_bill": cart.total_bill,
                "items": items_data 
            }
        })
    
    def delete(self, request, *args, **kwargs):
        booking_id = request.data.get('booking_id')
        menu_item_id = request.data.get('menu_item_id')

        try:
            booking = Booking.objects.get(booking_id=booking_id)
            cart = Cart.objects.get(booking=booking)
            cart_item = CartItem.objects.get(cart=cart, menu_item_id=menu_item_id)
        except (Booking.DoesNotExist, Cart.DoesNotExist, CartItem.DoesNotExist):
            raise NotFound({"message": "Booking, cart, or menu item not found."})

        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.total_price = cart_item.menu_item.price * cart_item.quantity
            cart_item.save()
        else:
            cart_item.delete()

        cart.total_bill = Decimal(sum(item.total_price for item in cart.items.all()))
        cart.save()

        # Update the total_bill in the booking as well
        booking.total_bill = cart.total_bill
        booking.save()

        cart_items = cart.items.all()
        items_data = [
            {
                "item_name": cart_item.menu_item.item_name,
                "quantity": cart_item.quantity
            }
            for cart_item in cart_items
        ]

        return Response({
            "message": "Item quantity updated or removed from cart successfully.",
            "cart": {
                "cart_id": cart.cart_id,
                "total_bill": cart.total_bill,
                "items": items_data
            }
        })


class GenerateBillView(APIView):
    def post(self, request, *args, **kwargs):
        cart_id = request.data.get('cart_id')

        try:
            cart = Cart.objects.get(cart_id=cart_id)
        except Cart.DoesNotExist:
            raise NotFound({"message": "Cart not found."})

        if cart.total_bill == 0:
            return Response({"message": "Failed to generate bill.", "errors": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": "Bill generated successfully.",
            "total_bill": cart.total_bill
        })

class EndBookingView(APIView):
    def post(self, request, *args, **kwargs):
        booking_id = request.data.get('booking_id')

        try:
            booking = Booking.objects.get(booking_id=booking_id)
        except Booking.DoesNotExist:
            raise NotFound({"message": "Booking not found."})

        booking.table.is_occupied = False
        booking.is_ongoing = False
        booking.table.save()
        booking.save()

        return Response({
            "message": "Booking ended successfully.",
            "booking": {
                "booking_id": booking.booking_id,
                "table_number": booking.table.table_number,
                "venue_name": booking.venue.name,
                "is_occupied": booking.table.is_occupied,
                "total_bill": booking.total_bill
            }
        })

class VenueMenuView(APIView):
    def get(self, request, venue_id, *args, **kwargs):
        try:
            venue = Venue.objects.get(venue_id=venue_id)
        except Venue.DoesNotExist:
            raise NotFound({"message": "Venue not found."})

        menu_items = Menu.objects.filter(venue=venue)
        
        if not menu_items:
            return Response({"message": "No menu items found for this venue."})

        menu_data = [
            {
                "menu_item_id": item.menu_item_id,
                "item_name": item.item_name,
                "price": item.price,
                "is_veg": item.is_veg,
                "tag": item.tag
            }
            for item in menu_items
        ]

        return Response({
            "message": "Menu fetched successfully.",
            "Venue": venue.name,
            "menu": menu_data
        })
    
class GetCurrentBookingDetailsView(APIView):
    def post(self, request, *args, **kwargs):
        booking_id = request.data.get('booking_id')

        try:
            booking = Booking.objects.get(booking_id=booking_id)
        except Booking.DoesNotExist:
            raise NotFound({"message": "Booking not found."})
        
        return Response({
            "message": "Booking details fetched successfully.",
            "booking": {
                "booking_id": booking.booking_id,
                "table_number": booking.table.table_number,
                "venue_name": booking.venue.name,
                "users" : [{"user_id": u.id, "name": u.name} for u in booking.users.all()],
                "waiter": {
                    "waiter_id": booking.waiter.waiter_id,
                    "name": booking.waiter.name
                } if booking.waiter else None,
                "is_occupied": booking.table.is_occupied,
                "is_ongoing": booking.is_ongoing,
                "total_bill": booking.total_bill
            }
        })