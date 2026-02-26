import logging
import os
from typing import Optional

import firebase_admin
from firebase_admin import auth, credentials
from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)

cred_path = os.path.join(os.path.dirname(__file__), "firebase-service-account.json")

_firebase_ready = False
try:
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        _firebase_ready = True
    else:
        logger.warning("firebase-service-account.json not found -- Firebase auth disabled.")
except Exception as _e:
    logger.warning(f"Firebase init failed: {_e} -- auth disabled.")


def verify_firebase_token(token: str):
    decoded = auth.verify_id_token(token)
    return decoded["uid"]


def require_auth(authorization: Optional[str] = Header(None)):
    # If Firebase is not configured, skip authentication locally
    if not _firebase_ready:
        return "anonymous"

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
