# Production SMTP setup — Twilio SendGrid

The forgot/reset-password flow (and Supabase confirmation emails generally) only *deliver* mail
if Supabase is wired to a real SMTP provider. **Locally nothing is needed** — Supabase captures
all auth emails in Inbucket (`http://127.0.0.1:54324`). **In production** you must configure
custom SMTP, or reset links never reach users (Supabase's built-in sender is rate-limited and
"for testing only").

This guide uses **Twilio SendGrid** (Twilio's email product; Supabase talks to it over SMTP).

---

## 1. Prerequisites
- A Twilio SendGrid account (sign up at sendgrid.com or via the Twilio console).
- Access to your production domain's DNS (for domain authentication — strongly recommended for
  deliverability so reset emails don't land in spam).

## 2. Create a SendGrid API key
1. SendGrid dashboard → **Settings → API Keys → Create API Key**.
2. Name it (e.g. `supabase-auth-smtp`).
3. Choose **Restricted Access** and grant **Mail Send → Full Access** (nothing else needed).
4. Create and **copy the key now** — it's shown only once. Store it as a secret
   (e.g. `SENDGRID_API_KEY`), never commit it.

## 3. Verify your sender identity
Pick one (domain authentication is better for deliverability):
- **Domain Authentication** (recommended): SendGrid → **Settings → Sender Authentication →
  Authenticate Your Domain**. Add the CNAME records SendGrid gives you to your DNS, then verify.
  You can then send as any address on that domain (e.g. `no-reply@yourchurch.org`).
- **Single Sender Verification** (quick start): SendGrid → **Settings → Sender Authentication →
  Verify a Single Sender**. Confirm the address via the email SendGrid sends. Limited but fine
  to start.

## 4. SMTP credentials to use
SendGrid's SMTP relay is the same for everyone — only the password (your API key) is secret:

| Field        | Value                                  |
|--------------|----------------------------------------|
| Host         | `smtp.sendgrid.net`                    |
| Port         | `587` (STARTTLS; `465` for SSL works too) |
| Username     | `apikey` *(the literal word, not your key)* |
| Password     | your SendGrid API key from step 2      |
| Sender email | a verified sender from step 3 (e.g. `no-reply@yourchurch.org`) |
| Sender name  | e.g. `NCA Worker Management`           |

## 5. Configure Supabase

### Hosted Supabase project (production)
1. Supabase dashboard → **Project Settings → Authentication → SMTP Settings**.
2. Toggle **Enable Custom SMTP** and fill in the table above. Save.
3. Dashboard → **Authentication → URL Configuration**:
   - **Site URL**: your deployed frontend origin, e.g. `https://app.yourchurch.org`.
   - **Redirect URLs**: add the reset target — `https://app.yourchurch.org/reset-password`
     (a wildcard like `https://app.yourchurch.org/**` also covers it). This is the production
     analogue of the local `additional_redirect_urls` we set in `supabase/config.toml`.

### Local / self-hosted via `supabase/config.toml`
Uncomment and fill the `[auth.email.smtp]` block (the API key comes from the environment, never
hard-coded):

```toml
[auth.email.smtp]
enabled = true
host = "smtp.sendgrid.net"
port = 587
user = "apikey"
pass = "env(SENDGRID_API_KEY)"
admin_email = "no-reply@yourchurch.org"
sender_name = "NCA Worker Management"
```

Export the secret before `supabase start` / deploy: `export SENDGRID_API_KEY=SG.xxxxx`.
Note: enabling custom SMTP here means emails are *actually sent* and no longer captured by
Inbucket — keep it commented out for normal local development.

## 6. Optional — email template & rate limit
- **Template**: Dashboard → **Authentication → Email Templates → Reset Password**. Customize copy;
  keep the `{{ .ConfirmationURL }}` variable — that's the link pointing at `/reset-password`.
- **Rate limit**: Dashboard → **Authentication → Rate Limits** (or `[auth.rate_limit] email_sent`
  in `config.toml`) — raise above the default if you expect more reset/confirmation emails per
  hour. (We bumped the local value to 30 for testing.)

## 7. Test it
1. In production, go to the login page → **Forgot password?** → submit a real address.
2. Confirm the email arrives (check spam on first sends until domain auth propagates).
3. Click the link → you land on `/reset-password` → set a new password → sign in with it.

## Troubleshooting
- **"redirect_to is not allowed"**: the reset URL isn't in Site URL / Redirect URLs — add the
  exact origin + `/reset-password` (or a `/**` wildcard).
- **No email arrives**: sender not verified (step 3), API key lacks Mail Send permission, or the
  key/password is wrong. Check SendGrid → **Activity Feed** for delivery/bounce events.
- **Link says invalid/expired**: the recovery token expired (`otp_expiry`, default 1h) or was
  already used — request a fresh one.
- **Emails land in spam**: complete Domain Authentication (step 3) rather than single-sender.
