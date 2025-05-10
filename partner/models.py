from django.apps import apps
from django.forms import ValidationError
import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
from django.db import models
import uuid
from django.db import transaction
from django.core.validators import MinValueValidator, MaxValueValidator

class Venue(models.Model):
    venue_id = models.CharField(max_length=10, unique=True, editable=False)
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(null=True, blank=True)
    category = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    gst_number = models.CharField(max_length=15, null=True, blank=True, unique=True)
    pan_number = models.CharField(max_length=10, null=True, blank=True, unique=True)
    city = models.CharField(max_length=255, db_index=True)
    geo_location = models.JSONField(null=True, blank=True, default=dict)  # Store latitude and longitude
    number_of_tables = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    total_capacity = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    venue_image = models.ImageField(upload_to='venue_images/', blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['name', 'city']),
        ]
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.venue_id:
            with transaction.atomic():
                # Lock the table to prevent race conditions
                last_venue = Venue.objects.select_for_update().order_by('-id').first()
                if last_venue:
                    last_id = int(last_venue.venue_id.replace('VEN', ''))
                    self.venue_id = f"VEN{(last_id + 1):03d}"
                else:
                    self.venue_id = "VEN001"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Table(models.Model):
    venue = models.ForeignKey(Venue, related_name='tables', on_delete=models.CASCADE, db_index=True)
    table_number = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    qr_code = models.CharField(max_length=255, unique=True)  # Stores <venue_id>::<table_no>
    qr_image = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    is_occupied = models.BooleanField(default=False, db_index=True)

    class Meta:
        unique_together = ('venue', 'table_number')
        ordering = ['venue', 'table_number']

    def save(self, *args, **kwargs):
        if not self.qr_code:
            self.qr_code = f"{self.venue.venue_id}::{self.table_number}"
            
        # Only generate QR code if it doesn't exist or if qr_code changed
        if not self.qr_image or not self.pk:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4
            )
            qr.add_data(self.qr_code)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            buffer = BytesIO()
            img.save(buffer, format="PNG")
            file_name = f"qr_{self.qr_code}.png"
            self.qr_image.save(file_name, ContentFile(buffer.getvalue()), save=False)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Table {self.table_number} at {self.venue.name}"


class Menu(models.Model):
    VENUE_ITEM_TAGS = [
        ('chef_special', 'Chef Special'),
        ('starter', 'Starter'),
        ('main_course', 'Main Course'),
        ('liquor', 'Liquor'),
        ('beverage', 'Beverage'),
        ('tobacco', 'Tobacco'),
    ]

    menu_item_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    venue = models.ForeignKey(Venue, related_name='menu_items', on_delete=models.CASCADE, db_index=True)
    item_name = models.CharField(max_length=255, db_index=True)
    item_description = models.TextField(null=True, blank=True)
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    discount = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage discount (0-100)"
    )
    is_available = models.BooleanField(default=True, db_index=True)
    is_veg = models.BooleanField(default=True, db_index=True)
    tag = models.CharField(max_length=20, choices=VENUE_ITEM_TAGS, db_index=True)
    image = models.ImageField(upload_to='menu_images/', blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['venue', 'is_available']),
            models.Index(fields=['venue', 'tag']),
        ]
        ordering = ['item_name']

    def __str__(self):
        return f"{self.item_name} ({self.get_tag_display()}) - {self.venue.name}"


class Offer(models.Model):
    OFFER_TYPES = [
        ('FREE_DRINK', 'Free Drink'),
        ('PERCENTAGE_OFF', 'Percentage Off'),
        ('HAPPY_HOUR', 'Happy Hour'),
        ('BUY1_GET1', 'Buy 1 Get 1'),
        ('LASOIREE_LEVEL', 'LaSoiree Level Offer'),
        ('ENTRY_FEE', 'Entry Fee'),
    ]
    
    LEVELS = [
        (1, 'Level 1'),
        (2, 'Level 2'),
        (3, 'Level 3'),
        (4, 'Level 4'),
        (5, 'Level 5'),
    ]
    
    offer_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    venue = models.ForeignKey(Venue, related_name='offers', on_delete=models.CASCADE, db_index=True)
    offer_type = models.CharField(max_length=20, choices=OFFER_TYPES, db_index=True)
    description = models.TextField(null=True, blank=True)
    level = models.PositiveSmallIntegerField(choices=LEVELS, null=True, blank=True, db_index=True)
    user = models.CharField(max_length=255, null=True, blank=True, db_index=True)  
    start_date = models.DateTimeField(db_index=True)
    end_date = models.DateTimeField(null=True, blank=True, db_index=True)
    discount_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage discount (0-100)"
    )
    is_entry_fee_required = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Offer'
        verbose_name_plural = 'Offers'
        indexes = [
            models.Index(fields=['venue', 'is_active']),
            models.Index(fields=['start_date', 'end_date']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(
                    models.Q(end_date__isnull=True) | 
                    models.Q(end_date__gte=models.F('start_date'))
                ),
                name='check_end_date_after_start_date'
            ),
            models.CheckConstraint(
                check=models.Q(discount_percentage__gte=0, discount_percentage__lte=100),
                name='discount_percentage_range'
            )
        ]

    def __str__(self):
        return f"{self.get_offer_type_display()} - {self.venue.name}"

    def save(self, *args, **kwargs):
        if self.offer_type in ['PERCENTAGE_OFF', 'HAPPY_HOUR'] and not self.discount_percentage:
            raise ValueError(f"{self.get_offer_type_display()} requires discount_percentage")
        super().save(*args, **kwargs)

    def clean(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError("End date must be after start date")