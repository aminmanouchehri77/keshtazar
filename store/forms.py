import jdatetime
from django import forms
from .models import Comment, Customer, Address


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['star', 'body']


class AddToCartForm(forms.Form):
    product_id = forms.CharField()
    quantity = forms.IntegerField()
    update = forms.IntegerField()


class CustomerForm(forms.ModelForm):
    birth_date = forms.CharField(
        label="تاریخ تولد",
        widget=forms.TextInput(attrs={
            'class': 'form-control jalali-date-input',
            'autocomplete': 'off',
            'placeholder': 'مثال: ۱۴۰۲/۰۵/۱۲'
        })
    )

    class Meta:
        model = Customer
        fields = ['phone_number','first_name','last_name','email','national_code','birth_date']

    def clean_birth_date(self):
        txt = self.cleaned_data['birth_date'].strip()
        # فرض می‌کنیم ورودی به شکل "۱۴۰۲/۰۵/۱۲" یا "1402/05/12" باشد
        try:
            parts = txt.replace('-', '/').split('/')
            jy, jm, jd = map(int, parts)
            # تبدیل جلالی به میلادی
            gdate = jdatetime.date(jy, jm, jd).togregorian()
            return gdate  # برمی‌گردانیم یک شیء datetime.date
        except Exception:
            raise forms.ValidationError("لطفاً یک تاریخ جلالی معتبر وارد کنید (مثال: ۱۴۰۲/۰۵/۱۲).")

    class Meta:
        model = Customer
        fields = [
            'first_name', 'last_name', 'email',
            'national_code', 'birth_date',
        ]


class AddressForm(forms.ModelForm):
    # Override فیلد street
    street = forms.CharField(
        label="خیابان",
        widget=forms.TextInput(attrs={
            "class": "form-control w-100",  # w-100: عرض ۱۰۰٪ کانتینر (Bootstrap)
            "placeholder": " لطفا نام خیابان و سایر جزئیات آدرس خود را در این فیلد وارد کنید.",
            # اگر می‌خواهید حداکثر عرض ثابت بدهید:
            # "style": "max-width: 500px;"
        })
    )
    # می‌توانید postal_code هم placeholder بدهید
    postal_code = forms.CharField(
        label="کد پستی",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "مثال: 1234567890"
        })
    )

    class Meta:
        model = Address
        fields = ['province', 'city', 'street', 'postal_code']
