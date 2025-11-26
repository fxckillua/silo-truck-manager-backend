# utils/auth.py
from datetime import datetime, timedelta
import jwt
from flask import current_app

def generate_token(user_id: int, profile: str):
    payload = {
        "sub": user_id,
        "profile": profile,
        "exp": datetime.utcnow() + timedelta(hours=8)
    }
    token = jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")
    return token

def decode_token(token: str):
    try:
        payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def generate_reset_token(user_id: int, expires_in_minutes: int = 15) -> str:
    payload = {
        "sub": user_id,
        "type": "password_reset",
        "exp": datetime.utcnow() + timedelta(minutes=expires_in_minutes)
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def verify_reset_token(token: str):
    try:
        payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
        if payload.get("type") != "password_reset":
            return None
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
