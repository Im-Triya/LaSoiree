from django.urls import path
from .views import RegisterAPIView, OTPRequestAPIView, OTPVerifyAPIView, DeleteUserAPIView

urlpatterns = [
    path('register/', RegisterAPIView.as_view(), name='register'),
    path('otp-request/', OTPRequestAPIView.as_view(), name='otp_request'),
    path('otp-verify/', OTPVerifyAPIView.as_view(), name='otp_verify'),
    path("delete-user/", DeleteUserAPIView.as_view(), name="delete_user"),
]

