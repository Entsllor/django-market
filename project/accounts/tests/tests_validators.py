import datetime
import unittest
import string

from accounts.file_utils import create_img, is_file_exists
from accounts.validators import (
    MAX_AVATAR_WIDTH, MAX_AVATAR_HEIGHT,
    MIN_AVATAR_WIDTH, MIN_AVATAR_HEIGHT,
    SUPPORTED_AVATAR_FORMATS, MIN_USER_AGE,
    ValidationError, avatar_format_validate,
    MIN_PHONE_NUMBER_LEN, MAX_PHONE_NUMBER_LEN,
    avatar_dimensions_validate, birthday_validate, phone_number_validate
)


def age_to_date(year, days=0):
    now = datetime.datetime.now()
    datetime.timedelta()
    return datetime.datetime(
        year=now.year - year,
        month=now.month,
        day=now.day
    ) - datetime.timedelta(days=days)


class AvatarTest(unittest.TestCase):
    def setUp(self) -> None:
        self.img_path = 'img_test_folder\\__TEST_IMG__'
        if is_file_exists(self.img_path):
            raise FileExistsError('File already exists')

    def test_constants_are_valid(self):
        self.assertGreater(MAX_AVATAR_HEIGHT, 0)
        self.assertGreater(MAX_AVATAR_WIDTH, 0)
        self.assertIsInstance(MAX_AVATAR_HEIGHT, int)
        self.assertIsInstance(MAX_AVATAR_WIDTH, int)
        self.assertIsInstance(SUPPORTED_AVATAR_FORMATS, (list, tuple))

    def test_get_valid_formats(self):
        for supported_format in SUPPORTED_AVATAR_FORMATS:
            img = create_img(self.img_path + supported_format, 1, 1, save=False)
            avatar_format_validate(img)

    def test_get_invalid_formats(self):
        for unsupported_format in ['.txt', '.py', '.gif', '.mp4', '.mp3']:
            img = create_img(self.img_path + unsupported_format, 1, 1, save=False)
            with self.assertRaises(ValidationError):
                avatar_format_validate(img)

    def test_valid_avatar_dimension(self):
        dimensions = (
            ((MAX_AVATAR_WIDTH + MIN_AVATAR_WIDTH) // 2, (MAX_AVATAR_HEIGHT + MIN_AVATAR_HEIGHT) // 2),
            ((MAX_AVATAR_WIDTH + MIN_AVATAR_WIDTH) // 2, MAX_AVATAR_HEIGHT),
            (MAX_AVATAR_WIDTH, (MAX_AVATAR_HEIGHT + MIN_AVATAR_HEIGHT) // 2),
            (MAX_AVATAR_WIDTH, MAX_AVATAR_HEIGHT),
            (MIN_AVATAR_HEIGHT, MAX_AVATAR_HEIGHT),
        )
        for w, h in dimensions:
            img = create_img(self.img_path + SUPPORTED_AVATAR_FORMATS[0], w, h, save=False)
            avatar_dimensions_validate(img)

    def test_invalid_avatar_dimension(self):
        dimensions = (
            (MIN_AVATAR_WIDTH - 1, MIN_AVATAR_WIDTH - 1),
            (MIN_AVATAR_WIDTH - 1, MIN_AVATAR_WIDTH),
            (MAX_AVATAR_WIDTH + 1, MAX_AVATAR_HEIGHT),
            (MAX_AVATAR_WIDTH + 1, MAX_AVATAR_HEIGHT + 1),
            (MAX_AVATAR_WIDTH, MAX_AVATAR_HEIGHT + 1),
        )
        for w, h in dimensions:
            img = create_img(self.img_path + SUPPORTED_AVATAR_FORMATS[0], w, h, save=False)
            with self.assertRaises(ValidationError):
                avatar_dimensions_validate(img)


class BirthdayValidatorTest(unittest.TestCase):
    min_age = MIN_USER_AGE

    def setUp(self) -> None:
        self.now = datetime.datetime.now()

    def test_older_than_min_age(self):
        birthdays = (
            # a year older
            age_to_date(self.min_age + 1),
            # a day older
            age_to_date(self.min_age, 1),
            # 40 days older
            age_to_date(self.min_age, 40),
        )
        for birthdate in birthdays:
            birthday_validate(birthdate)

    def test_birthdate_is_today(self):
        birthday_validate(age_to_date(self.min_age))

    def test_younger_than_min_age(self):
        birthdays = (
            # a day younger
            age_to_date(self.min_age, -1),
            # a month younger
            age_to_date(self.min_age, -31),
            # a year younger
            age_to_date(self.min_age - 1),
        )
        for birthdate in birthdays:
            with self.assertRaises(ValidationError):
                birthday_validate(birthdate)


class PhoneNumberValidatorTest(unittest.TestCase):
    min_len = MIN_PHONE_NUMBER_LEN
    max_len = MAX_PHONE_NUMBER_LEN
    invalid_chars = string.ascii_letters + string.punctuation.replace('+', '') + string.whitespace

    def get_number(self, num_len):
        digits = '1234567890'
        return digits * (num_len // len(digits)) + digits[:(num_len % len(digits))]

    def test_valid_numbers(self):
        test_numbers = [self.get_number(i) for i in range(self.min_len, self.max_len + 1)]
        for number in test_numbers:
            phone_number_validate(f'{number}')
            phone_number_validate(f'+{number}')

    def test_invalid_numbers(self):
        test_numbers = (
            self.get_number(self.min_len - 1),
            self.get_number(self.max_len + 1),
        )
        for number in test_numbers:
            with self.assertRaises(ValidationError, msg=number):
                phone_number_validate(f'{number}')
                phone_number_validate(f'+{number}')

    def test_incorrect_chars_in_number(self):
        test_numbers = [
            self.get_number(self.min_len)[:-1] + 'a',
            'a' + self.get_number(self.min_len)[1:],
            '-' + self.get_number(self.min_len)[1:],
            '#' + self.get_number(self.min_len)[1:],
        ] + [char * self.min_len for char in self.invalid_chars]
        for number in test_numbers:
            with self.assertRaises(ValidationError, msg=number):
                phone_number_validate(f'{number}')
                phone_number_validate(f'+{number}')
