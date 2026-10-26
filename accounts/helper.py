from kavenegar import *
from config.settings import KAVENEGAR_API_KEY
import logging
import requests
from random import randint
from . import models
import datetime

logger = logging.getLogger(__name__)


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
        response = requests.post(url, params=params, timeout=10)
        response.raise_for_status()
        logger.info('OTP provider request completed with status %s', response.status_code)
    except APIException:
        logger.error('OTP provider API request failed')
    except HTTPException:
        logger.error('OTP provider HTTP request failed')
    except requests.RequestException:
        logger.error('OTP provider network request failed')


def get_random_otp():
    return randint(100000, 999999)


def check_otp_expiration(mobile):
    try:
        user = models.CustomUser.objects.get(mobile=mobile)
        now = datetime.datetime.now()
        otp_time = user.otp_create_time
        diff_time = now - otp_time

        if diff_time.total_seconds() > 60:
            return False

        return True

    except models.CustomUser.DoesNotExist:
        return False


