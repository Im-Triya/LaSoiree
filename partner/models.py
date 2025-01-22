import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
from django.db import models


class Venue(models.Model):
    venue_id = models.CharField(max_length=10, unique=True, editable=False)
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    geo_location = models.JSONField()  # Store latitude and longitude as a dictionary
    number_of_tables = models.PositiveIntegerField()
    venue_image = models.ImageField(upload_to='venue_images/', blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.venue_id:
            last_venue = Venue.objects.all().order_by('id').last()
            self.venue_id = f"VEN{(int(last_venue.venue_id.replace('VEN', '')) + 1):03d}" if last_venue else "VEN001"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Table(models.Model):
    venue = models.ForeignKey(Venue, related_name='tables', on_delete=models.CASCADE)
    table_number = models.PositiveIntegerField()
    qr_code = models.CharField(max_length=255, unique=True)  # Stores <venue_id>::<table_no>
    qr_image = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    is_occupied = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.qr_code:
            self.qr_code = f"{self.venue.venue_id}::{self.table_number}"

        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
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
        ('starter', 'Starter'),
        ('beverage', 'Beverage'),
        ('main_course', 'Main Course'),
        ('dessert', 'Dessert'),
    ]

    venue = models.ForeignKey(Venue, related_name='menu_items', on_delete=models.CASCADE)
    item_name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_veg = models.BooleanField(default=True)
    tag = models.CharField(max_length=20, choices=VENUE_ITEM_TAGS)
    image = models.ImageField(upload_to='menu_images/', blank=True, null=True)

    def __str__(self):
        return f"{self.item_name} ({self.get_tag_display()}) - {self.venue.name}"
