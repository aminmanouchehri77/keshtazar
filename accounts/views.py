
from django.shortcuts import render, redirect, reverse
from django.contrib import messages
from django.contrib.auth import login, logout
from . models import CustomUser
from .forms import RegisterForm
from . import helper


def login_view(request):
    form = RegisterForm

    if request.method == "POST":
        try:
            if "mobile" in request.POST:
                if len(request.POST["mobile"]) != 11:
                    messages.error(request, 'شماره موبایل شما باید ۱۱ رقم باشد، لطفا دوباره تلاش کنید.', 'danger')
                    return redirect('accounts:login')

                mobile = request.POST.get('mobile')
                user = CustomUser.objects.get(mobile=mobile)
                if helper.check_otp_expiration(mobile):
                    return redirect('accounts:verify')

                # send otp
                otp = helper.get_random_otp()
                helper.send_otp(mobile, otp)
                # save otp
                print(otp)
                user.otp = otp
                user.save()
                request.session['user_mobile'] = user.mobile
                return redirect("accounts:verify")

        except CustomUser.DoesNotExist:
            form = RegisterForm(request.POST)
            if form.is_valid():
                user = form.save(commit=False)
                # send otp
                otp = helper.get_random_otp()
                helper.send_otp(mobile, otp)
                # save otp
                print(otp)
                user.otp = otp
                user.is_active = False
                user.save()
                request.session['user_mobile'] = user.mobile
                return redirect("accounts:verify")
    return render(request, 'accounts/login.html', {'form': form})


# TODO: after login delete the session
def verify_otp_view(request):
    try:
        if request.user.is_authenticated:
            return redirect('index')
        mobile = request.session.get('user_mobile')
        if not mobile:
            messages.error(request, 'مدت زیادی از آخرین ورود شما گذشته است! لطفا بعد از ۱ دقیقه دوباره تلاش کنید.', 'danger')
            return redirect('accounts:login')
        user = CustomUser.objects.get(mobile=mobile)
        if request.method == "POST":
            #check otp expiration
            if not helper.check_otp_expiration(mobile):
                messages.error(request, 'کد OTP منقضی شده است! لطفا دوباره تلاش کنید.', 'danger')
                return redirect('accounts:login')

            if user.otp == int(request.POST.get('otp')):
                user.is_active = True
                user.otp = None
                user.save()
                login(request, user)
                del request.session['user_mobile']
                return redirect('index')

            else:
                messages.error(request, 'کد OTP وارد شده نادرست است! لطفا دوباره تلاش کنید.', 'danger')
                return redirect("accounts:login")

        return render(request, 'accounts/verify.html', {'mobile': mobile,})
    except CustomUser.DoesNotExist:
        messages.error(request, 'کاربر نامعتبر است!', 'danger')
        return redirect("accounts:login")


def resend_otp_view(request):
    mobile = request.session.get('user_mobile')

    if helper.check_otp_expiration(mobile):
        return redirect('accounts:verify')
    otp = helper.get_random_otp()
    print(otp)

    # helper.send_otp(mobile, otp)
    return redirect("accounts:verify")


def logout_view(request):
    logout(request)
    return redirect(reverse('index'))


