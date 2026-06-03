# from django.contrib.auth.forms import UserChangeForm, UserCreationForm
# from .models import CustomUser
#
#
# class CustomUserCreationForm(UserCreationForm):
#     class Meta:
#         model = CustomUser
#         fields = ['mobile', ]
#
#
# class CustomUserChangeForm(UserChangeForm):
#     class Meta:
#         model = CustomUser
#         fields = ['mobile', ]
#
from django import forms

from .models import CustomUser


class RegisterForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['mobile', ]
