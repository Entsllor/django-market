from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ShoppingAccount, Cart


@receiver(signal=post_save, sender=User)
def post_create_or_update_user(sender, instance, created, **kwargs):
    """Create or update user's shopping account if the user-object is saved"""
    if created:
        ShoppingAccount.objects.create(user=instance)
    instance.shopping_account.save()


@receiver(signal=post_save, sender=ShoppingAccount)
def post_create_cart(sender, instance, created, **kwargs):
    """Create or update user's shopping account if the user-object is saved"""
    if not instance.cart:
        instance.cart = Cart.objects.create()
