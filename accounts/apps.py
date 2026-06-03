from django.apps import AppConfig
from django.core.signals import request_finished
from django.db.models.signals import post_save


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = 'کاربر ها'

    def ready(self):
        from . import signals
        from . import models
        request_finished.connect(signals.my_callback)
        post_save.connect(signals.create_new_user, sender=models.CustomUser)
        post_save.connect(signals.update_user, sender=models.CustomUser)