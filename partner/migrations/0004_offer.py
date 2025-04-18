# Generated by Django 5.1.4 on 2025-04-09 17:25

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0003_venue_total_capacity'),
    ]

    operations = [
        migrations.CreateModel(
            name='Offer',
            fields=[
                ('offer_id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('offer_type', models.CharField(choices=[('FREE_DRINK', 'Free Drink'), ('PERCENTAGE_OFF', 'Percentage Off'), ('HAPPY_HOUR', 'Happy Hour'), ('BUY1_GET1', 'Buy 1 Get 1'), ('LASOIREE_LEVEL', 'LaSoiree Level Offer'), ('ENTRY_FEE', 'Entry Fee')], max_length=20)),
                ('description', models.TextField()),
                ('level', models.PositiveSmallIntegerField(blank=True, choices=[(1, 'Level 1'), (2, 'Level 2'), (3, 'Level 3'), (4, 'Level 4'), (5, 'Level 5')], null=True)),
                ('user', models.CharField(max_length=255)),
                ('start_date', models.DateTimeField()),
                ('end_date', models.DateTimeField(blank=True, null=True)),
                ('discount_percentage', models.DecimalField(blank=True, decimal_places=2, help_text='Percentage discount (0-100)', max_digits=5, null=True)),
                ('is_entry_fee_required', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('venue', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='offers', to='partner.venue')),
            ],
            options={
                'verbose_name': 'Offer',
                'verbose_name_plural': 'Offers',
                'ordering': ['-start_date'],
            },
        ),
    ]
