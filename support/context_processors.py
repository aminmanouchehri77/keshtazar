from django.conf import settings


def support_widget_settings(request):
    return {'support_phone': settings.SUPPORT_PHONE}
