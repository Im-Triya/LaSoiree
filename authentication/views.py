from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import CustomUserSerializer, TokenSerializer
from .models import CustomUser, Tokens
# from .utils import send_otp_via_sms
from django.conf import settings
from twilio.rest import Client
# from django.http import JsonResponse
from google.auth.transport.requests import Request
from google.oauth2 import id_token
# from django.contrib.auth import get_user_model
from django.utils.timezone import now
import jwt

class SendOTPAPIView(APIView):
    def post(self, request):
        phone_number = request.data.get("phone_number")

        if not phone_number:
            return Response({"message": "Phone number is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.verify \
                .services(settings.TWILIO_SERVICE_SID) \
                .verifications \
                .create(to="+91" + phone_number, channel="sms")

            return Response({"message": "OTP sent successfully.", "phone_number": phone_number}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class VerifyPhoneAPIView(APIView):
    def post(self, request):
        phone_number = request.data.get("phone_number")
        otp = request.data.get("otp")

        if not phone_number or not otp:
            return Response({"message": "Phone number and OTP are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            verification_check = client.verify \
                .v2 \
                .services(settings.TWILIO_SERVICE_SID) \
                .verification_checks \
                .create(to="+91" + phone_number, code=otp)

            if verification_check.status == "approved":
                user, created = CustomUser.objects.get_or_create(phone_number=phone_number)
                user.is_verified = True
                user.last_login = now()
                user.save()

                token = jwt.encode({"user_id": str(user.id), "exp": now() + settings.JWT_EXPIRATION}, settings.SECRET_KEY, algorithm="HS256")
                Tokens.objects.create(user=user, token=token, expiry_date=now() + settings.JWT_EXPIRATION)

                return Response({"message": "Phone number verified successfully.", "is_verified": True, "token": token}, status=status.HTTP_200_OK)

            return Response({"message": "Invalid OTP.", "is_verified": False}, status=status.HTTP_400_BAD_REQUEST)

        except CustomUser.DoesNotExist:
            return Response({"message": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VerifyGoogleAPIView(APIView):
    def post(self, request):
        google_token = request.data.get("google_token")

        if not google_token:
            return Response({"message": "Google token is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            id_info = id_token.verify_oauth2_token(google_token, Request(), settings.GOOGLE_CLIENT_ID)
            email = id_info.get('email')
            name = id_info.get('name')

            user, created = CustomUser.objects.get_or_create(email=email)
            user.is_verified = True
            user.name = name
            user.last_login = now()
            user.save()

            token = jwt.encode({"user_id": str(user.id), "exp": now() + settings.JWT_EXPIRATION}, settings.SECRET_KEY, algorithm="HS256")
            Tokens.objects.create(user=user, token=token, expiry_date=now() + settings.JWT_EXPIRATION)

            return Response({"message": "Google account verified successfully.", "is_verified": True, "token": token}, status=status.HTTP_200_OK)

        except ValueError:
            return Response({"message": "Google account verification failed."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CheckUserExistsAPIView(APIView):
    def post(self, request):
        email = request.data.get("email")
        phone_number = request.data.get("phone_number")

        if not email and not phone_number:
            return Response({"message": "Email or phone number is required."}, status=status.HTTP_400_BAD_REQUEST)

        user = CustomUser.objects.filter(email=email).first() or CustomUser.objects.filter(phone_number=phone_number).first()

        if user:
            return Response(
                {
                    "message": "User already exists.",
                    "user_id": str(user.id),  # Now 'user' is an object, so 'id' exists
                    "email_exists": bool(user.email),
                    "phone_number_exists": bool(user.phone_number),
                },
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"message": "User does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )

class RegisterUserAPIView(APIView):
    def post(self, request):
        serializer = CustomUserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            token = jwt.encode({"user_id": str(user.id), "exp": now() + settings.JWT_EXPIRATION}, settings.SECRET_KEY, algorithm="HS256")
            Tokens.objects.create(user=user, token=token, expiry_date=now() + settings.JWT_EXPIRATION)

            return Response({"message": "User registered successfully.", "user_id": user.id, "token": token}, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UpdateLocationAPIView(APIView):
    def put(self, request):
        user_id = request.data.get("user_id")
        location = request.data.get("location")

        if not user_id or not location:
            return Response({"message": "User ID and location are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = CustomUser.objects.get(id=user_id)
            user.location = location
            user.save()
            return Response({"message": "Location updated successfully.", "location": user.location}, status=status.HTTP_200_OK)

        except CustomUser.DoesNotExist:
            return Response({"message": "User not found."}, status=status.HTTP_404_NOT_FOUND)


class UpdateProfileAPIView(APIView):
    def put(self, request):
        user_id = request.data.get("user_id")
        name = request.data.get("name")
        profile_photo = request.FILES.get("profile_photo")
        interests = request.data.get("interests")
        age_group = request.data.get("age_group")

        if not user_id:
            return Response({"message": "User ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = CustomUser.objects.get(id=user_id)

            user.name = name if name else user.name
            user.age_group = age_group if age_group else user.age_group
            user.profile_photo = profile_photo if profile_photo else user.profile_photo
            user.interests = interests if interests else user.interests


            user.save()
            return Response({"message": "Profile updated successfully."}, status=status.HTTP_200_OK)

        except CustomUser.DoesNotExist:
            return Response({"message": "User not found."}, status=status.HTTP_404_NOT_FOUND)


class LogoutUserAPIView(APIView):
    def delete(self, request):
        token = request.data.get("token")

        if not token:
            return Response({"message": "Token is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            Tokens.objects.get(token=token).delete()
            return Response({"message": "User logged out successfully."}, status=status.HTTP_200_OK)

        except Tokens.DoesNotExist:
            return Response({"message": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST)


class ValidateTokenAPIView(APIView):
    def post(self, request):
        token = request.data.get("token")

        if not token:
            return Response({"message": "Token is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user = CustomUser.objects.get(id=decoded_token["user_id"])
            return Response({"message": "Token is valid.", "is_authenticated": True}, status=status.HTTP_200_OK)

        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, CustomUser.DoesNotExist):
            return Response({"message": "Token is invalid or expired.", "is_authenticated": False}, status=status.HTTP_401_UNAUTHORIZED)


class FetchUserDetailsAPIView(APIView):
    def get(self, request):
        user_id = request.query_params.get("user_id")

        if not user_id:
            return Response({"message": "User ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = CustomUser.objects.get(id=user_id)
            serializer = CustomUserSerializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except CustomUser.DoesNotExist:
            return Response({"message": "User not found."}, status=status.HTTP_404_NOT_FOUND)
