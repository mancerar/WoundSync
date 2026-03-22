import logging
import json
import os
from typing import Optional
from dotenv import load_dotenv

import firebase_admin
from firebase_admin import auth, credentials
from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)

BACKEND_ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(BACKEND_ENV_PATH)

DEFAULT_CRED_PATH = os.path.join(os.path.dirname(__file__), "firebase-service-account.json")
FIREBASE_SERVICE_ACCOUNT_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()
FIREBASE_SERVICE_ACCOUNT_JSON = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
ALLOW_ANON_AUTH = os.getenv("ALLOW_ANON_AUTH", "false").strip().lower() == "true"


def _init_firebase_admin() -> bool:
    """Initialize Firebase Admin from backend-only secrets.

    Priority:
    1) FIREBASE_SERVICE_ACCOUNT_JSON (JSON string)
    2) FIREBASE_SERVICE_ACCOUNT_PATH (file path)
    3) legacy local file backend/app/firebase-service-account.json (if present)
    """
    try:
        cred = None

        if FIREBASE_SERVICE_ACCOUNT_JSON:
            cred_dict = json.loads(FIREBASE_SERVICE_ACCOUNT_JSON)
            cred = credentials.Certificate(cred_dict)
        else:
            cred_path = FIREBASE_SERVICE_ACCOUNT_PATH or DEFAULT_CRED_PATH
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)

        if cred is None:
            logger.warning(
                "Firebase Admin credentials not found. Set FIREBASE_SERVICE_ACCOUNT_PATH "
                "or FIREBASE_SERVICE_ACCOUNT_JSON in backend env."
            )
            return False

        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        return True
    except Exception as exc:
        logger.warning(f"Firebase init failed: {exc}")
        return False


_firebase_ready = _init_firebase_admin()


def verify_firebase_token(token: str):
    decoded = auth.verify_id_token(token)
    return decoded["uid"]


def require_auth(authorization: Optional[str] = Header(None)):
    if not _firebase_ready:
        if ALLOW_ANON_AUTH:
            return "anonymous"
        raise HTTPException(
            status_code=503,
            detail="Authentication backend is not configured. Contact administrator.",
        )

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
