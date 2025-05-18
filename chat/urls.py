from django.urls import path
from . import views

urlpatterns = [
    path('rooms/', views.ChatRoomListCreateView.as_view(), name='dm-list-create'),
    path('rooms/<uuid:room_id>/messages/', views.MessageListView.as_view(), name='message-list'),
    path('rooms/<uuid:room_id>/mark-read/', views.MarkMessagesAsReadView.as_view(), name='mark-read'),
]