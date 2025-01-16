from datetime import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from partner.models import Table
from .models import TableReservation, Order
from partner.models import Menu
from .serializers import TableReservationSerializer, OrderSerializer

class BookTableAPIView(APIView):
    def post(self, request, qr_code):
        print(f"Received QR Code: {qr_code}")
        table = get_object_or_404(Table, qr_code=qr_code)
        print(f"Found Table: {table}")
        
        if table.is_occupied:
            return Response({"error": "This table is already occupied."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if the user is authenticated
        if request.user.is_anonymous:
            return Response({"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
        
        reservation = TableReservation.objects.create(user=request.user, table=table)
        table.is_occupied = True
        table.save()

        serializer = TableReservationSerializer(reservation)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    
class PlaceOrderAPIView(APIView):
    def post(self, request, reservation_id):
        reservation = get_object_or_404(TableReservation, id=reservation_id, user=request.user)
        
        menu_item_id = request.data.get('menu_item_id')
        quantity = request.data.get('quantity', 1)

        menu_item = get_object_or_404(Menu, id=menu_item_id)
        order = Order.objects.create(reservation=reservation, menu_item=menu_item, quantity=quantity)

        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class BillingAPIView(APIView):
    def post(self, request, reservation_id):
        reservation = get_object_or_404(TableReservation, id=reservation_id, user=request.user)

        orders = reservation.orders.all()
        total_bill = sum(order.menu_item.price * order.quantity for order in orders)

        order_serializer = OrderSerializer(orders, many=True)

        reservation.end_time = timezone.now()
        reservation.table.is_occupied = False
        reservation.table.save()
        reservation.save()

        return Response({
            "message": "Billing successful!",
            "total_bill": total_bill,
            "orders": order_serializer.data
        }, status=status.HTTP_200_OK)
