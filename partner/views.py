import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Venue, Table, Menu, Offer
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
    def get(self, request, venue_id, *args, **kwargs):
        try:
            venue = Venue.objects.get(venue_id=venue_id)
            tables = venue.tables.all()
            serializer = TableSerializer(tables, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Venue.DoesNotExist:
            return Response({
                "message": "Venue not found."
            }, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, venue_id, *args, **kwargs):
        try:
            venue = Venue.objects.get(venue_id=venue_id)
            table_number = request.data.get("table_number")
            is_occupied = request.data.get("is_occupied", False)

            if Table.objects.filter(venue=venue, table_number=table_number).exists():
                return Response({
                    "message": f"Table number {table_number} already exists for this venue."
                }, status=status.HTTP_400_BAD_REQUEST)

            table = Table.objects.create(
                venue=venue,
                table_number=table_number,
                is_occupied=is_occupied
            )
            serializer = TableSerializer(table)
            return Response({
                "message": "Table added successfully.",
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)
        except Venue.DoesNotExist:
            return Response({
                "message": "Venue not found."
            }, status=status.HTTP_404_NOT_FOUND)

class AddMenuItemAPIView(APIView):
    def post(self, request, venue_id, *args, **kwargs):
        try:
            venue = Venue.objects.get(venue_id=venue_id)
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
    def patch(self, request, venue_id, *args, **kwargs):
        try:
            menu_item_id = request.data.get('menu_item_id')
            if not menu_item_id:
                return Response(
                    {"error": "menu_item_id is required in request body"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            venue = get_object_or_404(Venue, venue_id=venue_id)
            menu_item = get_object_or_404(Menu, menu_item_id=menu_item_id, venue=venue)

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
    def put(self, request, qr_code, *args, **kwargs):
        try:
            table = Table.objects.get(qr_code=qr_code)
            is_occupied = request.data.get("is_occupied", None)
            if is_occupied is not None:
                table.is_occupied = is_occupied
                table.save()
                return Response({
                    "message": "Table occupancy updated successfully."
                }, status=status.HTTP_200_OK)
            return Response({
                "message": "Invalid data provided."
            }, status=status.HTTP_400_BAD_REQUEST)
        except Table.DoesNotExist:
            return Response({
                "message": "Table not found."
            }, status=status.HTTP_404_NOT_FOUND)

class VenueTableStatsAPIView(APIView):
    def post(self, request):
        venue_id = request.data.get('venue_id')
        
        if not venue_id:
            return Response(
                {"error": "venue_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            venue = Venue.objects.get(venue_id=venue_id)
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
                "empty_tables": empty_tables
                
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
    def post(self, request):
       
        venue_id = request.data.get('venue_id')
        
        if not venue_id:
            return Response(
                {"error": "venue_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            venue = Venue.objects.get(venue_id=venue_id)
            
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
        
class CreateOfferAPIView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            venue = Venue.objects.get(venue_id=request.data['venue_id'])
            
            offer_data = {
                **request.data,
                'venue': venue.id,
                'is_active': True  
            }
            
            serializer = OfferSerializer(data=offer_data)
            serializer.is_valid(raise_exception=True)
            offer = serializer.save()

            return Response({
                "message": "Offer created successfully",
                "offer_id": str(offer.offer_id),
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)

        except Venue.DoesNotExist:
            return Response(
                {"error": "Venue not found"},
                status=status.HTTP_404_NOT_FOUND
            )
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
    def post(self, request):
        try:
            offer_id = request.data.get('offer_id')
            if not offer_id:
                return Response(
                    {"error": "offer_id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                offer = Offer.objects.get(offer_id=offer_id)
            except Offer.DoesNotExist:
                return Response(
                    {"error": "Offer not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            offer.is_active = False
            offer.save()
            
            serializer = OfferSerializer(offer)
            return Response({
                "message": "Offer deactivated successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )