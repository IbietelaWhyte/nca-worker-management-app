# Production SMTP setup

The forgot/reset-password flow (and Supabase confirmation emails generally) only *deliver* mail if
Supabase is wired to a real SMTP provider. **Locally nothing is needed** — Supabase captures all
auth emails in Inbucket (`http://127.0.0.1:54324`). **In production** you must configure custom
SMTP, or reset links never reach users (Supabase's built-in sender is rate-limited and "for
testing only").

This guide's primary path is **Gmail SMTP**, which lets you start **without owning a domain**.
A section at the end covers upgrading to **Resend + a verified domain** when you want branded
`no-reply@yourchurch.org` addresses and higher volume.

> **Why not just point Resend/SendGrid at my `@gmail` address?** You can't. Third-party relays
> require a domain you prove you own via DNS, and you can't add DNS records to `gmail.com`. Gmail
> (and Yahoo) now enforce DMARC, so any outside relay sending *as* `you@gmail.com` is treated as
> spoofing and gets rejected or spam-foldered. The only legitimate way to send from a Gmail
> address is through **Gmail's own SMTP**, authenticating as that mailbox — which is exactly what
> this guide does.

---

# Option A — Gmail SMTP (no domain required)

Good for getting started and for low volume like password resets. Limits: **~500 emails/day** on a
free Gmail account (~2,000/day on Google Workspace). Emails arrive *from your personal address*
(no custom branding, and Gmail may show "via gmail.com").

## 1. Enable 2-Step Verification
App Passwords require it. Google Account → **Security → 2-Step Verification** → turn it on.

## 2. Create an App Password
Google Account → **Security → 2-Step Verification → App passwords** → create one (name it e.g.
`supabase-smtp`). Google shows a **16-character** password once — copy it. Store it as a secret
(e.g. `GMAIL_APP_PASSWORD`); never commit it. This is **not** your normal Google password.

## 3. SMTP credentials to use

| Field        | Value                                            |
|--------------|--------------------------------------------------|
| Host         | `smtp.gmail.com`                                 |
| Port         | `587` (STARTTLS; `465` for SSL also works)       |
| Username     | your full Gmail address, e.g. `you@gmail.com`    |
| Password     | the 16-char **App Password** from step 2         |
| Sender email | your Gmail address (must match the username)     |
| Sender name  | e.g. `NCA Worker Management`                      |

## 4. Configure Supabase

### Hosted Supabase project (production)
1. Supabase dashboard → **Project Settings → Authentication → SMTP Settings**.
2. Enable **Custom SMTP** and fill in the table above. Save.
3. Dashboard → **Authentication → URL Configuration**:
   - **Site URL**: `https://nca-worker-management-app.vercel.app`
   - **Redirect URLs**: add `https://nca-worker-management-app.vercel.app/reset-password`
     (a wildcard like `https://nca-worker-management-app.vercel.app/**` also covers it).

### Local / self-hosted via `supabase/config.toml`
The `[auth.email.smtp]` block configures local/self-hosted SMTP (the App Password comes from the
environment, never hard-coded):

```toml
[auth.email.smtp]
enabled = true
host = "smtp.gmail.com"
port = 587
user = "you@gmail.com"
pass = "env(GMAIL_APP_PASSWORD)"
admin_email = "you@gmail.com"
sender_name = "NCA Worker Management"
```

Export the secret before `supabase start`: `export GMAIL_APP_PASSWORD=your16charapppassword`.
Note: while this block is `enabled = true`, local emails are sent for real via Gmail and are **no
longer captured by Inbucket**. For normal local development set `enabled = false` (or comment the
block) so Inbucket keeps intercepting mail at `http://127.0.0.1:54324`.

## 5. Test it
1. In production, go to the login page → **Forgot password?** → submit your address.
2. Confirm the email arrives.
3. Click the link → you land on `/reset-password` → set a new password → sign in with it.

## Troubleshooting — `500` on `/auth/v1/recover`
A 500 from `/recover` means the email failed to send. Check **Dashboard → Logs → Auth Logs** for
the exact reason:
- **"Username and Password not accepted"** → you used your normal Google password instead of an
  App Password, or 2-Step Verification isn't enabled. Enable 2FA and regenerate the App Password.
- **Daily limit reached** → free Gmail caps ~500 sends/day; wait, or move to Option B.
- **Connection/TLS errors** → re-check host `smtp.gmail.com` and port (`587` STARTTLS / `465` SSL).

---

# Option B — Resend + a verified domain (upgrade path)

When you want branded sender addresses (`no-reply@yourchurch.org`), better deliverability, and
higher volume, switch to a transactional provider. Resend has a real free tier (~3,000 emails/mo,
100/day, 1 domain). This requires a domain you control (cheap domains are ~$1–12/yr).

1. **Create an API key**: Resend dashboard → **API Keys → Create API Key** (Sending access). Copy
   it once; store as a secret `RESEND_API_KEY`, never commit.
2. **Add & verify your domain**: Resend → **Domains → Add Domain** → add the generated DNS records
   to your domain (SPF `TXT` + an `MX` feedback record, DKIM `TXT`, optional DMARC) → **Verify DNS
   Records**. DNS can take a while to propagate. (`onboarding@resend.dev` exists for a quick test
   but only delivers to your own Resend account email — a verified domain is needed for real
   users.)
3. **SMTP credentials**:

   | Field        | Value                                                   |
   |--------------|---------------------------------------------------------|
   | Host         | `smtp.resend.com`                                       |
   | Port         | `587` (STARTTLS; `465`/`2465` for SSL)                  |
   | Username     | `resend` *(the literal word)*                           |
   | Password     | your Resend API key (`re_…`)                            |
   | Sender email | an address on your **verified domain**                  |
   | Sender name  | e.g. `NCA Worker Management`                             |

4. **Configure Supabase**: same as Option A step 4 (dashboard SMTP settings + URL configuration),
   using the Resend values above. For `config.toml`, use `host = "smtp.resend.com"`,
   `user = "resend"`, `pass = "env(RESEND_API_KEY)"`.

### Troubleshooting (Resend)
- **`500` on `/recover` / "does not match a verified Sender Identity"** → the From address isn't on
  a verified domain, or the domain isn't verified yet. Finish domain verification and use a sender
  on that domain.
- **`401`/auth errors** → wrong API key, or the `RESEND_API_KEY` env var isn't set. Check Resend →
  **Logs/Emails** for the delivery/bounce event.
