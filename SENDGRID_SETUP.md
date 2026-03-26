# SendGrid Email Setup Guide for WoundSync

## ✅ What's Already Done

The code is ready! I've added:
- ✅ Email service (`backend/app/email_service.py`)
- ✅ Password reset endpoint (`/auth/request-password-reset`)
- ✅ Beautiful HTML email templates
- ✅ SendGrid package installed

## 🚀 Steps to Complete Setup

### Step 1: Get Your SendGrid API Key

1. Go to https://signup.sendgrid.com/ and create a free account
2. Verify your email address
3. In SendGrid dashboard, go to **Settings → API Keys**
4. Click **"Create API Key"**
5. Name it: `WoundSync Password Reset`
6. Choose **"Restricted Access"**
7. Under **Mail Send**, toggle it to **"Full Access"**
8. Click **"Create & View"**
9. **COPY THE API KEY** (you won't see it again!)

### Step 2: Verify Your Sender Email

1. In SendGrid, go to **Settings → Sender Authentication**
2. Click **"Verify a Single Sender"**
3. Fill in:
   - **From Name**: `WoundSync`
   - **From Email**: Your email (e.g., `your.email@gmail.com`)
   - **Reply To**: Same email
   - Company details (can be minimal)
4. Click **"Create"**
5. **Check your email** and click the verification link

### Step 3: Update Your `.env` File

Open `backend/.env` and replace these values:

```env
SENDGRID_API_KEY=SG.your_actual_api_key_here
SENDGRID_FROM_EMAIL=your.verified.email@gmail.com
SENDGRID_FROM_NAME=WoundSync
```

### Step 4: Restart the Backend Server

The server should auto-reload, but if not:
1. Stop the backend server (Ctrl+C in the terminal)
2. Start it again: `python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

### Step 5: Test It!

1. Go to your login page: http://localhost:3000
2. Click **"Forgot Password?"**
3. Enter your email
4. Check your inbox (and spam folder!)
5. You should receive a beautiful password reset email

## 📧 Email Features

Your password reset emails include:
- ✨ Beautiful, professional design
- 📱 Mobile-responsive layout
- 🔒 Secure reset links that expire in 1 hour
- 📝 Plain text fallback for email clients that don't support HTML
- 🎨 Branded with WoundSync colors

## 🎁 Bonus: Welcome Emails

I also added a welcome email function! You can call it when users sign up:

```python
from app.email_service import email_service

# Send welcome email to new users
email_service.send_welcome_email(
    to_email="user@example.com",
    user_name="John"  # Optional
)
```

## 🔍 Troubleshooting

### Email not arriving?
1. Check spam folder
2. Verify sender email is verified in SendGrid
3. Check SendGrid dashboard → Activity for delivery status
4. Make sure API key has "Mail Send" permission

### "Email service not configured" error?
1. Make sure `SENDGRID_API_KEY` is set in `backend/.env`
2. Restart the backend server
3. Check backend logs for "Email service loaded successfully"

### SendGrid free tier limits?
- 100 emails per day (plenty for password resets!)
- If you need more, upgrade to paid plan (very affordable)

## 📊 Monitor Email Delivery

Check SendGrid dashboard:
- **Activity** tab shows all sent emails
- **Statistics** shows delivery rates
- **Suppressions** shows bounced/blocked emails

## 🎉 You're All Set!

Once you complete these steps, your password reset emails will work perfectly!

Questions? Check the SendGrid docs: https://docs.sendgrid.com/
