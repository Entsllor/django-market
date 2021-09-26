from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Cart, Balance


@receiver(signal=post_save, sender=User)
def post_create_or_update_user(sender, instance, created, **kwargs):
    if created:
        Balance.objects.create(user=instance)
        Cart.objects.create(user=instance)
