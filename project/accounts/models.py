from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from .validators import phone_number_validate, birthday_validate, avatar_format_validate, \
    avatar_dimensions_validate


MAX_AVATAR_SIZE = 100 * 1024
GENDERS_CHOICES = [
    ('m', _('Male')),
    ('f', _('Female')),
]


class Profile(models.Model):
    user = models.OneToOneField(
        User,
        verbose_name=_('user'),
        on_delete=models.CASCADE,
        related_name='profile')

    first_name = models.CharField(
        verbose_name=_('first name'),
        max_length=150,
        blank=True)

    last_name = models.CharField(
        verbose_name=_('last name'),
        max_length=150,
        blank=True)

    phone_number = models.CharField(
        verbose_name=_('phone number'),
        blank=True,
        default='',
        max_length=16,
        validators=[phone_number_validate])

    birthdate = models.DateField(
        verbose_name=_('birthdate'),
        validators=[birthday_validate],
        null=True)

    country = models.CharField(
        verbose_name=_('country'),
        blank=True,
        max_length=127)

    town = models.CharField(
        verbose_name=_('town'),
        blank=True,
        max_length=127)

    about_user = models.TextField(
        verbose_name=_('about user'),
        blank=True,
        max_length=1024)

    avatar = models.ImageField(
        max_length=MAX_AVATAR_SIZE,
        verbose_name=_('avatar'),
        upload_to='avatars/',
        null=True,
        blank=True,
        # default='avatars/default_user_avatar.jpg',
        validators=[avatar_format_validate, avatar_dimensions_validate]
    )

    gender = models.CharField(
        verbose_name=_('gender'),
        max_length=3,
        choices=GENDERS_CHOICES,
        blank=True,
    )

    class Meta:
        verbose_name = _('Profile')
        verbose_name_plural = _('Profiles')

    def __str__(self):
        return f'Profile: {self.user.username}'

    def get_public_information(self) -> dict:
        public_information = {
            _('with us since'): self.user.date_joined,
            _('birthdate'): self.birthdate,
            _('first name'): self.first_name,
            _('last name'): self.last_name,
            _('gender'): self.gender,
            _('phone number'): self.phone_number,
            _('country'): self.country,
            _('town'): self.town,
            _('about user'): self.about_user,
        }
        return public_information


@receiver(signal=post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """Create or update the user's profile if the user-object is saved"""
    if created:
        Profile.objects.create(user=instance)
    instance.profile.save()
