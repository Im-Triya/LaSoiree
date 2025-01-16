from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Venue, Table
from .serializers import VenueSerializer, TableSerializer, MenuSerializer


class RegisterVenueAPIView(APIView):
    def post(self, request):
        serializer = VenueSerializer(data=request.data)
        if serializer.is_valid():
            venue = serializer.save()

            for i in range(1, venue.number_of_tables + 1):
                Table.objects.create(venue=venue, table_number=i)

            return Response(
                {
                    "message": "Venue registered successfully",
                    "venue_id": venue.venue_id,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VenueTablesAPIView(APIView):
    def get(self, request, venue_id):
        venue = get_object_or_404(Venue, venue_id=venue_id)

        tables = Table.objects.filter(venue=venue)
        serializer = TableSerializer(tables, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)


class AddMenuItemAPIView(APIView):
    def post(self, request, venue_id):
        venue = get_object_or_404(Venue, venue_id=venue_id)
        
        data = request.data.copy()
        data['venue'] = venue.id
        
        serializer = MenuSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Menu item added successfully!", "data": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)