from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from .models import Profile
from .validators import birthday_validate


class MyDateInput(forms.DateInput):
    input_type = 'date'


class RegistrationForm(UserCreationForm):
    """
    A form that creates a user, with no privileges, from the given username, email and
    password.
    """
    email = forms.EmailField()
    field_order = ['username', 'password']

    birthdate = forms.DateField(
        label=_('Birthdate'),
        required=True,
        widget=MyDateInput(),
        localize=True,
        validators=[birthday_validate]
    )

    def save(self, commit=True):
        user: User = super(RegistrationForm, self).save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        user.profile.birthdate = self.cleaned_data['birthdate']
        return user


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        exclude = ['user', 'birthdate']

    first_name = forms.CharField(label=_('Name'), max_length=31, required=False)
    last_name = forms.CharField(label=_('Surname'), max_length=31, required=False)
    profile_picture = forms.FileField(label=_('Avatar'), required=False)
    field_order = ['first_name', 'last_name']

    def save(self, commit=True):
        user: User = self.instance.user
        user_data = {
            'first_name': self.cleaned_data['first_name'],
            'last_name': self.cleaned_data['last_name']
        }
        User.objects.filter(id=user.id).update(**user_data)
        return super(ProfileUpdateForm, self).save()
