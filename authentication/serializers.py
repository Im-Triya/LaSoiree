from rest_framework import serializers
from .models import CustomUser

class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'first_name', 'last_name', 'email', 'phone_number', 'age_group', 'gender']  # Update 'name' to 'first_name' and 'last_name'
        extra_kwargs = {'email': {'required': True}, 'phone_number': {'required': True}}

    def create(self, validated_data):
        # Create the user with the validated data (no password handling)
        user = CustomUser.objects.create(**validated_data)
        return user
