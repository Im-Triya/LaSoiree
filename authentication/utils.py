from twilio.rest import Client
from django.conf import settings

def send_otp_via_sms(phone_number):
    """
    Sends an OTP via Twilio Verify Service.
    Does not return the verification SID.
    """
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    
    # Send OTP via Twilio Verify service
    client.verify \
        .v2 \
        .services(settings.TWILIO_SERVICE_SID) \
        .verifications \
        .create(to=phone_number, channel="sms")
