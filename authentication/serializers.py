from rest_framework import serializers
from .models import CustomUser, Owner, Manager, Waiter, RequestedOwner
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import ValidationError

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['user_type'] = user.get_user_type_display()
        return token

class BaseUserSerializer(serializers.ModelSerializer):
    class Meta:
        fields = [
            'id', 'email', 'phone_number', 'name', 'gender', 'is_verified',
            'is_location_permission_granted', 'location', 'profile_photo', 'last_login'
        ]
        extra_kwargs = {
            'email': {'required': False},
            'phone_number': {'required': False},
            'name': {'required': False},
            'profile_photo': {'required': False},
            'location': {'required': False},
        }

    def validate(self, attrs):
        if not attrs.get('email') and not attrs.get('phone_number'):
            raise serializers.ValidationError('At least one of email or phone number must be provided.')
        return attrs


class CustomUserSerializer(BaseUserSerializer):
    class Meta(BaseUserSerializer.Meta):
        model = CustomUser
        fields = BaseUserSerializer.Meta.fields + ['age_group', 'interests', 'level']


class OwnerSerializer(BaseUserSerializer):
    # Lazy import to avoid circular import
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from partner.models import Venue
        self.fields['venues'] = serializers.PrimaryKeyRelatedField(
            many=True,
            queryset=Venue.objects.all(),
            required=False
        )

    class Meta(BaseUserSerializer.Meta):
        model = Owner
        fields = BaseUserSerializer.Meta.fields + ['venues']


class ManagerSerializer(BaseUserSerializer):
    class Meta(BaseUserSerializer.Meta):
        model = Manager
        fields = BaseUserSerializer.Meta.fields + ['venue', 'owner']


class WaiterSerializer(BaseUserSerializer):
    class Meta(BaseUserSerializer.Meta):
        model = Waiter
        fields = BaseUserSerializer.Meta.fields + ['venue', 'manager']

class RequestedOwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestedOwner
        fields = [
            'phone_number', 'email', 'name',
            'business_name', 'details', 'category',
            'gst_number', 'pan_number'
        ]
        extra_kwargs = {
            'email': {'required': False},
            'name': {'required': False},
            'business_name': {'required': False},
            'details': {'required': False},
            'category': {'required': False},
            'gst_number': {'required': False},
            'pan_number': {'required': False},
        }

class StaffVerificationSerializer(serializers.Serializer):
    ROLE_CHOICES = ['CO_OWNER', 'MANAGER', 'WAITER']
    
    role = serializers.ChoiceField(choices=ROLE_CHOICES)
    phone_number = serializers.CharField()
    name = serializers.CharField()
    email = serializers.EmailField(required=False, allow_null=True)
    venue_id = serializers.CharField(required=False)
    
    def validate(self, attrs):
        role = attrs.get('role')
        venue_id = attrs.get('venue_id')
        
        if role in ['MANAGER', 'WAITER'] and not venue_id:
            raise ValidationError('venue_id is required for manager and waiter roles')
        
        return attrs