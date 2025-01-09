from django.db import models

class User(models.Model):
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=10, unique=True)
    email = models.EmailField(unique=True)
    age_group = models.CharField(max_length=20)
    gender = models.CharField(max_length=10, choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')])

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['name']

    def __str__(self):
        return self.name
    
    @property
    def is_authenticated(self):
        return True 

    @property
    def is_anonymous(self):
        return False 

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name.split()[0] 

