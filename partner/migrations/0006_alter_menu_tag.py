# Generated by Django 5.1.4 on 2025-04-11 11:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0005_menu_discount_menu_is_available_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='menu',
            name='tag',
            field=models.CharField(choices=[('chef_special', 'Chef Special'), ('starter', 'Starter'), ('main_course', 'Main Course'), ('liquor', 'Liquor'), ('beverage', 'Beverage'), ('tobacco', 'Tobacco')], max_length=20),
        ),
    ]
