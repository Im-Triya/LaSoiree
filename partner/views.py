import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Venue, Table, Menu
from .serializers import VenueSerializer, TableSerializer, MenuSerializer

class RegisterVenueAPIView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = VenueSerializer(data=request.data)
        if serializer.is_valid():
            venue = serializer.save()

            for i in range(1, venue.number_of_tables + 1):
                Table.objects.create(venue=venue, table_number=i)
            
            return Response({
                "message": "Venue registered successfully.",
                "venue_id": venue.venue_id
            }, status=status.HTTP_201_CREATED)
        return Response({
            "message": "Venue registration failed.",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


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


class UpdateVenueAPIView(APIView):
    def put(self, request, venue_id, *args, **kwargs):
        try:
            venue = Venue.objects.get(venue_id=venue_id)
            original_number_of_tables = venue.number_of_tables
            new_number_of_tables = int(request.data.get("number_of_tables", original_number_of_tables))

            # Update the venue details using the serializer
            serializer = VenueSerializer(venue, data=request.data, partial=True)
            if serializer.is_valid():
                # Save the updated venue details
                serializer.save()

                # Create new tables if the number of tables has increased
                if new_number_of_tables > original_number_of_tables:
                    for table_number in range(original_number_of_tables + 1, new_number_of_tables + 1):
                        Table.objects.create(
                            venue=venue,
                            table_number=table_number,
                            is_occupied=False
                        )

                return Response({
                    "message": "Venue details updated successfully."
                }, status=status.HTTP_200_OK)

            return Response({
                "message": "Failed to update venue details.",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        except Venue.DoesNotExist:
            return Response({
                "message": "Venue not found."
            }, status=status.HTTP_404_NOT_FOUND)
