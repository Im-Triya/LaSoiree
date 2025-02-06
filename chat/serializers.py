from rest_framework import serializers
from .models import PrivateMessage

class PrivateMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    receiver_name = serializers.SerializerMethodField()

    class Meta:
        model = PrivateMessage
        fields = ['sender_name', 'receiver_name', 'message']

    def get_sender_name(self, obj):
        return obj.sender.get_full_name()

    def get_receiver_name(self, obj):
        return obj.receiver.get_full_name()