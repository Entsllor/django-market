import datetime
import string

from django.test import SimpleTestCase

from accounts.validators import (
    MIN_USER_AGE, ValidationError,
    MIN_PHONE_NUMBER_LEN, MAX_PHONE_NUMBER_LEN,
    birthday_validate, phone_number_validate
)


def age_to_date(year, days=0):
    now = datetime.datetime.now()
    datetime.timedelta()
    return datetime.datetime(
        year=now.year - year,
        month=now.month,
        day=now.day
    ) - datetime.timedelta(days=days)


class BirthdayValidatorTest(SimpleTestCase):
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


class PhoneNumberValidatorTest(SimpleTestCase):
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
            *[char * self.min_len for char in self.invalid_chars]
        ]
        for number in test_numbers:
            with self.assertRaises(ValidationError, msg=number):
                phone_number_validate(f'{number}')
                phone_number_validate(f'+{number}')
