import datetime
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from core_app.validators import default_image_format_validator, ImageSizeValidator

SUPPORTED_AVATAR_FORMATS = settings.SUPPORTED_IMAGE_FORMATS
MIN_USER_AGE = settings.MIN_USER_AGE
MAX_AVATAR_WIDTH = 1200
MAX_AVATAR_HEIGHT = 1200
MIN_AVATAR_WIDTH = 200
MIN_AVATAR_HEIGHT = 200
MIN_PHONE_NUMBER_LEN = 8
MAX_PHONE_NUMBER_LEN = 16


def get_age(birthdate: datetime):
    today = datetime.date.today()
    year_delta = (today.year - birthdate.year) - 1
    had_birthday_this_year = (today.month, today.day) >= (birthdate.month, birthdate.day)
    return year_delta + had_birthday_this_year


avatar_dimensions_validate = ImageSizeValidator(
    MIN_AVATAR_WIDTH, MIN_AVATAR_HEIGHT, MAX_AVATAR_WIDTH, MAX_AVATAR_HEIGHT
)

avatar_format_validate = default_image_format_validator


def birthday_validate(date: datetime.datetime):
    age = get_age(date)
    if age < MIN_USER_AGE:
        raise ValidationError(_('You cannot create an account if you are under {}.').format(MIN_USER_AGE))


def phone_number_validate(phone):
    if not re.fullmatch(r'^\+?\d{' + f'{MIN_PHONE_NUMBER_LEN},{MAX_PHONE_NUMBER_LEN}' + r'}$', phone):
        raise ValidationError(_('Expected an phone number in the format +99999999999 or 99999999999'))
