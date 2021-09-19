from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.urls import reverse_lazy
from django.utils.translation import ugettext_lazy as _
from django.views.generic import FormView, UpdateView, DetailView

from .forms import *


class LogIn(LoginView):
    template_name = 'accounts/log_in_template.html'
    success_url = reverse_lazy('market_app:catalogue')
    redirect_authenticated_user = True


class LogOut(LogoutView):
    template_name = 'accounts/log_out_page.html'


class ProfileView(LoginRequiredMixin, DetailView):
    template_name = 'accounts/profile.html'
    model = Profile
    context_object_name = 'profile'

    def get_object(self, queryset=None):
        return self.request.user.profile


class UpdateProfile(LoginRequiredMixin, UpdateView):
    """View for updating user profile, with a response rendered by a template."""
    model = ProfileView
    form_class = ProfileUpdateForm
    template_name = 'accounts/update_profile.html'
    success_url = reverse_lazy('accounts:profile')

    def get_object(self, queryset=None):
        return self.request.user.profile


class Registration(FormView):
    """
    View for register and log in a new user,
    with a redirect the user to his profile page after success registration.
    """
    template_name = 'accounts/registration.html'
    form_class = RegistrationForm
    success_url = reverse_lazy('accounts:profile')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user=user)
        return super(Registration, self).form_valid(form=form)


class PasswordChange(LoginRequiredMixin, PasswordChangeView):
    template_name = 'accounts/password_change_template.html'
    success_url = reverse_lazy('accounts:profile')

    def form_valid(self, form):
        messages.success(self.request, _('Your password was changed.'))
        return super(PasswordChange, self).form_valid(form=form)
