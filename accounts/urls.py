from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('verify/', views.verify_otp_view, name='verify'),
    path('logout/', views.logout_view, name='logout'),
    path('resend-otp/', views.resend_otp_view, name='resend_otp'),
]
