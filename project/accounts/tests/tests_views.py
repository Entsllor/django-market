from pathlib import Path

from django.core.exceptions import ObjectDoesNotExist
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from ..views import *


def delete_file_if_exists(abs_path):
    abs_file_path = Path(abs_path)
    if abs_file_path.is_file():
        abs_file_path.unlink()


class AccountsFunctionalTestBase(TestCase):
    registration_url = reverse_lazy('accounts:registration')
    log_in_url = reverse_lazy('accounts:log_in')
    profile_url = reverse_lazy('accounts:profile')

    username = 'test_user_username'
    user_password = 'test_user_password'

    user_data = {
        'username': username,
        'password1': user_password,
        'password2': user_password,
        'email': 'somevalid@mail.com',
        'birthdate': '10/10/2000'
    }

    def register_user(self):
        return self.client.post(self.registration_url, data=self.user_data)

    def try_get_user_by_username(self, username=None):
        if username is None:
            username = self.username
        return User.objects.get(username=username)


class UserRegistrationTest(AccountsFunctionalTestBase):
    def test_can_user_create_account(self):
        self.assertRaises(ObjectDoesNotExist, self.try_get_user_by_username)
        self.register_user()
        user = self.try_get_user_by_username()
        self.assertIn(user, User.objects.all())

    def test_created_user_have_a_profile(self):
        self.register_user()
        user = self.try_get_user_by_username()
        self.assertIsInstance(user.profile, Profile)

    def test_redirect_user_after_registration(self):
        resp = self.register_user()
        self.assertRedirects(resp, self.profile_url)

    def test_user_logged_in_after_registration(self):
        resp = self.register_user()
        self.assertEqual(
            resp.wsgi_request.user,
            self.try_get_user_by_username()
        )

    def test_user_profile_has_a_birthday_value(self):
        self.register_user()
        self.assertTrue(self.try_get_user_by_username().profile.birthdate)


class ProfileFunctionalTest(AccountsFunctionalTestBase):
    update_profile_url = reverse_lazy('accounts:update_profile')
    test_img_path = r'accounts\tests\img_test_folder\TEST_AVATAR_FILE_TO_DELETE_AFTER_TESTS.png'

    profile_data = {
        'country': 'Rwanda',
        'phone_number': '99999999999'
    }

    def setUp(self) -> None:
        self.register_user()
        # expect auto-log-in after registration
        Profile.objects.filter(user_id=self.user.id).update(**self.profile_data)

    @property
    def user(self):
        return self.try_get_user_by_username()

    @property
    def profile(self):
        return self.user.profile

    def get_response_from_profile_page(self):
        return self.client.get(self.profile_url)

    def test_can_update_profile_data(self):
        new_country = 'Uganda'
        data_to_update = {'country': new_country}

        # if need to test update with avatar-updating try this or run test_can_upload_avatar
        # with open(self.test_img_path, 'rb') as avatar_file:
        #     data_to_update['profile_picture'] = SimpleUploadedFile(avatar_file.name, avatar_file.read())

        self.assertNotEqual(self.profile.country, new_country)
        data_to_upload = (self.profile.__dict__.copy() | data_to_update)
        if 'profile_picture' not in data_to_update:
            data_to_upload.pop('profile_picture')  # pop if not to change avatar
        self.client.post(self.update_profile_url, data=data_to_upload)
        self.assertEqual(self.profile.country, new_country)
        self.assertEqual(self.profile.phone_number, self.profile_data['phone_number'])

    def test_can_upload_avatar(self):
        profile_picture_value_before_updating = self.profile.profile_picture

        with open(self.test_img_path, 'rb') as avatar_file:
            data_to_update = {'profile_picture': SimpleUploadedFile(avatar_file.name, avatar_file.read())}
            self.client.post(
                self.update_profile_url,
                data=self.profile.__dict__ | data_to_update
            )
            self.assertNotEqual(self.profile.profile_picture, profile_picture_value_before_updating)

            # we have to delete file in tests from media, unless there will be a lot of unused files in media folder
            delete_file_if_exists(self.profile.profile_picture.path)
            # print(f'{profile_picture_value_before_updating = } {self.profile.profile_picture = }')

    def test_fields_are_displayed(self):
        response = self.get_response_from_profile_page()
        self.assertContains(response, self.profile.country)
        self.assertContains(response, self.profile.phone_number)

    def test_password_is_not_displayed(self):
        response = self.get_response_from_profile_page()
        self.assertNotContains(response, self.user.password)


class AuthenticationTest(AccountsFunctionalTestBase):
    password_change_url = reverse_lazy('accounts:change_password')
    new_password = 'Some2DifficultPassword/'

    def log_in_by_url(self, username=None, password=None):
        if username is None:
            username = self.username
        if password is None:
            password = self.user_password
        return self.client.post(
            self.log_in_url,
            data={'username': username, 'password': password}
        )

    def log_in(self, username=None, password=None):
        if username is None:
            username = self.username
        if password is None:
            password = self.user_password
        return self.client.login(username=username, password=password)

    def get_current_logged_user(self):
        response = self.client.get(self.profile_url)
        return response.wsgi_request.user

    def change_password(self, new_password, old_password=None):
        if old_password is None:
            old_password = self.user_password
        return self.client.post(
            self.password_change_url,
            data={
                'old_password': old_password,
                'new_password1': new_password,
                'new_password2': new_password,
            }
        )

    def setUp(self) -> None:
        response = self.register_user()
        self.registered_user = response.wsgi_request.user

    def test_auth_if_password_is_valid(self):
        self.client.logout()
        response = self.log_in_by_url()
        self.assertRedirects(response, self.profile_url)
        self.assertEqual(self.registered_user, self.get_current_logged_user())

    def test_auth_if_password_is_invalid(self):
        self.client.logout()
        response = self.log_in_by_url(password=self.user_password[::-1])
        self.assertFalse(response.context['form'].is_valid())
        self.assertURLEqual(self.log_in_url, response.request['PATH_INFO'])

    def test_change_password(self):
        old_password = self.user_password
        self.assertTrue(self.log_in(password=old_password))
        self.change_password(self.new_password)
        self.client.logout()
        self.assertFalse(self.log_in(password=old_password))
        self.assertTrue(self.log_in(password=self.new_password))

    def test_redirect_after_password_changing(self):
        response = self.change_password(self.new_password)
        self.assertRedirects(response, self.profile_url)
