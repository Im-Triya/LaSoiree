# Generated by Django 5.1.4 on 2025-04-11 21:46

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0007_remove_manager_owner_remove_waiter_manager_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='manager',
            old_name='owner',
            new_name='owners',
        ),
        migrations.RenameField(
            model_name='waiter',
            old_name='manager',
            new_name='managers',
        ),
    ]
