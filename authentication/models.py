from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

class CustomUserManager(BaseUserManager):
    def create_user(self, email, phone_number, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        if not phone_number:
            raise ValueError("The Phone Number field must be set")
        
        email = self.normalize_email(email)
        user = self.model(email=email, phone_number=phone_number, **extra_fields)
        user.set_password(password)  # Hash the password
        user.save(using=self._db)
        return user

    def create_superuser(self, email, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get('is_superuser') is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        
        return self.create_user(email, phone_number, password, **extra_fields)

class CustomUser(AbstractUser):
    username = None  # Remove the username field
    phone_number = models.CharField(max_length=10, unique=True, null=False, blank=False)
    email = models.EmailField(unique=True, null=False, blank=False)
    age_group = models.CharField(max_length=20, blank=True, null=True)
    gender = models.CharField(
        max_length=10,
        choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')],
        blank=True,
        null=True,
    )

    is_mobile_verified = models.BooleanField(default=False)
    is_google_authenticated = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'  # Use email for authentication
    REQUIRED_FIELDS = ['phone_number']  # Additional fields for createsuperuser

    objects = CustomUserManager()

    def __str__(self):
        return self.email
