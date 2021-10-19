import os
from typing import Iterable

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def get_image_dimensions_validator(min_image_width, min_image_height, max_image_width, max_image_height):
    def image_dimensions_validate(image):
        w = image.width
        h = image.height
        if w > max_image_width or h > max_image_height:
            raise ValidationError(
                _("Please use an image that is {}x{} or smaller.").format(max_image_width, max_image_height)
            )
        elif w < min_image_width or h < min_image_height:
            raise ValidationError(
                _("Please use an image that is {}x{} or bigger.").format(min_image_width, min_image_height)
            )

    return image_dimensions_validate


def get_image_format_validator(allowed_formats: Iterable[str]):
    def image_format_validate(image):
        main, extension = os.path.splitext(image.path)
        if extension not in allowed_formats:
            raise ValidationError(_('Expected file formats for uploads: {}. Caught "{}"').format(
                ", ".join(allowed_formats),
                extension
            ))

    return image_format_validate
