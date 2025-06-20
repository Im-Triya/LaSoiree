import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Venue, Table, Menu, Offer
from authentication.models import CustomUser, Manager, Waiter, Owner
from .serializers import VenueSerializer, TableSerializer, MenuSerializer, OfferSerializer
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import PermissionDenied, NotFound

class UpdateVenueAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    

    def patch(self, request, *args, **kwargs):
        user_type = request.auth.payload.get('user_type')
        if user_type != "owner":
            raise PermissionDenied("Only owners can update venues.")

        venue_id = kwargs.get('venue_id')
        if not venue_id:
            return Response(
                {"message": "Venue ID is required in URL."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            venue = Venue.objects.get(venue_id=venue_id)
            
            if not venue.owners.filter(user__id=request.user.id).exists():
                raise PermissionDenied("You don't own this venue.")

            serializer = VenueSerializer(
                venue, 
                data=request.data, 
                partial=True,
                context={'request': request}  
            )
            
            if not serializer.is_valid():
                return Response(
                    {
                        "message": "Validation failed",
                        "errors": serializer.errors
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            updated_venue = serializer.save()

            if 'number_of_tables' in request.data:
                current_tables_count = venue.tables.count()  
                new_table_count = updated_venue.number_of_tables
                
                if new_table_count > current_tables_count:
                    for i in range(current_tables_count + 1, new_table_count + 1):
                        Table.objects.create(venue=venue, table_number=i)
                elif new_table_count < current_tables_count:
                    venue.tables.filter(table_number__gt=new_table_count).delete()

            return Response(
                {
                    "message": "Venue updated successfully",
                    "data": VenueSerializer(updated_venue).data
                },
                status=status.HTTP_200_OK
            )

        except Venue.DoesNotExist:
            raise NotFound("Venue not found")
        except Exception as e:
            return Response(
                {"message": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class VenueTablesAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_user_type(self, request):
        return request.auth.payload.get('user_type')

    def check_user_permission(self, user_type):
        allowed_types = ['owner', 'manager', 'waiter']
        return user_type in allowed_types

    def is_user_associated_with_venue(self, request, venue):
        user_id = request.auth.payload.get('user_id')
        
        if not user_id:
            return False
            
        try:
            custom_user = CustomUser.objects.get(id=user_id)
            user_type = self.get_user_type(request)
            
            if user_type == 'owner':
                # Check if the user is an owner of this venue
                return venue.owners.filter(user=custom_user).exists()
            
            elif user_type == 'manager':
                # Check if the user is a manager assigned to this venue
                return Manager.objects.filter(user=custom_user, venue=venue).exists()
                
            elif user_type == 'waiter':
                # Check if the user is a waiter assigned to this venue
                return Waiter.objects.filter(user=custom_user, venue=venue).exists()
                
            return False
        except CustomUser.DoesNotExist:
            return False

    def get(self, request, venue_id, *args, **kwargs):
        try:
            user_type = self.get_user_type(request)
            if not self.check_user_permission(user_type):
                return Response({
                    "message": "You don't have permission to access this resource."
                }, status=status.HTTP_403_FORBIDDEN)

            venue = Venue.objects.get(venue_id=venue_id)
            
            # Check if the user is associated with this venue
            if not self.is_user_associated_with_venue(request, venue):
                return Response({
                    "message": "You are not associated with this venue."
                }, status=status.HTTP_403_FORBIDDEN)

            tables = venue.tables.all()
            serializer = TableSerializer(tables, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Venue.DoesNotExist:
            return Response({
                "message": "Venue not found."
            }, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request, venue_id, *args, **kwargs):
        try:
            user_type = self.get_user_type(request)
            if not self.check_user_permission(user_type):
                return Response({
                    "message": "You don't have permission to perform this action."
                }, status=status.HTTP_403_FORBIDDEN)

            venue = Venue.objects.get(venue_id=venue_id)
            
            # Check if the user is associated with this venue
            if not self.is_user_associated_with_venue(request, venue):
                return Response({
                    "message": "You are not associated with this venue."
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Only allow owners and managers to add tables (not waiters)
            if user_type == 'waiter':
                return Response({
                    "message": "Waiters cannot add tables to venues."
                }, status=status.HTTP_403_FORBIDDEN)

            # Get the highest existing table number for this venue
            last_table = venue.tables.all().order_by('-table_number').first()
            new_table_number = 1 if last_table is None else last_table.table_number + 1

            table = Table.objects.create(
                venue=venue,
                table_number=new_table_number,
                is_occupied=False  # Default to unoccupied when creating new table
            )
            
            serializer = TableSerializer(table)
            return Response({
                "message": "Table added successfully.",
                "table_number": new_table_number,
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except Venue.DoesNotExist:
            return Response({
                "message": "Venue not found."
            }, status=status.HTTP_404_NOT_FOUND)

class AddMenuItemAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_user_type(self, request):
        return request.auth.payload.get('user_type')

    def check_user_permission(self, user_type):
        return user_type in ['owner', 'manager']

    def is_user_associated_with_venue(self, request, venue):
        user_id = request.auth.payload.get('user_id')
        
        if not user_id:
            return False
            
        try:
            custom_user = CustomUser.objects.get(id=user_id)
            
            if request.auth.payload.get('user_type') == 'owner':
                # Check if the user is an owner of this venue
                return venue.owners.filter(user=custom_user).exists()
            
            elif request.auth.payload.get('user_type') == 'manager':
                # Check if the user is a manager assigned to this venue
                return Manager.objects.filter(user=custom_user, venue=venue).exists()
                
            return False
        except CustomUser.DoesNotExist:
            return False

    def post(self, request, venue_id, *args, **kwargs):
        try:
            user_type = self.get_user_type(request)
            if not self.check_user_permission(user_type):
                return Response({
                    "message": "You don't have permission to add menu items."
                }, status=status.HTTP_403_FORBIDDEN)

            venue = Venue.objects.get(venue_id=venue_id)
            
            # Check if the user is associated with this venue
            if not self.is_user_associated_with_venue(request, venue):
                return Response({
                    "message": "You are not associated with this venue."
                }, status=status.HTTP_403_FORBIDDEN)

            data = request.data
            serializer = MenuSerializer(data={**data, "venue": venue.id})
            
            if serializer.is_valid():
                menu_item = serializer.save()
                return Response({
                    "message": "Menu item added successfully.",
                    "data": MenuSerializer(menu_item).data
                }, status=status.HTTP_201_CREATED)
            
            return Response({
                "message": "Menu item addition failed.",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Venue.DoesNotExist:
            return Response({
                "message": "Venue not found."
            }, status=status.HTTP_404_NOT_FOUND)
        
class UpdateMenuItemAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_user_type(self, request):
        return request.auth.payload.get('user_type')

    def check_user_permission(self, user_type):
        # Only allow owners and managers to update menu items
        return user_type in ['owner', 'manager']

    def is_user_associated_with_venue(self, request, venue):
        user_id = request.auth.payload.get('user_id')
        
        if not user_id:
            return False
            
        try:
            custom_user = CustomUser.objects.get(id=user_id)
            user_type = self.get_user_type(request)
            
            if user_type == 'owner':
                # Check if the user is an owner of this venue
                return venue.owners.filter(user=custom_user).exists()
            
            elif user_type == 'manager':
                # Check if the user is a manager assigned to this venue
                return Manager.objects.filter(user=custom_user, venue=venue).exists()
                
            return False
        except CustomUser.DoesNotExist:
            return False

    def patch(self, request, venue_id, *args, **kwargs):
        try:
            # Check user permissions
            user_type = self.get_user_type(request)
            if not self.check_user_permission(user_type):
                return Response({
                    "error": "You don't have permission to update menu items."
                }, status=status.HTTP_403_FORBIDDEN)

            # Validate required fields
            menu_item_id = request.data.get('menu_item_id')
            if not menu_item_id:
                return Response(
                    {"error": "menu_item_id is required in request body"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get venue and menu item
            venue = get_object_or_404(Venue, venue_id=venue_id)
            
            # Check if user is associated with this venue
            if not self.is_user_associated_with_venue(request, venue):
                return Response({
                    "error": "You are not associated with this venue."
                }, status=status.HTTP_403_FORBIDDEN)

            menu_item = get_object_or_404(Menu, menu_item_id=menu_item_id, venue=venue)

            # Update menu item
            serializer = MenuSerializer(
                instance=menu_item,
                data=request.data,
                partial=True  
            )
            serializer.is_valid(raise_exception=True)
            updated_item = serializer.save()

            return Response({
                "message": "Menu item updated successfully",
                "data": MenuSerializer(updated_item).data
            }, status=status.HTTP_200_OK)

        except ValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class UpdateTableOccupancyAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def put(self, request, qr_code, *args, **kwargs):
        try:
            table = Table.objects.get(qr_code=qr_code)
            is_occupied = request.data.get("is_occupied", None)
            
            if is_occupied is None:
                return Response({
                    "message": "is_occupied field is required."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            table.is_occupied = is_occupied
            table.save()
            
            return Response({
                "message": "Table occupancy updated successfully.",
                "table_number": table.table_number,
                "is_occupied": table.is_occupied
            }, status=status.HTTP_200_OK)
            
        except Table.DoesNotExist:
            return Response({
                "message": "Table not found."
            }, status=status.HTTP_404_NOT_FOUND)

class VenueTableStatsAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_user_type(self, request):
        return request.auth.payload.get('user_type')

    def check_user_permission(self, user_type):
        allowed_types = ['owner', 'manager', 'waiter']
        return user_type in allowed_types

    def is_user_associated_with_venue(self, request, venue):
        user_id = request.auth.payload.get('user_id')
        
        if not user_id:
            return False
            
        try:
            custom_user = CustomUser.objects.get(id=user_id)
            user_type = self.get_user_type(request)
            
            if user_type == 'owner':
                return venue.owners.filter(user=custom_user).exists()
            elif user_type == 'manager':
                return Manager.objects.filter(user=custom_user, venue=venue).exists()
            elif user_type == 'waiter':
                return Waiter.objects.filter(user=custom_user, venue=venue).exists()
            return False
        except CustomUser.DoesNotExist:
            return False

    def get(self, request, venue_id, *args, **kwargs):
        try:
            # Check user permissions
            user_type = self.get_user_type(request)
            if not self.check_user_permission(user_type):
                return Response({
                    "error": "You don't have permission to access this resource."
                }, status=status.HTTP_403_FORBIDDEN)

            # Get venue
            venue = Venue.objects.get(venue_id=venue_id)
            
            # Check venue association
            if not self.is_user_associated_with_venue(request, venue):
                return Response({
                    "error": "You are not associated with this venue."
                }, status=status.HTTP_403_FORBIDDEN)

            # Calculate stats
            tables = venue.tables.all()
            total_tables = tables.count()
            occupied_tables = tables.filter(is_occupied=True).count()
            empty_tables = total_tables - occupied_tables
            
            return Response({
                "venue_id": venue_id,
                "venue_name": venue.name,
                "total_tables": total_tables,
                "occupied_tables": occupied_tables,
                "total_capacity": venue.total_capacity,
                "empty_tables": empty_tables,
                "current_strength": venue.current_strength
            }, status=status.HTTP_200_OK)
            
        except Venue.DoesNotExist:
            return Response(
                {"error": f"Venue with ID {venue_id} not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class VenueActiveOffersAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_user_type(self, request):
        return request.auth.payload.get('user_type')

    def check_user_permission(self, user_type):
        allowed_types = ['owner', 'manager', 'waiter']
        return user_type in allowed_types

    def is_user_associated_with_venue(self, request, venue):
        user_id = request.auth.payload.get('user_id')
        
        if not user_id:
            return False
            
        try:
            custom_user = CustomUser.objects.get(id=user_id)
            user_type = self.get_user_type(request)
            
            if user_type == 'owner':
                return venue.owners.filter(user=custom_user).exists()
            elif user_type == 'manager':
                return Manager.objects.filter(user=custom_user, venue=venue).exists()
            elif user_type == 'waiter':
                return Waiter.objects.filter(user=custom_user, venue=venue).exists()
            return False
        except CustomUser.DoesNotExist:
            return False

    def get(self, request, venue_id, *args, **kwargs):
        try:
            # Check user permissions
            user_type = self.get_user_type(request)
            if not self.check_user_permission(user_type):
                return Response({
                    "error": "You don't have permission to access this resource."
                }, status=status.HTTP_403_FORBIDDEN)

            # Get venue
            venue = get_object_or_404(Venue, venue_id=venue_id)
            
            # Check venue association
            if not self.is_user_associated_with_venue(request, venue):
                return Response({
                    "error": "You are not associated with this venue."
                }, status=status.HTTP_403_FORBIDDEN)

            # Get active offers for this venue
            active_offers = Offer.objects.filter(
                venue=venue,
                is_active=True
            ).order_by('-start_date')
            
            # Serialize the offers
            serializer = OfferSerializer(active_offers, many=True)
            
            return Response({
                "venue_id": venue_id,
                "venue_name": venue.name,
                "active_offers_count": active_offers.count(),
                "offers": serializer.data,
                "message": f"Found {active_offers.count()} active offers for {venue.name}"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class CreateOfferAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_user_type(self, request):
        return request.auth.payload.get('user_type')

    def check_user_permission(self, user_type):
        # Only allow owners and managers to create offers
        return user_type in ['owner', 'manager']

    def is_user_associated_with_venue(self, request, venue):
        user_id = request.auth.payload.get('user_id')
        
        if not user_id:
            return False
            
        try:
            custom_user = CustomUser.objects.get(id=user_id)
            user_type = self.get_user_type(request)
            
            if user_type == 'owner':
                # Check if the user is an owner of this venue
                return venue.owners.filter(user=custom_user).exists()
            
            elif user_type == 'manager':
                # Check if the user is a manager assigned to this venue
                return Manager.objects.filter(user=custom_user, venue=venue).exists()
                
            return False
        except CustomUser.DoesNotExist:
            return False

    def post(self, request, venue_id, *args, **kwargs):
        try:
            # Check user permissions
            user_type = self.get_user_type(request)
            if not self.check_user_permission(user_type):
                return Response({
                    "error": "Only venue owners and managers can create offers"
                }, status=status.HTTP_403_FORBIDDEN)

            # Get venue and verify association
            venue = get_object_or_404(Venue, venue_id=venue_id)
            if not self.is_user_associated_with_venue(request, venue):
                return Response({
                    "error": "You are not associated with this venue"
                }, status=status.HTTP_403_FORBIDDEN)

            # Prepare offer data
            offer_data = {
                **request.data,
                'venue': venue.id,
                'is_active': True  
            }
            
            # Validate and create offer
            serializer = OfferSerializer(data=offer_data)
            serializer.is_valid(raise_exception=True)
            offer = serializer.save()

            return Response({
                "message": "Offer created successfully",
                "offer_id": str(offer.offer_id),
                "venue_id": venue_id,
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)

        except KeyError as e:
            return Response(
                {"error": f"Missing required field: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class DeactivateOfferAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_user_type(self, request):
        return request.auth.payload.get('user_type')

    def check_user_permission(self, user_type):
        # Only allow owners and managers to deactivate offers
        return user_type in ['owner', 'manager']

    def is_user_associated_with_venue(self, request, venue):
        user_id = request.auth.payload.get('user_id')
        
        if not user_id:
            return False
            
        try:
            custom_user = CustomUser.objects.get(id=user_id)
            user_type = self.get_user_type(request)
            
            if user_type == 'owner':
                # Check if the user is an owner of this venue
                return venue.owners.filter(user=custom_user).exists()
            
            elif user_type == 'manager':
                # Check if the user is a manager assigned to this venue
                return Manager.objects.filter(user=custom_user, venue=venue).exists()
                
            return False
        except CustomUser.DoesNotExist:
            return False

    def patch(self, request, venue_id, *args, **kwargs):
        try:
            # Check user permissions
            user_type = self.get_user_type(request)
            if not self.check_user_permission(user_type):
                return Response({
                    "error": "Only venue owners and managers can deactivate offers"
                }, status=status.HTTP_403_FORBIDDEN)

            # Get venue and verify association
            venue = get_object_or_404(Venue, venue_id=venue_id)
            if not self.is_user_associated_with_venue(request, venue):
                return Response({
                    "error": "You are not associated with this venue"
                }, status=status.HTTP_403_FORBIDDEN)

            # Get offer and verify it belongs to venue
            offer_id = request.data.get('offer_id')
            if not offer_id:
                return Response(
                    {"error": "offer_id is required in request body"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            offer = get_object_or_404(Offer, offer_id=offer_id, venue=venue)
            
            # Deactivate offer
            offer.is_active = False
            offer.save()
            
            serializer = OfferSerializer(offer)
            return Response({
                "message": "Offer deactivated successfully",
                "venue_id": venue_id,
                "data": serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class OwnerVenuesAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Check if user is an owner
        user_type = request.auth.payload.get('user_type')
        if user_type != 'owner':
            return Response(
                {'error': 'Only owners can access this endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get the owner instance for the current user
        try:
            owner = Owner.objects.get(user=request.user)
        except Owner.DoesNotExist:
            return Response(
                {'error': 'Owner profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get all venues associated with this owner
        venues = owner.venues.all()
        serializer = VenueSerializer(venues, many=True)
        
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class VenueQRCodesAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, venue_id):
        try:
            venue = Venue.objects.get(venue_id=venue_id)
        except Venue.DoesNotExist:
            return Response(
                {"error": f"Venue with ID {venue_id} not found", "received_venue_id": venue_id},
                status=status.HTTP_404_NOT_FOUND
            )

        # Debugging: Print the venue ID being searched
        print(f"Searching for venue: {venue_id}")

        # Build response data
        response_data = {
            "venue_info": {
                "id": venue.venue_id,
                "name": venue.name,
                "qr_code_url": request.build_absolute_uri(venue.qr_code.url) if venue.qr_code else None
            },
            "tables": [
                {
                    "table_number": table.table_number,
                    "qr_code_url": request.build_absolute_uri(table.qr_image.url) if table.qr_image else None,
                    "is_occupied": table.is_occupied,
                    "qr_data": table.qr_code  # The VEN001::1 format
                }
                for table in venue.tables.all().order_by('table_number')
            ]
        }

        return Response(response_data)