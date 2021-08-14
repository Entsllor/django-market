from django.contrib import admin

from .models import Profile


class ProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'gender', 'phone_number']


admin.site.register(Profile, ProfileAdmin)
