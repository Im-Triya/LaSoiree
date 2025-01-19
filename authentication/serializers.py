from rest_framework import serializers
from .models import CustomUser, Tokens

class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            'id', 'email', 'phone_number', 'name', 'age_group', 'gender', 'is_verified', 
            'is_permission_granted', 'location', 'profile_photo', 'interests', 'level', 'last_login'
        ]
        extra_kwargs = {
            'email': {'required': False},
            'phone_number': {'required': False},
            'name': {'required': False},
            'profile_photo': {'required': False},
            'interests': {'required': False},
            'location': {'required': False},
        }

    def validate(self, attrs):
        if not attrs.get('email') and not attrs.get('phone_number'):
            raise serializers.ValidationError('At least one of email or phone number must be provided.')
        return attrs

class TokenSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer(read_only=True)

    class Meta:
        model = Tokens
        fields = ['id', 'user', 'token', 'expiry_date']
