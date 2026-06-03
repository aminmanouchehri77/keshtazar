from django.urls import register_converter


class PersianSlugConverter:
    regex = r'[-\wآ-ی]+'  # حروف فارسی + کاراکترهای مجاز

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value


register_converter(PersianSlugConverter, 'pslug')