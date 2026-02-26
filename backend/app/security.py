import firebase_admin
from firebase_admin import auth, credentials
import os
from typing import Optional
from fastapi import Header, HTTPException


cred_path = os.path.join(
    os.path.dirname(__file__),
    "firebase-service-account.json"
)

cred = credentials.Certificate(cred_path)

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)


def verify_firebase_token(token: str):
    decoded = auth.verify_id_token(token)
    return decoded["uid"]


def require_auth(authorization: Optional[str] = Header(None)):
  
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    try:
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authorization header")

        token = parts[1]
        uid = verify_firebase_token(token)
        return uid
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")