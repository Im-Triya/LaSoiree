from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from rest_framework import status
from decimal import Decimal
from django.contrib.auth import get_user_model
from partner.models import Venue, Table, Menu
from authentication.models import Waiter, Owner, Manager
from .models import Booking, Cart, CartItem, Presence
from geopy.distance import geodesic
import uuid
from django.db.models import Sum
from django.utils import timezone
import math
from datetime import datetime, timedelta
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError


def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(d_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c / 1000  # Convert to kilometers

class FetchVenuesView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            # Check user type from JWT payload
            user_type = request.auth.payload.get('user_type')
            if user_type != 'customuser':
                raise PermissionDenied({"message": "Only custom users can access this endpoint."})

            # Get user from JWT user_id
            user_id = request.auth.payload.get('user_id')
            if not user_id:
                raise NotFound({"message": "User ID not found in token."})

            user = get_user_model().objects.get(id=user_id)
            venues = Venue.objects.all()

            def get_geo(venue):
                """Helper function to safely extract latitude & longitude."""
                venue_geo = venue.geo_location or {}
                return (
                    venue_geo.get("latitude"),  # None is acceptable now
                    venue_geo.get("longitude"),
                )

            # Initialize variables for location handling
            user_location = None
            user_has_location = False

            # Check if user's location permission is granted and has valid location
            if user.is_location_permission_granted:
                user_geo = user.location or {}
                user_lat = user_geo.get("latitude")
                user_lon = user_geo.get("longitude")

                if user_lat is not None and user_lon is not None:
                    user_location = (user_lat, user_lon)
                    user_has_location = True

            # Prepare venue data with distance calculation
            venue_data = []
            venues_with_location = []
            venues_without_location = []

            for venue in venues:
                venue_lat, venue_lon = get_geo(venue)
                venue_has_location = venue_lat is not None and venue_lon is not None
                
                distance = None
                if user_has_location and venue_has_location:
                    try:
                        distance = geodesic(user_location, (venue_lat, venue_lon)).kilometers
                    except ValueError as e:
                        # Handle potential geodesic calculation errors
                        distance = None

                venue_info = {
                    "venue_id": venue.venue_id,
                    "name": venue.name,
                    "city": venue.city,
                    "geo_location": {
                        "latitude": venue_lat,
                        "longitude": venue_lon,
                    },
                    "number_of_tables": venue.number_of_tables,
                    "venue_image": venue.venue_image.url if venue.venue_image else None,
                    "distance": distance,
                    "has_location": venue_has_location,
                }

                if venue_has_location:
                    venues_with_location.append(venue_info)
                else:
                    venues_without_location.append(venue_info)

            # Sort venues with location by distance if user has location
            if user_has_location:
                venues_with_location.sort(key=lambda x: x["distance"] if x["distance"] is not None else float('inf'))
            
            # Combine lists (venues with location first, then venues without)
            venue_data = venues_with_location + venues_without_location

            return Response({"venues": venue_data})

        except get_user_model().DoesNotExist:
            raise NotFound({"message": "User not found."})
        except Exception as e:
            # Generic error handler for unexpected errors
            return Response(
                {"message": "An error occurred while fetching venues.", "error": str(e)},
                status=500
            )

class BookingTableView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            # Validate user type from JWT payload
            user_type = request.auth.payload.get('user_type')
            if user_type != 'customuser':
                raise PermissionDenied(
                    {"message": "Only custom users can book tables.", "code": "user_type_invalid"}
                )

            # Get user_id from JWT payload
            user_id = request.auth.payload.get('user_id')
            if not user_id:
                raise ValidationError(
                    {"message": "User ID not found in token.", "code": "missing_user_id"}
                )

            # Get QR code from request data
            qr_code = request.data.get('qr_code')
            if not qr_code:
                raise ValidationError(
                    {"message": "QR code is required.", "code": "missing_qr_code"},
                    code=status.HTTP_400_BAD_REQUEST
                )

            # Get user object
            try:
                user = get_user_model().objects.get(id=user_id)
            except get_user_model().DoesNotExist:
                raise NotFound(
                    {"message": "User not found.", "code": "user_not_found"}
                )

            # Parse QR code and get venue/table
            try:
                venue_id, table_no = qr_code.split("::")
                venue = Venue.objects.get(venue_id=venue_id)
                table = Table.objects.get(qr_code=qr_code)
            except ValueError:
                raise ValidationError(
                    {"message": "Invalid QR code format.", "code": "invalid_qr_format"},
                    code=status.HTTP_400_BAD_REQUEST
                )
            except Venue.DoesNotExist:
                raise NotFound(
                    {"message": "Venue not found.", "code": "venue_not_found"}
                )
            except Table.DoesNotExist:
                raise NotFound(
                    {"message": "Table not found.", "code": "table_not_found"}
                )

            # Check if table is already occupied
            if table.is_occupied:
                raise ValidationError(
                    {
                        "message": "Table is already occupied.", 
                        "code": "table_occupied",
                        "table_number": table.table_number,
                        "venue_name": venue.name
                    },
                    code=status.HTTP_409_CONFLICT
                )

            # Create booking
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

            # Update table status
            table.is_occupied = True
            table.save()

            # Prepare response data
            users_data = [{
                "user_id": u.id, 
                "name": u.name,
                "email": u.email
            } for u in booking.users.all()]

            return Response({
                "message": "Table booked successfully.",
                "code": "booking_success",
                "booking_id": str(booking.booking_id),
                "table": {
                    "venue_id": venue.venue_id,
                    "venue_name": venue.name,
                    "table_id": table.qr_code,
                    "table_number": table.table_number,
                    "is_occupied": table.is_occupied,
                    "qr_code": table.qr_code
                },
                "users": users_data,
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            # Handle unexpected errors
            return Response(
                {
                    "message": "An error occurred while processing your request.",
                    "error": str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class JoinTableView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            # Validate user type from JWT payload
            user_type = request.auth.payload.get('user_type')
            if user_type != 'customuser':
                raise PermissionDenied(
                    {"message": "Only custom users can join tables.", "code": "invalid_user_type"}
                )

            # Get user_id from JWT payload
            user_id = request.auth.payload.get('user_id')
            if not user_id:
                raise ValidationError(
                    {"message": "User ID not found in token.", "code": "missing_user_id"},
                    code=status.HTTP_400_BAD_REQUEST
                )

            # Get QR code from request data
            qr_code = request.data.get('qr_code')
            if not qr_code:
                raise ValidationError(
                    {"message": "QR code is required.", "code": "missing_qr_code"},
                    code=status.HTTP_400_BAD_REQUEST
                )

            # Get user object
            try:
                user = get_user_model().objects.get(id=user_id)
            except get_user_model().DoesNotExist:
                raise NotFound(
                    {"message": "User not found.", "code": "user_not_found"}
                )

            # Parse QR code and get venue/table
            try:
                venue_id, table_no = qr_code.split("::")
                venue = Venue.objects.get(venue_id=venue_id)
                table = Table.objects.get(qr_code=qr_code)
            except ValueError:
                raise ValidationError(
                    {"message": "Invalid QR code format.", "code": "invalid_qr_format"},
                    code=status.HTTP_400_BAD_REQUEST
                )
            except Venue.DoesNotExist:
                raise NotFound(
                    {"message": "Venue not found.", "code": "venue_not_found"}
                )
            except Table.DoesNotExist:
                raise NotFound(
                    {"message": "Table not found.", "code": "table_not_found"}
                )

            # Check if table is occupied
            if not table.is_occupied:
                raise ValidationError(
                    {
                        "message": "Table is not currently occupied.", 
                        "code": "table_not_occupied",
                        "table_number": table.table_number,
                        "venue_name": venue.name
                    },
                    code=status.HTTP_400_BAD_REQUEST
                )

            # Get the active booking for this table
            try:
                booking = Booking.objects.get(venue=venue, table=table, is_ongoing=True)
            except Booking.DoesNotExist:
                raise NotFound(
                    {
                        "message": "No active booking found for this table.",
                        "code": "no_active_booking",
                        "table_number": table.table_number
                    }
                )

            # Add user to the booking
            if booking.users.filter(id=user.id).exists():
                raise ValidationError(
                    {
                        "message": "User already joined this table.",
                        "code": "user_already_joined",
                        "booking_id": str(booking.booking_id)
                    },
                    code=status.HTTP_409_CONFLICT
                )

            booking.users.add(user)
            booking.save()

            # Prepare response data
            users_data = [{
                "user_id": u.id,
                "name": u.name,
                "email": u.email
            } for u in booking.users.all()]

            return Response({
                "message": "Successfully joined the table.",
                "code": "join_success",
                "booking_id": str(booking.booking_id),
                "venue": {
                    "venue_id": venue.venue_id,
                    "name": venue.name
                },
                "table": {
                    "table_id": table.qr_code,
                    "table_number": table.table_number,
                    "qr_code": table.qr_code
                },
                "users": users_data,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            # Handle unexpected errors
            return Response(
                {
                    "message": "An error occurred while processing your request.",
                    "error": str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class SendWaiterNotificationView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            # Validate user type from JWT payload
            user_type = request.auth.payload.get('user_type')
            if user_type != 'customuser':
                raise PermissionDenied(
                    {"message": "Only customers can request waiter notifications.", 
                     "code": "invalid_user_type"}
                )

            # Get user_id from JWT payload
            user_id = request.auth.payload.get('user_id')
            if not user_id:
                raise ValidationError(
                    {"message": "User ID not found in token.", 
                     "code": "missing_user_id"},
                    code=status.HTTP_400_BAD_REQUEST
                )

            # Validate booking_id in request data
            booking_id = request.data.get('booking_id')
            if not booking_id:
                raise ValidationError(
                    {"message": "booking_id is required.",
                     "code": "missing_booking_id"},
                    code=status.HTTP_400_BAD_REQUEST
                )

            # Get booking object
            try:
                booking = Booking.objects.get(booking_id=booking_id)
            except Booking.DoesNotExist:
                raise NotFound(
                    {"message": "Booking not found.", 
                     "code": "booking_not_found"}
                )

            # Verify the requesting user is part of the booking
            if not booking.users.filter(id=user_id).exists():
                raise PermissionDenied(
                    {"message": "You are not part of this booking.",
                     "code": "not_booking_member",
                     "booking_id": str(booking_id)}
                )

            # Get waiters assigned to the booking's venue
            waiters = Waiter.objects.filter(venue=booking.venue)
            
            # If booking already has a waiter assigned, only notify that specific waiter
            if booking.waiter:
                waiters = waiters.filter(user=booking.waiter.user)

            if not waiters.exists():
                raise ValidationError(
                    {"message": "No waiters available for this booking.",
                     "code": "no_waiters_available"},
                    code=status.HTTP_400_BAD_REQUEST
                )

            # To do : Implement actual notification system
            # For now, return success with relevant details
            return Response({
                "message": "Waiter notification sent successfully.",
                "code": "notification_sent",
                "booking_id": str(booking.booking_id),
                "venue": {
                    "venue_id": str(booking.venue.venue_id),
                    "name": booking.venue.name
                },
                "table_number": booking.table.table_number,
                "waiters_notified": [{
                    "waiter_id": str(w.user_id),
                    "name": w.user.name
                } for w in waiters],
                "is_specific_waiter": booking.waiter is not None
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"message": "An error occurred while sending waiter notification.",
                 "code": "server_error",
                 "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class AcceptBookingView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            # Validate user type from JWT payload (should be waiter)
            user_type = request.auth.payload.get('user_type')
            if user_type != 'waiter':
                raise PermissionDenied(
                    {"message": "Only waiters can accept bookings.", "code": "invalid_user_type"}
                )

            # Get user_id from JWT payload
            user_id = request.auth.payload.get('user_id')
            if not user_id:
                raise ValidationError(
                    {"message": "User ID not found in token.", "code": "missing_user_id"},
                    code=status.HTTP_400_BAD_REQUEST
                )

            # Get booking_id from request data
            booking_id = request.data.get('booking_id')
            if not booking_id:
                raise ValidationError(
                    {"message": "Booking ID is required.", "code": "missing_booking_id"},
                    code=status.HTTP_400_BAD_REQUEST
                )

            # Get booking object
            try:
                booking = Booking.objects.get(booking_id=booking_id)
            except Booking.DoesNotExist:
                raise NotFound(
                    {"message": "Booking not found.", "code": "booking_not_found"}
                )

            # Get waiter object (using user_id from JWT)
            try:
                waiter = Waiter.objects.get(user_id=user_id, venue=booking.venue)
            except Waiter.DoesNotExist:
                raise NotFound(
                    {
                        "message": "Waiter not found or not assigned to this venue.",
                        "code": "waiter_not_found",
                        "venue_id": str(booking.venue.venue_id)
                    }
                )

            # Check if booking already has a waiter
            if booking.waiter:
                raise ValidationError(
                    {
                        "message": "Booking already assigned to another waiter.",
                        "code": "booking_already_assigned",
                        "current_waiter": {
                            "waiter_id": str(booking.waiter.user_id),
                            "name": booking.waiter.user.name
                        }
                    },
                    code=status.HTTP_409_CONFLICT
                )

            # Assign waiter to booking
            booking.waiter = waiter
            booking.save()

            return Response({
                "message": "Booking accepted successfully.",
                "code": "booking_accepted",
                "booking": {
                    "booking_id": str(booking.booking_id),
                    "table": {
                        "table_id": str(booking.table.qr_code),
                        "table_number": booking.table.table_number
                    },
                    "venue": {
                        "venue_id": str(booking.venue.venue_id),
                        "name": booking.venue.name
                    },
                    "waiter": {
                        "waiter_id": str(waiter.user_id),
                        "name": waiter.user.name,
                        "email": waiter.user.email
                    },
                    "users": [{
                        "user_id": str(u.id),
                        "name": u.name,
                        "email": u.email
                    } for u in booking.users.all()],
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {
                    "message": "An error occurred while accepting the booking.",
                    "code": "server_error",
                    "error": str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class AddItemToCartView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            # Validate user type from JWT payload
            user_type = request.auth.payload.get('user_type')
            if user_type not in ['customuser', 'waiter']:
                raise PermissionDenied(
                    {"message": "Only customers or waiters can generate bills.", 
                     "code": "invalid_user_type"}
                )

            # Get user from JWT
            user_id = request.auth.payload.get('user_id')
            if not user_id:
                raise ValidationError(
                    {"message": "User ID not found in token.", 
                     "code": "missing_user_id"},
                    code=status.HTTP_400_BAD_REQUEST
                )

            # Validate request data
            booking_id = request.data.get('booking_id')
            menu_item_id = request.data.get('menu_item_id')
            quantity = request.data.get('quantity', 1)  # Default to 1 if not specified

            if not all([booking_id, menu_item_id]):
                raise ValidationError(
                    {"message": "Both booking_id and menu_item_id are required.",
                     "code": "missing_required_fields"},
                    code=status.HTTP_400_BAD_REQUEST
                )

            try:
                quantity = int(quantity)
                if quantity <= 0:
                    raise ValueError
            except ValueError:
                raise ValidationError(
                    {"message": "Quantity must be a positive integer.",
                     "code": "invalid_quantity"},
                    code=status.HTTP_400_BAD_REQUEST
                )

            # Get booking and verify user belongs to it
            try:
                booking = Booking.objects.get(booking_id=booking_id)

                # MOVED THIS CHECK AFTER WE GET THE BOOKING OBJECT
                if booking.is_ongoing == False:
                    raise ValidationError(
                        {"message": "Booking has ended.",
                         "code": "booking_not_ongoing"},
                        code=status.HTTP_400_BAD_REQUEST
                    )

                if user_type == 'customuser':
                    if not booking.users.filter(id=user_id).exists():
                        raise PermissionDenied(
                            {"message": "User not part of this booking.",
                             "code": "not_booking_member"}
                        )
                elif user_type == 'waiter':
                    if not booking.waiter or str(booking.waiter.user_id) != user_id:
                        raise PermissionDenied(
                            {"message": "Waiter not assigned to this booking.",
                             "code": "not_assigned_waiter"}
                        )
            except Booking.DoesNotExist:
                raise NotFound(
                    {"message": "Booking not found.",
                     "code": "booking_not_found"}
                )

            # Rest of your code remains the same...
            # Get menu item
            try:
                menu_item = Menu.objects.get(menu_item_id=menu_item_id)
            except Menu.DoesNotExist:
                raise NotFound(
                    {"message": "Menu item not found.",
                     "code": "menu_item_not_found"}
                )

            # Create or update cart
            cart, created = Cart.objects.get_or_create(booking=booking)
            cart_item, item_created = CartItem.objects.get_or_create(
                cart=cart, 
                menu_item=menu_item,
                defaults={
                    "quantity": quantity,
                    "total_price": menu_item.price * quantity
                }
            )

            if not item_created:
                cart_item.quantity += quantity
                cart_item.total_price = menu_item.price * cart_item.quantity
                cart_item.save()

            # Update cart and booking totals
            cart.total_bill = sum(item.total_price for item in cart.items.all())
            cart.save()

            booking.total_bill = cart.total_bill
            booking.save()

            # Prepare response
            cart_items = cart.items.all()
            items_data = [
                {
                    "item_id": str(item.menu_item.menu_item_id),
                    "item_name": item.menu_item.item_name,
                    "quantity": item.quantity,
                    "unit_price": str(item.menu_item.price),
                    "total_price": str(item.total_price)
                }
                for item in cart_items
            ]

            return Response({
                "message": "Item added to cart successfully.",
                "code": "item_added",
                "cart": {
                    "cart_id": str(cart.cart_id),
                    "total_bill": str(cart.total_bill),
                    "items": items_data,
                    "booking_id": str(booking_id)
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"message": "An error occurred while adding item to cart.",
                 "code": "server_error",
                 "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, *args, **kwargs):
        try:
            # Validate user type from JWT payload
            user_type = request.auth.payload.get('user_type')
            if user_type not in ['customuser', 'waiter']:
                raise PermissionDenied(
                    {"message": "Only customers or waiters can generate bills.", 
                     "code": "invalid_user_type"}
                )
    
            # Get user from JWT
            user_id = request.auth.payload.get('user_id')
            if not user_id:
                raise ValidationError(
                    {"message": "User ID not found in token.", 
                     "code": "missing_user_id"},
                    code=status.HTTP_400_BAD_REQUEST
                )
    
            # Validate request data
            booking_id = request.data.get('booking_id')
            menu_item_id = request.data.get('menu_item_id')
    
            if not all([booking_id, menu_item_id]):
                raise ValidationError(
                    {"message": "Both booking_id and menu_item_id are required.",
                     "code": "missing_required_fields"},
                    code=status.HTTP_400_BAD_REQUEST
                )
    
            # Get booking and verify user belongs to it
            try:
                booking = Booking.objects.get(booking_id=booking_id)
                
                # MOVED THIS CHECK AFTER WE GET THE BOOKING OBJECT
                if booking.is_ongoing == False:
                    raise ValidationError(
                        {"message": "Booking has ended.",
                         "code": "booking_not_ongoing"},
                        code=status.HTTP_400_BAD_REQUEST
                    )
                    
                if user_type == 'customuser':
                    if not booking.users.filter(id=user_id).exists():
                        raise PermissionDenied(
                            {"message": "User not part of this booking.",
                             "code": "not_booking_member"}
                        )
                elif user_type == 'waiter':
                    if not booking.waiter or str(booking.waiter.user_id) != user_id:
                        raise PermissionDenied(
                            {"message": "Waiter not assigned to this booking.",
                             "code": "not_assigned_waiter"}
                        )
            except Booking.DoesNotExist:
                raise NotFound(
                    {"message": "Booking not found.",
                     "code": "booking_not_found"}
                )
    
            # Get cart and cart item
            try:
                cart = Cart.objects.get(booking=booking)
                cart_item = CartItem.objects.get(cart=cart, menu_item_id=menu_item_id)
            except Cart.DoesNotExist:
                raise NotFound(
                    {"message": "Cart not found for this booking.",
                     "code": "cart_not_found"}
                )
            except CartItem.DoesNotExist:
                raise NotFound(
                    {"message": "Item not found in cart.",
                     "code": "item_not_in_cart"}
                )
    
            # Update or remove item
            if cart_item.quantity > 1:
                cart_item.quantity -= 1
                cart_item.total_price = cart_item.menu_item.price * cart_item.quantity
                cart_item.save()
            else:
                cart_item.delete()
    
            # Update cart and booking totals
            cart.total_bill = sum(item.total_price for item in cart.items.all())
            cart.save()
    
            booking.total_bill = cart.total_bill
            booking.save()
    
            # Prepare response
            cart_items = cart.items.all()
            items_data = [
                {
                    "item_id": str(item.menu_item.menu_item_id),
                    "item_name": item.menu_item.item_name,
                    "quantity": item.quantity,
                    "unit_price": str(item.menu_item.price),
                    "total_price": str(item.total_price)
                }
                for item in cart_items
            ]
    
            return Response({
                "message": "Item quantity updated or removed from cart successfully.",
                "code": "cart_updated",
                "cart": {
                    "cart_id": str(cart.cart_id),
                    "total_bill": str(cart.total_bill),
                    "items": items_data,
                    "booking_id": str(booking_id)
                }
            }, status=status.HTTP_200_OK)
    
        except Exception as e:
            return Response(
                {"message": "An error occurred while updating cart.",
                 "code": "server_error",
                 "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class GenerateBillView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            # Validate user type from JWT payload
            user_type = request.auth.payload.get('user_type')
            if user_type not in ['customuser', 'waiter']:
                raise PermissionDenied(
                    {"message": "Only customers or waiters can generate bills.", 
                     "code": "invalid_user_type"}
                )

            # Get user from JWT
            user_id = request.auth.payload.get('user_id')
            if not user_id:
                raise ValidationError(
                    {"message": "User ID not found in token.", 
                     "code": "missing_user_id"},
                    code=status.HTTP_400_BAD_REQUEST
                )

            # Validate request data
            booking_id = request.data.get('booking_id')
            

            if not booking_id :
                raise ValidationError(
                    {"message": "booking_id is required.",
                     "code": "missing_identifier"},
                    code=status.HTTP_400_BAD_REQUEST
                )

            # Get cart object
            cart = None
            if booking_id:
                try:
                    booking = Booking.objects.get(booking_id=booking_id)
                    # Verify user access
                    if user_type == 'customuser':
                        if not booking.users.filter(id=user_id).exists():
                            raise PermissionDenied(
                                {"message": "User not part of this booking.",
                                 "code": "not_booking_member"}
                            )
                    elif user_type == 'waiter':
                        if not booking.waiter or str(booking.waiter.user_id) != user_id:
                            raise PermissionDenied(
                                {"message": "Waiter not assigned to this booking.",
                                 "code": "not_assigned_waiter"}
                            )
                    
                    cart = Cart.objects.get(booking=booking)
                except Booking.DoesNotExist:
                    raise NotFound(
                        {"message": "Booking not found.",
                         "code": "booking_not_found"}
                    )
                except Cart.DoesNotExist:
                    raise NotFound(
                        {"message": "Cart not found for this booking.",
                         "code": "cart_not_found"}
                    )

            # Check if cart is empty
            if cart.total_bill <= 0:
                raise ValidationError(
                    {"message": "Cannot generate bill for empty cart.",
                     "code": "empty_cart"},
                    code=status.HTTP_400_BAD_REQUEST
                )

            # Get cart items for detailed response
            cart_items = cart.items.all()
            items_data = [
                {
                    "item_id": str(item.menu_item.menu_item_id),
                    "item_name": item.menu_item.item_name,
                    "quantity": item.quantity,
                    "unit_price": str(item.menu_item.price),
                    "total_price": str(item.total_price)
                }
                for item in cart_items
            ]

            return Response({
                "message": "Bill generated successfully.",
                "code": "bill_generated",
                "booking_id": str(cart.booking.booking_id),
                "cart_id": str(cart.cart_id),
                "total_bill": str(cart.total_bill),
                "items": items_data,
                "venue": {
                    "venue_id": str(cart.booking.venue.venue_id),
                    "name": cart.booking.venue.name
                },
                "table_number": cart.booking.table.table_number,
                "waiter": {
                    "waiter_id": str(cart.booking.waiter.user_id) if cart.booking.waiter else None,
                    "name": cart.booking.waiter.user.name if cart.booking.waiter else None
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"message": "An error occurred while generating bill.",
                 "code": "server_error",
                 "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class EndBookingView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            # Validate user type from JWT payload
            user_type = request.auth.payload.get('user_type')
            if user_type not in ['customuser', 'waiter']:
                raise PermissionDenied(
                    {"message": "Only customers or waiters can end bookings.", 
                     "code": "invalid_user_type"}
                )

            # Get user from JWT
            user_id = request.auth.payload.get('user_id')
            if not user_id:
                raise ValidationError(
                    {"message": "User ID not found in token.", 
                     "code": "missing_user_id"},
                    code=status.HTTP_400_BAD_REQUEST
                )

            # Validate request data
            booking_id = request.data.get('booking_id')
            if not booking_id:
                raise ValidationError(
                    {"message": "booking_id is required.",
                     "code": "missing_booking_id"},
                    code=status.HTTP_400_BAD_REQUEST
                )

            # Get booking object
            try:
                booking = Booking.objects.get(booking_id=booking_id)
            except Booking.DoesNotExist:
                raise NotFound(
                    {"message": "Booking not found.",
                     "code": "booking_not_found"}
                )

            # Verify user access
            if user_type == 'customuser':
                if not booking.users.filter(id=user_id).exists():
                    raise PermissionDenied(
                        {"message": "User not part of this booking.",
                         "code": "not_booking_member"}
                    )
            elif user_type == 'waiter':
                if not booking.waiter or str(booking.waiter.user_id) != user_id:
                    raise PermissionDenied(
                        {"message": "Waiter not assigned to this booking.",
                         "code": "not_assigned_waiter"}
                    )

            # End the booking
            booking.table.is_occupied = False
            booking.is_ongoing = False
            booking.table.save()
            booking.save()

            return Response({
                "message": "Booking ended successfully.",
                "code": "booking_ended",
                "booking": {
                    "booking_id": str(booking.booking_id),
                    "table_number": booking.table.table_number,
                    "venue": {
                        "venue_id": str(booking.venue.venue_id),
                        "name": booking.venue.name
                    },
                    "is_occupied": booking.table.is_occupied,
                    "total_bill": str(booking.total_bill),
                    
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"message": "An error occurred while ending booking.",
                 "code": "server_error",
                 "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class VenueMenuView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

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
                "item_description": item.item_description,
                "price": str(item.price),  
                "discount": str(item.discount) if item.discount is not None else None,
                "is_available": item.is_available,
                "is_veg": item.is_veg,
                "tag": item.tag,
                "tag_display": item.get_tag_display(), 
                "image": request.build_absolute_uri(item.image.url) if item.image else None
            }
            for item in menu_items
        ]

        return Response({
            "message": "Menu fetched successfully.",
            "Venue": venue.name,
            "menu": menu_data
        })
    
class GetCurrentBookingDetailsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            # Validate user type from JWT payload
            user_type = request.auth.payload.get('user_type')
            if user_type not in ['customuser', 'waiter']:
                raise PermissionDenied(
                    {"message": "Only customers or waiters can view booking details.", 
                     "code": "invalid_user_type"}
                )

            # Get user from JWT
            user_id = request.auth.payload.get('user_id')
            if not user_id:
                raise ValidationError(
                    {"message": "User ID not found in token.", 
                     "code": "missing_user_id"},
                    code=status.HTTP_400_BAD_REQUEST
                )

            # Validate request data
            booking_id = request.data.get('booking_id')
            if not booking_id:
                raise ValidationError(
                    {"message": "booking_id is required.",
                     "code": "missing_booking_id"},
                    code=status.HTTP_400_BAD_REQUEST
                )

            # Get booking object
            try:
                booking = Booking.objects.get(booking_id=booking_id)
            except Booking.DoesNotExist:
                raise NotFound(
                    {"message": "Booking not found.",
                     "code": "booking_not_found"}
                )

            # Verify user access
            if user_type == 'customuser':
                if not booking.users.filter(id=user_id).exists():
                    raise PermissionDenied(
                        {"message": "User not part of this booking.",
                         "code": "not_booking_member"}
                    )
            elif user_type == 'waiter':
                if not booking.waiter or str(booking.waiter.user_id) != user_id:
                    raise PermissionDenied(
                        {"message": "Waiter not assigned to this booking.",
                         "code": "not_assigned_waiter"}
                    )

            # Get cart details
            cart_details = None
            try:
                cart = Cart.objects.get(booking=booking)
                cart_items = CartItem.objects.filter(cart=cart).select_related('menu_item')
                
                cart_details = {
                    "cart_id": str(cart.cart_id),
                    "total_bill": str(cart.total_bill),
                    "items": [
                        {
                            "item_id": str(item.menu_item.menu_item_id),
                            "item_name": item.menu_item.item_name,
                            "quantity": item.quantity,
                            "unit_price": str(item.menu_item.price),
                            "total_price": str(item.total_price)
                        } 
                        for item in cart_items
                    ]
                }
            except Cart.DoesNotExist:
                cart_details = None

            return Response({
                "message": "Booking details fetched successfully.",
                "code": "booking_details_fetched",
                "booking": {
                    "booking_id": str(booking.booking_id),
                    "table_number": booking.table.table_number,
                    "venue": {
                        "venue_id": str(booking.venue.venue_id),
                        "name": booking.venue.name
                    },
                    "users": [{
                        "user_id": str(u.id),
                        "name": u.name,
                        "email": u.email
                    } for u in booking.users.all()],
                    "waiter": {
                        "waiter_id": str(booking.waiter.user_id),
                        "name": booking.waiter.user.name,
                        "email": booking.waiter.user.email
                    } if booking.waiter else None,
                    "is_occupied": booking.table.is_occupied,
                    "is_ongoing": booking.is_ongoing,
                    "total_bill": str(booking.total_bill),
                    "cart": cart_details
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"message": "An error occurred while fetching booking details.",
                 "code": "server_error",
                 "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class PresenceCheckInView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        # Check user type in JWT payload (assuming 'user_type' is in token payload)
        user_type = request.auth.get('user_type') if hasattr(request, 'auth') else None
        if user_type != 'customuser':
            return Response({"detail": "Only customuser can check in."}, status=status.HTTP_403_FORBIDDEN)
        
        venue_id = request.data.get('venue_id')
        if not venue_id:
            return Response({"detail": "venue_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        venue = get_object_or_404(Venue, venue_id=venue_id)

        # Check if Presence already exists with no time_out (active presence)
        presence_qs = Presence.objects.filter(user=user, venue=venue, time_out__isnull=True)
        if presence_qs.exists():
            return Response({"detail": "User already checked in at this venue."}, status=status.HTTP_400_BAD_REQUEST)

        presence = Presence.objects.create(user=user, venue=venue, time_in=timezone.now())
        return Response({"detail": f"Checked in at {venue.name}", "presence_id": str(presence.id)}, status=status.HTTP_201_CREATED)

class PresenceLocationCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        # Get current location from request
        current_location = request.data.get('location')
        if not current_location:
            return Response({"detail": "Current location is required."}, status=status.HTTP_400_BAD_REQUEST)
        lat = current_location.get('latitude')
        lon = current_location.get('longitude')
        if lat is None or lon is None:
            return Response({"detail": "Latitude and longitude are required."}, status=status.HTTP_400_BAD_REQUEST)
        
        presence = Presence.objects.filter(user=user).first()
        
        
        venue_location = presence.venue.geo_location or {}
        venue_lat = venue_location.get('latitude')
        venue_lon = venue_location.get('longitude')

        if venue_lat is None or venue_lon is None:
            return Response({"detail": "Venue location is not set properly."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        distance = haversine_distance(float(lat), float(lon), float(venue_lat), float(venue_lon))

        if distance > 50:  # meters
            # Remove Presence entry (mark time_out as now)
            presence.delete()
            return Response({"detail": "You are too far from the venue. Checked out automatically."}, status=status.HTTP_200_OK)

        return Response({"detail": "You are within the venue location.", "distance_meters": distance}, status=status.HTTP_200_OK)
    
class VenueOngoingBookingsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, venue_id, *args, **kwargs):
        try:
            # Validate user type from JWT payload
            user_type = request.auth.payload.get('user_type')
            if user_type not in ['owner', 'manager', 'waiter']:
                raise PermissionDenied(
                    {"message": "Only venue owners, managers or waiters can access this information.",
                     "code": "invalid_user_type"}
                )

            # Get user from JWT
            user_id = request.auth.payload.get('user_id')
            if not user_id:
                raise PermissionDenied(
                    {"message": "User ID not found in token.",
                     "code": "missing_user_id"}
                )

            # Get venue and verify user association
            try:
                venue = Venue.objects.get(venue_id=venue_id)
                
                # Verify user is associated with the venue
                if user_type == 'owner':
                    if not venue.owners.filter(user_id=user_id).exists():
                        raise PermissionDenied(
                            {"message": "User is not an owner of this venue.",
                             "code": "not_venue_owner"}
                        )
                elif user_type == 'manager':
                    if not venue.managers.filter(user_id=user_id).exists():
                        raise PermissionDenied(
                            {"message": "User is not a manager of this venue.",
                             "code": "not_venue_manager"}
                        )
                elif user_type == 'waiter':
                    if not venue.waiters.filter(user_id=user_id).exists():
                        raise PermissionDenied(
                            {"message": "User is not a waiter at this venue.",
                             "code": "not_venue_waiter"}
                        )
            except Venue.DoesNotExist:
                raise NotFound(
                    {"message": "Venue not found.",
                     "code": "venue_not_found"}
                )

            # Get all ongoing bookings for the venue
            ongoing_bookings = Booking.objects.filter(
                venue=venue,
                is_ongoing=True
            ).select_related('table', 'waiter__user', 'venue')

            bookings_data = []
            for booking in ongoing_bookings:
                bookings_data.append({
                    "booking_id": str(booking.booking_id),
                    "table_number": booking.table.table_number,
                    "total_bill": str(booking.total_bill),
                    "waiter": {
                        "waiter_id": str(booking.waiter.user_id) if booking.waiter else None,
                        "name": booking.waiter.user.name if booking.waiter else None,
                        "email": booking.waiter.user.email if booking.waiter else None
                    } if booking.waiter else None,
                    "users": [{
                        "user_id": str(user.id),
                        "name": user.name,
                        "email": user.email
                    } for user in booking.users.all()],
                    "qr_code": booking.qr_code
                })

            return Response({
                "message": "Ongoing bookings retrieved successfully.",
                "code": "ongoing_bookings_retrieved",
                "venue": {
                    "venue_id": str(venue.venue_id),
                    "name": venue.name
                },
                "ongoing_bookings_count": len(bookings_data),
                "ongoing_bookings": bookings_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"message": "An error occurred while fetching ongoing bookings.",
                 "code": "server_error",
                 "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class VenueStaffListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, venue_id, *args, **kwargs):
        try:
            # Validate user type from JWT payload
            user_type = request.auth.payload.get('user_type')
            if user_type not in ['owner', 'manager', 'waiter']:
                raise PermissionDenied(
                    {"message": "Only venue staff can access this information.",
                     "code": "invalid_user_type"}
                )

            # Get user from JWT
            user_id = request.auth.payload.get('user_id')
            if not user_id:
                raise PermissionDenied(
                    {"message": "User ID not found in token.",
                     "code": "missing_user_id"}
                )

            # Get venue and verify user association
            try:
                venue = Venue.objects.get(venue_id=venue_id)
                
                # Verify user is associated with the venue
                if user_type == 'owner':
                    if not venue.owners.filter(user_id=user_id).exists():
                        raise PermissionDenied(
                            {"message": "User is not an owner of this venue.",
                             "code": "not_venue_owner"}
                        )
                elif user_type == 'manager':
                    if not venue.managers.filter(user_id=user_id).exists():
                        raise PermissionDenied(
                            {"message": "User is not a manager of this venue.",
                             "code": "not_venue_manager"}
                        )
                elif user_type == 'waiter':
                    if not venue.waiters.filter(user_id=user_id).exists():
                        raise PermissionDenied(
                            {"message": "User is not a waiter at this venue.",
                             "code": "not_venue_waiter"}
                        )
            except Venue.DoesNotExist:
                raise NotFound(
                    {"message": "Venue not found.",
                     "code": "venue_not_found"}
                )

            # Get all staff members associated with the venue
            owners = venue.owners.all().select_related('user')
            managers = venue.managers.all().select_related('user')
            waiters = venue.waiters.all().select_related('user')

            def serialize_staff(staff_member, role):
                return {
                    "staff_id": str(staff_member.user_id),
                    "name": staff_member.user.name,
                    "email": staff_member.user.email,
                    "phone_number": staff_member.user.phone_number,
                    "role": role,
                }

            staff_data = (
                [serialize_staff(owner, "owner") for owner in owners] +
                [serialize_staff(manager, "manager") for manager in managers] +
                [serialize_staff(waiter, "waiter") for waiter in waiters]
            )

            return Response({
                "message": "Venue staff retrieved successfully.",
                "code": "venue_staff_retrieved",
                "venue": {
                    "venue_id": str(venue.venue_id),
                    "name": venue.name
                },
                "staff_count": len(staff_data),
                "staff": staff_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"message": "An error occurred while fetching venue staff.",
                 "code": "server_error",
                 "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class UserVenuesListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            # Validate user type from JWT payload
            user_type = request.auth.payload.get('user_type')
            if user_type not in ['owner', 'manager', 'waiter']:
                raise PermissionDenied(
                    {"message": "Only owners, managers or waiters can access this information.",
                     "code": "invalid_user_type"}
                )

            # Get user from JWT
            user_id = request.auth.payload.get('user_id')
            if not user_id:
                raise PermissionDenied(
                    {"message": "User ID not found in token.",
                     "code": "missing_user_id"}
                )

            # Get all venues associated with the user based on their role
            venues = []
            
            if user_type == 'owner':
                owner_venues = Venue.objects.filter(owners__user_id=user_id).distinct()
                for venue in owner_venues:
                    venues.append({
                        "venue_id": str(venue.venue_id),
                        "name": venue.name,
                        "city": venue.city,
                        "role": "owner"
                    })
                    
            elif user_type == 'manager':
                manager_venues = Venue.objects.filter(managers__user_id=user_id).distinct()
                for venue in manager_venues:
                    venues.append({
                        "venue_id": str(venue.venue_id),
                        "name": venue.name,
                        "city": venue.city,
                        "role": "manager"
                    })
                    
            elif user_type == 'waiter':
                waiter_venues = Venue.objects.filter(waiters__user_id=user_id).distinct()
                for venue in waiter_venues:
                    venues.append({
                        "venue_id": str(venue.venue_id),
                        "name": venue.name,
                        "city": venue.city,
                        "role": "waiter"
                    })

            return Response({
                "message": "User venues retrieved successfully.",
                "code": "user_venues_retrieved",
                "user": {
                    "user_id": user_id,
                    "name": request.user.name,
                    "role": user_type
                },
                "venues_count": len(venues),
                "venues": venues
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"message": "An error occurred while fetching user venues.",
                 "code": "server_error",
                 "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class DailySalesView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, venue_id, *args, **kwargs):
        try:
            # Validate user type
            user_type = request.auth.payload.get('user_type')
            if user_type not in ['owner', 'manager', 'waiter']:
                raise PermissionDenied(
                    {"message": "Only venue staff can access sales data.",
                     "code": "invalid_user_type"}
                )

            # Get user from JWT
            user_id = request.auth.payload.get('user_id')
            if not user_id:
                raise PermissionDenied(
                    {"message": "User ID not found in token.",
                     "code": "missing_user_id"}
                )

            # Verify venue exists and user is associated
            try:
                venue = Venue.objects.get(venue_id=venue_id)
                
                # Verify user association
                if user_type == 'owner':
                    if not venue.owners.filter(user_id=user_id).exists():
                        raise PermissionDenied(
                            {"message": "User is not an owner of this venue.",
                             "code": "not_venue_owner"}
                        )
                elif user_type == 'manager':
                    if not venue.managers.filter(user_id=user_id).exists():
                        raise PermissionDenied(
                            {"message": "User is not a manager of this venue.",
                             "code": "not_venue_manager"}
                        )
                elif user_type == 'waiter':
                    if not venue.waiters.filter(user_id=user_id).exists():
                        raise PermissionDenied(
                            {"message": "User is not a waiter at this venue.",
                             "code": "not_venue_waiter"}
                        )
            except Venue.DoesNotExist:
                raise NotFound(
                    {"message": "Venue not found.",
                     "code": "venue_not_found"}
                )

            # Calculate daily sales
            today = timezone.now().date()
            daily_sales = Booking.objects.filter(
                venue=venue,
                is_ongoing=False,
                date=today
            ).aggregate(total_sales=Sum('total_bill'))['total_sales'] or 0

            return Response({
                "message": "Daily sales retrieved successfully.",
                "code": "daily_sales_retrieved",
                "venue": {
                    "venue_id": str(venue.venue_id),
                    "name": venue.name
                },
                "date": today,
                "total_sales": float(daily_sales),
                "currency": "INR"
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"message": "An error occurred while fetching daily sales.",
                 "code": "server_error",
                 "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class MonthlySalesView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, venue_id, *args, **kwargs):
        try:
            # Validate user type
            user_type = request.auth.payload.get('user_type')
            if user_type not in ['owner', 'manager', 'waiter']:
                raise PermissionDenied(
                    {"message": "Only venue staff can access sales data.",
                     "code": "invalid_user_type"}
                )

            # Get user from JWT
            user_id = request.auth.payload.get('user_id')
            if not user_id:
                raise PermissionDenied(
                    {"message": "User ID not found in token.",
                     "code": "missing_user_id"}
                )

            # Verify venue exists and user is associated
            try:
                venue = Venue.objects.get(venue_id=venue_id)
                
                # Verify user association
                if user_type == 'owner':
                    if not venue.owners.filter(user_id=user_id).exists():
                        raise PermissionDenied(
                            {"message": "User is not an owner of this venue.",
                             "code": "not_venue_owner"}
                        )
                elif user_type == 'manager':
                    if not venue.managers.filter(user_id=user_id).exists():
                        raise PermissionDenied(
                            {"message": "User is not a manager of this venue.",
                             "code": "not_venue_manager"}
                        )
                elif user_type == 'waiter':
                    if not venue.waiters.filter(user_id=user_id).exists():
                        raise PermissionDenied(
                            {"message": "User is not a waiter at this venue.",
                             "code": "not_venue_waiter"}
                        )
            except Venue.DoesNotExist:
                raise NotFound(
                    {"message": "Venue not found.",
                     "code": "venue_not_found"}
                )

            # Calculate monthly sales with daily breakdown
            today = timezone.now()
            first_day = today.replace(day=1)
            last_day = (first_day + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            # Get all completed bookings for the month
            bookings = Booking.objects.filter(
                venue=venue,
                is_ongoing=False,
                date__gte=first_day,
                date__lte=last_day
            )
            
            # Calculate total monthly sales
            monthly_total = bookings.aggregate(
                total_sales=Sum('total_bill')
            )['total_sales'] or 0
            
            # Get daily breakdown
            daily_sales = bookings.values('date').annotate(
                daily_total=Sum('total_bill')
            ).order_by('date')
            
            # Format daily sales data
            daily_sales_data = []
            current_date = first_day
            while current_date <= last_day:
                daily_total = 0
                for sale in daily_sales:
                    if sale['date'] == current_date:
                        daily_total = sale['daily_total']
                        break
                
                daily_sales_data.append({
                    "date": current_date,
                    "total_sales": float(daily_total)
                })
                current_date += timedelta(days=1)

            return Response({
                "message": "Monthly sales retrieved successfully.",
                "code": "monthly_sales_retrieved",
                "venue": {
                    "venue_id": str(venue.venue_id),
                    "name": venue.name
                },
                "month": today.month,
                "year": today.year,
                "total_sales": float(monthly_total),
                "daily_sales": daily_sales_data,
                "currency": "INR"
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"message": "An error occurred while fetching monthly sales.",
                 "code": "server_error",
                 "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class CurrentVenuePresenceView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, venue_id, *args, **kwargs):
        try:
            # Get the venue
            venue = get_object_or_404(Venue, venue_id=venue_id)
            
            # Get all active presences (where time_out is null)
            active_presences = Presence.objects.filter(
                venue=venue,
                time_out__isnull=True
            ).select_related('user')
            
            # Count of currently present users
            present_users_count = active_presences.count()
            
            # Prepare user details
            present_users = []
            for presence in active_presences:
                user = presence.user
                present_users.append({
                    "user_id": str(user.id),
                    "name": user.name,
                    "email": user.email,
                    "phone_number": user.phone_number,
                    "check_in_time": presence.time_in,
                    "presence_id": str(presence.id)
                })
            
            return Response({
                "message": "Current venue presence retrieved successfully.",
                "venue": {
                    "venue_id": str(venue.venue_id),
                    "name": venue.name
                },
                "present_users_count": present_users_count,
                "present_users": present_users,
                "last_updated": timezone.now()
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"message": "An error occurred while fetching venue presence.",
                 "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )