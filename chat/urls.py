from django.urls import path
from .views import *

urlpatterns = [
    path('private-chat/', PrivateChatView.as_view(), name='private-chat'),
    path('active-users/<int:res_id>/', ActiveChatUsersView.as_view(), name='active-chat-users'),
    path('mark-inactive/', MarkUserInactiveView.as_view(), name='mark-user-inactive'),
]