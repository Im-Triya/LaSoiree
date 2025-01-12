from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import CustomUserSerializer
from .models import CustomUser
from .utils import send_otp_via_sms
from django.conf import settings
from twilio.rest import Client
from django.http import JsonResponse
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from django.contrib.auth import get_user_model

class RegisterAPIView(APIView):
    def post(self, request):
        serializer = CustomUserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OTPRequestAPIView(APIView):
    def post(self, request):
        phone_number = request.data.get("phone_number")

        if not phone_number:
            return Response({"error": "Phone number is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            send_otp_via_sms("+91" + phone_number)

            return Response({"message": "OTP sent successfully!"}, status=status.HTTP_200_OK)

        except CustomUser.DoesNotExist:
            return Response({"error": "User with this phone number does not exist."}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class OTPVerifyAPIView(APIView):
    def post(self, request):
        phone_number = request.data.get("phone_number")
        otp = request.data.get("otp")

        if not phone_number or not otp:
            return Response({"error": "Phone number and OTP are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            verification_check = client.verify \
                .v2 \
                .services(settings.TWILIO_SERVICE_SID) \
                .verification_checks \
                .create(to="+91" + phone_number, code=otp)

            if verification_check.status == "approved":
                return Response({"message": "OTP verified successfully!"}, status=status.HTTP_200_OK)
            else:
                return Response({"error": "OTP verification failed."}, status=status.HTTP_400_BAD_REQUEST)

        except CustomUser.DoesNotExist:
            return Response({"error": "User with this phone number does not exist."}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class DeleteUserAPIView(APIView):
    def delete(self, request):
        phone_number = request.data.get("phone_number")

        if not phone_number:
            return Response({"error": "Phone number is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Fetch the user by phone number
            user = CustomUser.objects.get(phone_number=phone_number)
            
            # Delete the user from the database
            user.delete()

            return Response({"message": f"User with phone number {phone_number} deleted successfully."}, status=status.HTTP_200_OK)
        
        except CustomUser.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class GoogleLoginView(APIView):
    def post(self, request, *args, **kwargs):
        token = request.data.get('token')

        if not token:
            return Response({"detail": "Token is missing"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Verify the token using Google's public keys
            id_info = id_token.verify_oauth2_token(
                token, 
                Request(), 
                audience=settings.GOOGLE_CLIENT_ID  # Replace with your actual Google client ID in settings
            )

            # Check if the token is valid and extract user info
            email = id_info.get('email')

            # Check if the user already exists or create a new user
            user, created = get_user_model().objects.get_or_create(email=email)

            # Optionally, you can set other user details like name, gender, etc.
            if created:
                user.name = id_info.get('name')
                user.save()

            # Now authenticate the user (you can create JWT or a session)
            # Here we just return user data, but you can return a JWT token instead
            return JsonResponse(CustomUserSerializer(user).data, status=status.HTTP_200_OK)

        except ValueError:
            # Token verification failed
            return Response({"detail": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)