from kavenegar import *
from config.settings import KAVENEGAR_API_KEY
import requests
from random import randint
from . import models
import datetime


def send_otp(mobile, otp):
    try:
        api = KAVENEGAR_API_KEY
        url = f'https://api.kavenegar.com/v1/{api}/verify/lookup.json'
        params = {
            # 'sender': '20006535',  # optional

            'receptor': mobile,  # multiple mobile number, split by comma
            'template': 'keshtazarsms',
            'token': otp,

        }
        response = requests.post(url, params=params)
        print('OTP: ', otp)
        print(response)
    except APIException as e:
        print(e)
    except HTTPException as e:
        print(e)


def get_random_otp():
    return randint(100000, 999999)


def check_otp_expiration(mobile):
    try:
        user = models.CustomUser.objects.get(mobile=mobile)
        now = datetime.datetime.now()
        print(now)
        otp_time = user.otp_create_time
        print(otp_time)
        diff_time = now - otp_time
        print('OTP TIME: ', diff_time)

        if diff_time.seconds > 60:
            return False

        return True

    except models.CustomUser.DoesNotExist:
        return False


