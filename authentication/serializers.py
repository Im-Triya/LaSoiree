from rest_framework import serializers
from .models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'phone_number', 'age_group', 'gender']
        extra_kwargs = {'email': {'required': True}, 'phone_number': {'required': True}}

    def create(self, validated_data):
        # Create the user with the validated data (no password handling)
        user = User.objects.create(**validated_data)
        return user
