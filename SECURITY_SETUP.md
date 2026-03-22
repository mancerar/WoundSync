# WoundSync Secret & Auth Hardening

## What was changed in code

- Removed committed Firebase Admin key file from `backend/app/firebase-service-account.json`.
- Backend now loads Firebase Admin credentials from environment variables only:
  - `FIREBASE_SERVICE_ACCOUNT_PATH` (preferred)
  - `FIREBASE_SERVICE_ACCOUNT_JSON` (alternative)
- Backend no longer silently skips auth unless explicitly allowed.
  - Set `ALLOW_ANON_AUTH=true` only for local testing.
- Added safe templates:
  - `backend/.env.example`
  - `ui/.env.example`
- Added stronger gitignore patterns for Firebase service account files.

## Manual steps you must do now (outside code)

1. Rotate Firebase Admin service-account key in Google Cloud / Firebase Console.
2. Rotate AWS IAM access key pair used by backend.
3. Disable/delete old compromised keys immediately.

## Local setup (safe)

### Backend (`backend/.env`)

Copy `backend/.env.example` to `backend/.env` and set:

- `FIREBASE_SERVICE_ACCOUNT_PATH=<absolute path to NEW service-account json>`
- `AWS_ACCESS_KEY_ID=<new key id>`
- `AWS_SECRET_ACCESS_KEY=<new secret>`
- `AWS_REGION`, `S3_BUCKET`
- Optional: `QWEN_VL_API_KEY`

### UI (`ui/.env.local`)

Use only public frontend vars:

- `NEXT_PUBLIC_FIREBASE_*`
- `NEXT_PUBLIC_BACKEND_URL`
- `NEXT_PUBLIC_PASSWORD_RESET_URL`

Do **not** put AWS keys or Firebase Admin service-account JSON in UI env.

## Notes

- Passwords are managed by Firebase Auth; never store plaintext passwords in backend DB.
- Backend stores app data keyed by verified Firebase UID.
