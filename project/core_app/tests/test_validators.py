from django.conf import settings
from django.test import SimpleTestCase

from core_app.file_utils import *
from core_app.validators import *

supported_image_formats = settings.SUPPORTED_IMAGE_FORMATS
min_image_width = 500
min_image_height = 600
max_image_width = 1000
max_image_height = 1200

image_format_validate = get_image_format_validator(supported_image_formats)
image_dimensions_validate = get_image_dimensions_validator(
    min_image_width,
    min_image_height,
    max_image_width,
    max_image_height
)


class AvatarTest(SimpleTestCase):
    def setUp(self) -> None:
        self.img_path = 'img_test_folder\\__TEST_IMG__'
        if is_file_exists(self.img_path):
            raise FileExistsError('File already exists')

    def test_get_valid_formats(self):
        for supported_format in supported_image_formats:
            img = create_img(self.img_path + supported_format, 1, 1, save=False)
            image_format_validate(img)

    def test_get_invalid_formats(self):
        for unsupported_format in ['.txt', '.py', '.gif', '.mp4', '.mp3']:
            img = create_img(self.img_path + unsupported_format, 1, 1, save=False)
            with self.assertRaises(ValidationError):
                image_format_validate(img)

    def test_valid_image_dimension(self):
        dimensions = (
            ((max_image_width + min_image_width) // 2, (max_image_height + min_image_height) // 2),
            ((max_image_width + min_image_width) // 2, max_image_height),
            (max_image_width, (max_image_height + min_image_height) // 2),
            (max_image_width, max_image_height),
            (min_image_height, max_image_height),
        )
        for w, h in dimensions:
            img = create_img(self.img_path + supported_image_formats[0], w, h, save=False)
            image_dimensions_validate(img)

    def test_invalid_image_dimension(self):
        dimensions = (
            (min_image_width - 1, min_image_width - 1),
            (min_image_width - 1, min_image_width),
            (max_image_width + 1, max_image_height),
            (max_image_width + 1, max_image_height + 1),
            (max_image_width, max_image_height + 1),
        )
        for w, h in dimensions:
            img = create_img(self.img_path + supported_image_formats[0], w, h, save=False)
            with self.assertRaises(ValidationError):
                image_dimensions_validate(img)
