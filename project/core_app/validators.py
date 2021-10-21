import os
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible
from django.utils.translation import gettext_lazy as _


@deconstructible
class ImageSizeValidator:
    def __init__(self, min_image_width, min_image_height, max_image_width, max_image_height):
        self.min_image_width = min_image_width
        self.min_image_height = min_image_height
        self.max_image_width = max_image_width
        self.max_image_height = max_image_height

    def __call__(self, image):
        w = image.width
        h = image.height
        if w > self.max_image_width or h > self.max_image_height:
            raise ValidationError(
                _("Please use an image that is {}x{} or smaller.").format(self.max_image_width, self.max_image_height)
            )
        elif w < self.min_image_width or h < self.min_image_height:
            raise ValidationError(
                _("Please use an image that is {}x{} or bigger.").format(self.min_image_width, self.min_image_height)
            )


@deconstructible
class ImageExtensionValidator:
    def __init__(self, allowed_extensions):
        self.allowed_extensions = allowed_extensions

    def __call__(self, image):
        main, extension = os.path.splitext(image.path)
        if extension not in self.allowed_extensions:
            raise ValidationError(_('Expected file formats for uploads: {}. Caught "{}"').format(
                ", ".join(self.allowed_extensions),
                extension
            ))


@deconstructible
class ForbiddenSymbolsValidator:
    def __init__(self, pattern):
        self.pattern = pattern

    def __call__(self, text):
        if invalid_symbol := re.search(self.pattern, text):
            raise ValidationError(_('Invalid symbol "{}" in text field').format(invalid_symbol.group()))


default_image_format_validator = ImageExtensionValidator(settings.SUPPORTED_IMAGE_FORMATS)
