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
        model = CustomUser  # Explicitly set model for base
        fields = [
            'id', 'email', 'phone_number', 'name', 'gender', 'is_verified',
            'is_location_permission_granted', 'location', 'profile_photo', 'last_login',
            'age_group', 'interests', 'level'
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
        # Inherits fields from BaseUserSerializer


class OwnerSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer()  # Nested serializer for CustomUser
    
    class Meta:
        model = Owner
        fields = ['user']  # Only include Owner-specific fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from partner.models import Venue
        self.fields['venues'] = serializers.PrimaryKeyRelatedField(
            many=True,
            queryset=Venue.objects.all(),
            required=False,
            source='user.owner_venues'  # Assuming you have a related_name for venues owned
        )


class ManagerSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer()  # Nested serializer
    
    class Meta:
        model = Manager
        fields = ['user', 'venue', 'owners']  # Manager-specific fields only

    def to_representation(self, instance):
        # Custom representation to handle ManyToManyField
        ret = super().to_representation(instance)
        ret['owners'] = [owner.user_id for owner in instance.owners.all()]
        return ret


class WaiterSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer()  # Nested serializer
    
    class Meta:
        model = Waiter
        fields = ['user', 'venue', 'managers']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['managers'] = [manager.user_id for manager in instance.managers.all()]
        return ret

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