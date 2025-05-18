from django.shortcuts import render
from django.db import models

# Create your views here.
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .models import ChatRoom, Message
from .serializers import ChatRoomSerializer, MessageSerializer
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

User = get_user_model()


class ChatRoomListCreateView(generics.ListCreateAPIView):
    serializer_class = ChatRoomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return ChatRoom.objects.filter(
            models.Q(participant1=user) | models.Q(participant2=user)
        ).distinct()

    def perform_create(self, serializer):
        other_user_id = self.request.data.get('other_user')
        other_user = get_object_or_404(User, id=other_user_id)
        
        # Check if chat room already exists
        existing_room = ChatRoom.objects.filter(
            models.Q(participant1=self.request.user, participant2=other_user) |
            models.Q(participant1=other_user, participant2=self.request.user)
        ).first()
        
        if existing_room:
            return existing_room
            
        return serializer.save(
            participant1=self.request.user,
            participant2=other_user
        )

class MessageListView(generics.ListCreateAPIView):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        room_id = self.kwargs['room_id']
        user = self.request.user
        
        # Verify user is part of the chat room
        room = get_object_or_404(ChatRoom, id=room_id)
        if user not in [room.participant1, room.participant2]:
            return Message.objects.none()
            
        return Message.objects.filter(room=room)

    def perform_create(self, serializer):
        room_id = self.kwargs['room_id']
        room = get_object_or_404(ChatRoom, id=room_id)
        serializer.save(room=room, sender=self.request.user)

class MarkMessagesAsReadView(generics.UpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def update(self, request, *args, **kwargs):
        room_id = kwargs['room_id']
        user = request.user
        
        # Verify user is part of the chat room
        room = get_object_or_404(ChatRoom, id=room_id)
        if user not in [room.participant1, room.participant2]:
            return Response(status=status.HTTP_403_FORBIDDEN)
            
        # Mark all unread messages as read
        Message.objects.filter(
            room=room,
            read=False
        ).exclude(sender=user).update(read=True)
        
        return Response(status=status.HTTP_200_OK)