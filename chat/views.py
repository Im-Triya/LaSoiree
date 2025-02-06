from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import models

from venueservices.models import RestaurantVisit
from .models import PrivateMessage
from .serializers import PrivateMessageSerializer

class PrivateChatView(APIView):
    def get(self, request):
        sender_id = request.query_params.get('sender_id')
        receiver_id = request.query_params.get('receiver_id')

        messages = PrivateMessage.objects.filter(
            (models.Q(sender_id=sender_id) & models.Q(receiver_id=receiver_id)) |
            (models.Q(sender_id=receiver_id) & models.Q(receiver_id=sender_id))
        ).order_by('timestamp')

        serializer = PrivateMessageSerializer(messages, many=True)
        return Response(serializer.data)
    
class ActiveChatUsersView(APIView):
    """
    Fetch the list of active users for chat in a specific restaurant.
    """
    def get(self, request, res_id):
        current_user = request.user
        active_users = RestaurantVisit.objects.filter(
            res_id=res_id,
            is_active=True,
            user__is_chat_allowed=True
        ).exclude(user=current_user)

        users_data = [
            {
                "user_id": visit.user.id,
                "username": visit.user.name
            }
            for visit in active_users
        ]

        return Response(users_data, status=status.HTTP_200_OK)
    
class MarkUserInactiveView(APIView):
    """
    Mark a user as inactive in a specific restaurant.
    """
    def post(self, request):
        data = request.data
        user_id = data.get('user_id')
        res_id = data.get('res_id')

        # Fetch the active visit for the user
        visit = RestaurantVisit.objects.filter(user_id=user_id, res_id=res_id, is_active=True).first()
        if not visit:
            return Response({"message": "No active visit found for the user."}, status=status.HTTP_400_BAD_REQUEST)

        # Mark the user as inactive
        visit.is_active = False
        visit.save()

        return Response({"message": "User marked as inactive."}, status=status.HTTP_200_OK)
