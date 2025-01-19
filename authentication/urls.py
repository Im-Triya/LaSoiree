from django.urls import path
from .views import (
    SendOTPAPIView,
    VerifyPhoneAPIView,
    VerifyGoogleAPIView,
    CheckUserExistsAPIView,
    RegisterUserAPIView,
    UpdateLocationAPIView,
    UpdateProfileAPIView,
    LogoutUserAPIView,
    ValidateTokenAPIView,
    FetchUserDetailsAPIView,
)

urlpatterns = [
    path('send-otp', SendOTPAPIView.as_view(), name='send_otp'),
    path('verify-phone', VerifyPhoneAPIView.as_view(), name='verify_phone'),
    path('verify-google', VerifyGoogleAPIView.as_view(), name='verify_google'),
    path('check-user', CheckUserExistsAPIView.as_view(), name='check_user'),
    path('register', RegisterUserAPIView.as_view(), name='register_user'),
    path('update-location', UpdateLocationAPIView.as_view(), name='update_location'),
    path('update-profile', UpdateProfileAPIView.as_view(), name='update_profile'),
    path('logout', LogoutUserAPIView.as_view(), name='logout_user'),
    path('validate-token', ValidateTokenAPIView.as_view(), name='validate_token'),
    path('details', FetchUserDetailsAPIView.as_view(), name='fetch_user_details'),
]
