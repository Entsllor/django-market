import datetime
import os.path
import re

from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

SUPPORTED_AVATAR_FORMATS = ['.jpg', '.jpeg', '.png']
MAX_AVATAR_WIDTH = 1200
MAX_AVATAR_HEIGHT = 1200
MIN_AVATAR_WIDTH = 200
MIN_AVATAR_HEIGHT = 200
MIN_PHONE_NUMBER_LEN = 8
MAX_PHONE_NUMBER_LEN = 16
MIN_USER_AGE = 18


def get_age(birthdate: datetime):
    today = datetime.date.today()
    year_delta = (today.year - birthdate.year) - 1
    had_birthday_this_year = (today.month, today.day) >= (birthdate.month, birthdate.day)
    return year_delta + had_birthday_this_year


def avatar_dimensions_validate(avatar):
    w = avatar.width
    h = avatar.height
    if w > MAX_AVATAR_WIDTH or h > MAX_AVATAR_HEIGHT:
        raise ValidationError("{} {}x{} {}".format(
            _('Please use an image that is'),
            MAX_AVATAR_WIDTH,
            MAX_AVATAR_HEIGHT,
            _('or smaller.'),
        ))
    elif w < MIN_AVATAR_WIDTH or h < MIN_AVATAR_HEIGHT:
        raise ValidationError("{} {}x{} {}".format(
            _('Please use an image that is'),
            MIN_AVATAR_WIDTH,
            MIN_AVATAR_HEIGHT,
            _('or bigger.'),
        ))


def avatar_format_validate(avatar):
    main, extension = os.path.splitext(avatar.path)
    if extension not in SUPPORTED_AVATAR_FORMATS:
        raise ValidationError('{}: {}. {} "{extension}"'.format(
            _("Expected file formats for uploads"),
            ", ".join(SUPPORTED_AVATAR_FORMATS),
            _("Caught"),
            extension=extension
        ))


def birthday_validate(date: datetime.datetime):
    age = get_age(date)
    if age < MIN_USER_AGE:
        raise ValidationError(_('You cannot create an account if you are under 18'))


def phone_number_validate(phone):
    if not re.fullmatch(r'^\+?\d{' + f'{MIN_PHONE_NUMBER_LEN},{MAX_PHONE_NUMBER_LEN}' + r'}$', phone):
        raise ValidationError(_('Expected an phone number in the format +99999999999 or 99999999999'))
