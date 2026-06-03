from django.contrib.auth.backends import ModelBackend
from .models import CustomUser


class MobileBackend(ModelBackend):

    @staticmethod
    def authenticate(request, mobile=None, password=None ,):
        try:
            user = CustomUser.objects.get(mobile=mobile)
            return user

        except CustomUser.DoesNotExist:
            pass

    @staticmethod
    def get_user(user_id):
        try:
            return CustomUser.objects.get(pk=user_id)

        except CustomUser.DoesNotExist:
            return None

