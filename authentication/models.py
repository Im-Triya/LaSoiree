from django.db import models
import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError

class BaseUserManager(BaseUserManager):
    def create_user(self, email=None, phone_number=None, password=None, **extra_fields):
        if not email and not phone_number:
            raise ValueError('User must have either an email or phone number')
        
        email = self.normalize_email(email) if email else None
        user = self.model(email=email, phone_number=phone_number, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email=email, password=password, **extra_fields)

class BaseUserModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, null=True, blank=True)
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    gender = models.CharField(max_length=50, null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    is_location_permission_granted = models.BooleanField(default=False)
    location = models.JSONField(null=True, blank=True)
    profile_photo = models.ImageField(upload_to='profile_photos/', null=True, blank=True)
    last_login = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def clean(self):
        if not self.email and not self.phone_number:
            raise ValidationError('User must have either an email or phone number')

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email if self.email else self.phone_number

class CustomUser(AbstractBaseUser, BaseUserModel, PermissionsMixin):
    age_group = models.CharField(max_length=50, null=True, blank=True)
    interests = models.JSONField(null=True, blank=True)
    level = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = BaseUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

class Owner(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, default=None, null=True, blank=True)
    
class Manager(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, default=None, null=True, blank=True)
    venue = models.ForeignKey('partner.Venue', on_delete=models.CASCADE, null=True, blank=True, related_name='managers')
    owners = models.ManyToManyField(Owner, related_name='managers')

class Waiter(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, default=None, null=True, blank=True)
    venue = models.ForeignKey('partner.Venue', on_delete=models.CASCADE, null=True, blank=True, related_name='waiters')
    managers = models.ManyToManyField(Manager, related_name='waiters')

class RequestedOwner(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    ]

    phone_number = models.CharField(max_length=15, unique=True)
    email = models.EmailField()
    name = models.CharField(max_length=100)
    business_name = models.CharField(max_length=255)
    details = models.TextField()
    category = models.CharField(max_length=100)
    gst_number = models.CharField(max_length=20)
    pan_number = models.CharField(max_length=20)
    owner_accepted = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"{self.name} - {self.business_name} ({self.owner_accepted})"