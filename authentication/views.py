from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from .serializers import CustomUserSerializer, OwnerSerializer, ManagerSerializer, WaiterSerializer, RequestedOwnerSerializer, StaffVerificationSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError, PermissionDenied
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from django.db import transaction
from .models import CustomUser, Owner, Manager, Waiter, RequestedOwner
# from .utils import send_otp_via_sms
from django.conf import settings
from twilio.rest import Client
# from django.http import JsonResponse
from google.auth.transport.requests import Request
from google.oauth2 import id_token
# from django.contrib.auth import get_user_model
from django.utils.timezone import now
from datetime import datetime
import jwt
from rest_framework import status
from partner.models import Venue


from django.http import JsonResponse
from django.db import connection
from rest_framework.views import APIView

class CheckAPIView(APIView):
    def post(self, request):
        table_name = 'authentication_customuser'  # Replace if app name is different

        with connection.cursor() as cursor:
            # Check if the table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, [table_name])
            table_exists = cursor.fetchone()[0]

            if not table_exists:
                return Response(
                    {"message": f"Table '{table_name}' does not exist."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Get column names
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 1")
            column_names = [desc[0] for desc in cursor.description]

        return Response(
            {
                "message": f"Table '{table_name}' exists.",
                "columns": column_names
            },
            status=status.HTTP_200_OK
        )


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
        input_user_type = request.data.get("user_type", "customuser").lower()

        if not phone_number or not otp:
            return Response(
                {"message": "Phone number and OTP are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Verification logic (keep test numbers)
            if phone_number in ["9999999999", "1111111111", "2222222222", "3333333333"]:
                verification_status = "approved"
            else:
                client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                verification_check = client.verify \
                    .v2 \
                    .services(settings.TWILIO_SERVICE_SID) \
                    .verification_checks \
                    .create(to="+91" + phone_number, code=otp)
                verification_status = verification_check.status

            if verification_status != "approved":
                return Response(
                    {"message": "Invalid OTP.", "is_verified": False},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get or create the user
            user, created = CustomUser.objects.get_or_create(
                phone_number=phone_number,
                defaults={
                    'is_verified': True,
                    'last_login': datetime.now()
                }
            )

            if not created:
                user.is_verified = True
                user.last_login = datetime.now()
                user.save()

            # Determine user type and set is_staff
            final_user_type = input_user_type
            is_staff = False

            if input_user_type == 'partner':
                # Check for existing partner roles (owner > manager > waiter)
                if Owner.objects.filter(user=user).exists():
                    final_user_type = 'owner'
                elif Manager.objects.filter(user=user).exists():
                    final_user_type = 'manager'
                elif Waiter.objects.filter(user=user).exists():
                    final_user_type = 'waiter'
                else:
                    final_user_type = 'partner'
            
            # Set is_staff for partner roles
            if final_user_type in ['owner', 'manager', 'waiter', 'partner']:
                is_staff = True
                user.is_staff = True
                user.save()

            # Generate token
            token = AccessToken.for_user(user)
            token['user_type'] = final_user_type

            return Response({
                "message": "Phone number verified successfully.",
                "is_verified": True,
                "access": str(token),
                "user_type": final_user_type,
                "user_id": str(user.id),
                "is_staff": is_staff
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class RequestOwnerAPIView(APIView):
    def post(self, request):
        serializer = RequestedOwnerSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Owner request submitted successfully."}, status=201)
        return Response(serializer.errors, status=400)

class VerifyOwnerAPIView(APIView):
    def post(self, request):
        phone_number = request.data.get("phone_number")

        try:
            requested_owner = RequestedOwner.objects.get(phone_number=phone_number)

            # Create CustomUser
            user, created = CustomUser.objects.get_or_create(
                phone_number=phone_number,
                defaults={
                    "email": requested_owner.email,
                    "name": requested_owner.name,
                    "is_verified": True
                }
            )
            if not created:
                user.email = requested_owner.email
                user.name = requested_owner.name
                user.is_verified = True
                user.save()

            # Create Owner
            owner = Owner.objects.create(user=user)

            # Update request to accepted
            requested_owner.owner_accepted = "accepted"
            requested_owner.save()

            # Create Venue
            venue = Venue.objects.create(
                name=requested_owner.business_name,
                description=requested_owner.details,
                category=requested_owner.category,
                gst_number=requested_owner.gst_number,
                pan_number=requested_owner.pan_number,
            )
            venue.owners.add(owner)

            # Create JWT
            token = AccessToken.for_user(user)
            token["user_type"] = "owner"

            return Response({
                "message": "Owner verified and venue created successfully.",
                "access": str(token),
                "user_id": str(user.id)
            }, status=201)

        except RequestedOwner.DoesNotExist:
            return Response({"message": "Requested owner not found."}, status=404)
        except Exception as e:
            return Response({"message": str(e)}, status=500)

class DeclineOwnerAPIView(APIView):
    def post(self, request):
        phone_number = request.data.get("phone_number")

        try:
            requested_owner = RequestedOwner.objects.get(phone_number=phone_number)
            requested_owner.owner_accepted = "declined"
            requested_owner.save()
            return Response({"message": "Owner request declined."}, status=200)
        except RequestedOwner.DoesNotExist:
            return Response({"message": "Requested owner not found."}, status=404)
        except Exception as e:
            return Response({"message": str(e)}, status=500)

class VerifyStaffAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = StaffVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        role_to_add = data['role']
        request_user = request.user

        print("Raw JWT payload:", request.auth.payload) 
        user_type = request.auth.payload.get('user_type')
        print(f"Extracted user_type: {user_type}")
        
        try:
            with transaction.atomic():
                if role_to_add == 'CO_OWNER':
                    return self._add_co_owner(request_user, user_type, data)
                elif role_to_add == 'MANAGER':
                    return self._add_manager(request_user, user_type, data)
                elif role_to_add == 'WAITER':
                    return self._add_waiter(request_user, user_type, data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def _validate_owner_permission(self, user, user_type):
        """Validate that user is an owner"""
        if (user_type).lower() != 'owner':
            raise PermissionDenied('Only owners can perform this action')
        return get_object_or_404(Owner, user=user)
    
    def _validate_venue_permission(self, user, user_type, venue_id):
        """Validate that user has permission for the venue"""
        venue = get_object_or_404(Venue, venue_id=venue_id)
        
        if (user_type).lower() == 'owner':
            if not venue.owners.filter(user=user).exists():
                raise PermissionDenied('You are not an owner of this venue')
        elif (user_type).lower() == 'manager':
            if not Manager.objects.filter(user=user, venue=venue).exists():
                raise PermissionDenied('You are not a manager of this venue')
        else:
            raise PermissionDenied('You do not have permission for this venue')
        
        return venue
    
    def _create_or_get_user(self, data, is_staff=False):
        """Helper to create or get user with proper defaults"""
        user, created = CustomUser.objects.get_or_create(
            phone_number=data['phone_number'],
            defaults={
                'name': data['name'],
                'email': data.get('email'),
                'is_verified': True,
                'is_staff': is_staff
            }
        )
        return user, created
    
    def _add_co_owner(self, request_user, user_type, data):
        # Only owners can add co-owners
        requesting_owner = self._validate_owner_permission(request_user, user_type)
        
        # Get one of the venues owned by the requesting owner
        venue = requesting_owner.venues.first()
        if not venue:
            raise ValidationError('Requesting owner has no venues')
        
        # Create or get the user
        user, created = self._create_or_get_user(data, is_staff=True)
        
        if not created:
            if Owner.objects.filter(user=user).exists():
                raise ValidationError('User is already a co-owner')
        
        # Create the owner
        owner = Owner.objects.create(user=user)
        
        # Add to venue owners
        venue.owners.add(owner)
        
        return Response(
            {
                'message': 'Co-owner added successfully',
                'owner_id': owner.user_id,
                'venue_id': venue.venue_id
            },
            status=status.HTTP_201_CREATED
        )
    
    def _add_manager(self, request_user, user_type, data):
        # Only owners can add managers
        if (user_type).lower() != 'owner':
            raise PermissionDenied('Only owners can add managers')
        
        venue = self._validate_venue_permission(request_user, user_type, data['venue_id'])
        
        # Create or get the user
        user, created = self._create_or_get_user(data, is_staff=True)
        
        if not created:
            if Manager.objects.filter(user=user, venue=venue).exists():
                raise ValidationError('User is already a manager for this venue')
        
        # Create the manager
        manager = Manager.objects.create(user=user, venue=venue)
        
        # Add all venue owners as managers' owners
        manager.owners.set(venue.owners.all())
        
        return Response(
            {
                'message': 'Manager added successfully',
                'manager_id': manager.user_id,
                'venue_id': venue.venue_id
            },
            status=status.HTTP_201_CREATED
        )
    
    def _add_waiter(self, request_user, user_type, data):
        # Owners or managers can add waiters
        if (user_type).lower() not in ['owner', 'manager']:
            raise PermissionDenied('Only owners or managers can add waiters')
        
        venue = self._validate_venue_permission(request_user, user_type, data['venue_id'])
        
        # Create or get the user
        user, created = self._create_or_get_user(data)
        
        if not created:
            if Waiter.objects.filter(user=user, venue=venue).exists():
                raise ValidationError('User is already a waiter for this venue')
        
        # Create the waiter
        waiter = Waiter.objects.create(user=user, venue=venue)
        
        # Add all venue managers as waiter's managers
        managers = Manager.objects.filter(venue=venue)
        waiter.managers.set(managers)
        
        return Response(
            {
                'message': 'Waiter added successfully',
                'waiter_id': waiter.user_id,
                'venue_id': venue.venue_id
            },
            status=status.HTTP_201_CREATED
        )
        
class VerifyGoogleAPIView(APIView):
    def post(self, request):
        google_token = request.data.get("google_token")

        if not google_token:
            return Response(
                {"message": "Google token is required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Verify Google token
            id_info = id_token.verify_oauth2_token(
                google_token, 
                google_requests.Request(), 
                settings.GOOGLE_CLIENT_ID
            )
            
            email = id_info.get("email")
            name = id_info.get("name")

            # Get or create user
            user, created = CustomUser.objects.get_or_create(
                email=email,
                defaults={
                    'is_verified': True,
                    'name': name
                }
            )
            
            # Update user if not created
            if not created:
                user.is_verified = True
                if not user.name:
                    user.name = name
                user.last_login = now()
                user.save()

            # Generate SimpleJWT token
            token = AccessToken.for_user(user)
            
            # Add custom claims if needed (e.g., user_type)
            token['user_type'] = 'customuser'  # Or get from user model if available
            
            return Response({
                "message": "Google account verified successfully.",
                "is_verified": True,
                "access": str(token),  # SimpleJWT standard field name
                "refresh": str(token),  # Add if using refresh tokens
                "user_id": str(user.id),
                "email": user.email
            }, status=status.HTTP_200_OK)

        except ValueError:
            return Response(
                {"message": "Invalid Google token."},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class CheckUserExistsAPIView(APIView):
    def post(self, request):
        email = request.data.get("email")
        phone_number = request.data.get("phone_number")

        if not email and not phone_number:
            return Response(
                {"message": "Email or phone number is required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Search across all user types
        user_types = {
            'customuser': CustomUser,
            'owner': Owner,
            'manager': Manager,
            'waiter': Waiter
        }

        results = {}
        exists = False

        for user_type, model in user_types.items():
            query = {}
            if email:
                query['email'] = email
            if phone_number:
                query['phone_number'] = phone_number
            
            # Get the first matching record for each user type
            user = model.objects.filter(**query).first()
            
            if user:
                exists = True
                results[user_type] = {
                    'exists': True,
                    'id': str(user.id),
                    'email': user.email,
                    'phone_number': user.phone_number,
                    'is_verified': user.is_verified,
                    'name': user.name
                }
            else:
                results[user_type] = {'exists': False}

        if exists:
            return Response(
                {
                    "message": "User exists",
                    "exists": True,
                    "roles": results,
                    "has_multiple_roles": sum(1 for role in results.values() if role['exists']) > 1
                },
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {
                    "message": "User does not exist in any role",
                    "exists": False,
                    "roles": results
                },
                status=status.HTTP_404_NOT_FOUND
            )

class RegisterUserAPIView(APIView):
    def post(self, request):
        serializer = CustomUserSerializer(data=request.data)

        if serializer.is_valid():
            # Check for existing user before saving
            phone_number = request.data.get("phone_number")
            if phone_number and CustomUser.objects.filter(phone_number=phone_number).exists():
                existing_user = CustomUser.objects.get(phone_number=phone_number)
                return Response({
                    "message": "User with this phone number already exists.",
                    "user_id": existing_user.id
                }, status=status.HTTP_400_BAD_REQUEST)

            # Create new user
            user = serializer.save()
            
            # Generate SimpleJWT tokens
            access_token = AccessToken.for_user(user)
            refresh_token = RefreshToken.for_user(user)  # Optional: if using refresh tokens
            
            # Add custom claims if needed
            access_token['user_type'] = 'customuser'  # Example custom claim
            
            return Response({
                "message": "User registered successfully.",
                "user_id": str(user.id),
                "access": str(access_token),
                "refresh": str(refresh_token),  # Optional
                "email": user.email,
                "phone_number": user.phone_number
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UpdateLocationAPIView(APIView):
    def put(self, request):
        user_id = request.data.get("user_id")
        location = request.data.get("location")
        user_type = request.data.get("user_type", "customuser")  # Default to customuser

        if not user_id or not location:
            return Response(
                {"message": "User ID and location are required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Map user types to their models
        user_model_map = {
            'customuser': CustomUser,
            'owner': Owner,
            'manager': Manager,
            'waiter': Waiter
        }

        if user_type not in user_model_map:
            return Response(
                {"message": "Invalid user type."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            model_class = user_model_map[user_type]
            user = model_class.objects.get(id=user_id)
            
            user.location = location
            user.is_location_permission_granted = True
            user.save()
            
            return Response(
                {
                    "message": "Location updated successfully.",
                    "user_type": user_type,
                    "location": user.location
                }, 
                status=status.HTTP_200_OK
            )

        except model_class.DoesNotExist:
            return Response(
                {"message": f"{user_type.capitalize()} not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class UpdateProfileAPIView(APIView):
    def put(self, request):
        user_id = request.data.get("user_id")
        user_type = request.data.get("user_type", "customuser")  # Default to customuser
        name = request.data.get("name")
        gender = request.data.get("gender")
        profile_photo = request.FILES.get("profile_photo")
        interests = request.data.get("interests")
        age_group = request.data.get("age_group")
        level = request.data.get("level")

        if not user_id:
            return Response(
                {"message": "User ID is required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Map user types to their models
        user_model_map = {
            'customuser': CustomUser,
            'owner': Owner,
            'manager': Manager,
            'waiter': Waiter
        }

        if user_type not in user_model_map:
            return Response(
                {"message": "Invalid user type."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            model_class = user_model_map[user_type]
            user = model_class.objects.get(id=user_id)

            # Update fields if they are provided
            update_fields = []
            if name is not None:
                user.name = name
                update_fields.append('name')
            if gender is not None:
                user.gender = gender
                update_fields.append('gender')
            if age_group is not None and hasattr(user, 'age_group'):
                user.age_group = age_group
                update_fields.append('age_group')
            if profile_photo is not None:
                user.profile_photo = profile_photo
                update_fields.append('profile_photo')
            if interests is not None and hasattr(user, 'interests'):
                user.interests = interests
                update_fields.append('interests')
            if level is not None and hasattr(user, 'level'):
                user.level = level

            if update_fields:
                user.save(update_fields=update_fields)

            return Response(
                {
                    "message": "Profile updated successfully.",
                    "user_type": user_type,
                    "updated_fields": update_fields
                }, 
                status=status.HTTP_200_OK
            )

        except model_class.DoesNotExist:
            return Response(
                {"message": f"{user_type.capitalize()} not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class LogoutUserAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        try:
            refresh_token = request.data["refresh_token"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST)

# class ValidateTokenAPIView(APIView):
#     def post(self, request):
#         token = request.data.get("token")

#         if not token:
#             return Response({"message": "Token is required."}, status=status.HTTP_400_BAD_REQUEST)

#         try:
#             decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
#             user = CustomUser.objects.get(id=decoded_token["user_id"])
#             return Response({"message": "Token is valid.", "is_authenticated": True}, status=status.HTTP_200_OK)

#         except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, CustomUser.DoesNotExist):
#             return Response({"message": "Token is invalid or expired.", "is_authenticated": False}, status=status.HTTP_401_UNAUTHORIZED)

class FetchUserDetailsAPIView(APIView):
    def post(self, request): 
        user_id = request.data.get("user_id")  
        user_type = request.data.get("user_type", "customuser")

        if not user_id:
            return Response(
                {"message": "User ID is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user_model_map = {
            'customuser': {
                'model': CustomUser,
                'serializer': CustomUserSerializer
            },
            'owner': {
                'model': Owner,
                'serializer': OwnerSerializer
            },
            'manager': {
                'model': Manager,
                'serializer': ManagerSerializer
            },
            'waiter': {
                'model': Waiter,
                'serializer': WaiterSerializer
            }
        }

        if user_type not in user_model_map:
            return Response(
                {"message": "Invalid user type."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            model_info = user_model_map[user_type]
            user = model_info['model'].objects.get(id=user_id)
            serializer = model_info['serializer'](user)
            
            return Response(
                {
                    "message": "User details fetched successfully.",
                    "user_type": user_type,
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )

        except model_info['model'].DoesNotExist:
            return Response(
                {"message": f"{user_type.capitalize()} not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class WaiterDetailsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, manager_id=None):  
        try:
            manager = Manager.objects.get(id=manager_id)
            
            waiters = Waiter.objects.filter(manager=manager)
            
            serializer = WaiterSerializer(waiters, many=True)
            
            return Response({
                "count": waiters.count(),
                "waiters": serializer.data
            }, status=status.HTTP_200_OK)
        
        except Manager.DoesNotExist:
            return Response(
                {"error": "Manager not found"},
                status=status.HTTP_404_NOT_FOUND
            )