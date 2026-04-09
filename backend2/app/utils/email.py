import random
import string
from datetime import datetime, timedelta


def generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def get_otp_expiry(minutes: int = 10) -> datetime:
    return datetime.utcnow() + timedelta(minutes=minutes)
