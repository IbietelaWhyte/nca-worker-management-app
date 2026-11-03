# Auth email setup

Supabase sends this app's two emails itself: the **invite** an admin triggers when giving
somebody a login, and the **password reset** from "Forgot password?" on the sign-in page. The
backend sends no email of any kind. What reaches people therefore depends on Supabase's SMTP
settings, its templates, and its link expiry, all three of which are kept in this repo and
applied to production with one command.

**Locally nothing is needed.** The stack captures every auth email in Mailpit at
`http://127.0.0.1:54324`, using the same templates production does.

## How the switch works

One variable, `EMAIL_PROVIDER`, chooses which SMTP server Supabase sends through:

| `EMAIL_PROVIDER` | Status                                              | Sends from                     |
|------------------|-----------------------------------------------------|--------------------------------|
| `gmail`          | **Current**, while the app is piloted by one department | the maintainer's Gmail address |
| `resend`         | Ready, waiting on the church domain (see [church-onboarding.md](church-onboarding.md)) | `no-reply@notify.<church domain>` |

1. `cp supabase/.env.example supabase/.env` and fill it in. It is gitignored. It holds the provider
   credentials and a Supabase personal access token, and nothing in it is read by the backend.
2. `just smtp-apply --dry-run` prints what would change, and sends nothing.
3. `just smtp-apply` applies it to the production project through the Supabase Management API:
   - the chosen provider's SMTP host, user, password, sender address and sender name
   - the invite and recovery **templates and subjects**, read from `supabase/templates/` and
     the `[auth.email.template.*]` blocks in `supabase/config.toml`
   - the link expiry (`otp_expiry` in `config.toml`, 24 hours)

   A real environment variable beats the file, so `EMAIL_PROVIDER=resend just smtp-apply` switches
   without editing it, and `EMAIL_PROVIDER=gmail just smtp-apply` switches back.

**Edit templates in the repo, never in the dashboard.** The next `just smtp-apply` overwrites
whatever the dashboard holds.

### Testing real delivery from the local stack

`eval "$(just smtp-env)"` exports `SMTP_*` for the chosen provider, which the `env(SMTP_*)`
values in `config.toml`'s `[auth.email.smtp]` block read. Set that block's `enabled = true` and
restart (`just db-stop && just db-start`). Mail then goes out for real and stops appearing in
Mailpit. Set it back to `false` when done.

## Once per project, by hand

These are not covered by `just smtp-apply`:

- **Authentication → URL Configuration.** Site URL is the deployed frontend
  (`https://nca-worker-management-app.vercel.app`). Redirect URLs must include
  `https://nca-worker-management-app.vercel.app/reset-password`, or a wildcard covering it. Invite
  and reset links both land there, and a URL not on the list sends people to the site root
  instead.
- **Authentication → Sign In / Providers.** Email signups off: accounts are created only by an
  admin's invite.
- **Authentication → Policies → Password.** At least 10 characters, with lowercase, uppercase,
  digits and symbols. This matches `supabase/config.toml` and `frontend/src/lib/password.js`;
  change all three together.

---

## Gmail (current provider)

Fine for a pilot: about 500 emails a day on a free account. The drawback is that mail arrives from a
personal address, and it stops if that one person's Google account changes.

1. Turn on **2-Step Verification** on the Google account. App Passwords require it.
2. **Security → 2-Step Verification → App passwords.** Create one (e.g. `supabase-smtp`) and
   copy the 16 characters. This is not the account password.
3. In `supabase/.env`: `EMAIL_PROVIDER=gmail`, `GMAIL_SMTP_USER=<the address>`,
   `GMAIL_APP_PASSWORD=<the 16 characters>`. Gmail only sends as the mailbox that signs in, so
   that address is also the sender.

> **Why not point Resend at the Gmail address?** It can't be done. Relays need a domain whose DNS
> you control, and Gmail enforces DMARC, so anyone else sending *as* `you@gmail.com` is treated as
> spoofing.

## Resend (target provider)

Resend sends from the church's own domain, so the mail is branded, authenticated against the
church's DNS, and not tied to any one person.

1. **Verify a subdomain, not the root.** In Resend, add `notify.<church domain>`. Its SPF (`TXT`),
   DKIM (`TXT`) and bounce `MX` records go on the subdomain only, so the root domain's Microsoft 365
   `MX` and SPF records are untouched, and M365's SPF lookup budget is unaffected. The church's
   DNS administrator adds them; [church-onboarding.md](church-onboarding.md) tracks this.
2. **DMARC.** Make sure the root domain has a `_dmarc` record (start with `p=none` and a reporting
   address). It applies to the subdomain too.
3. **API key.** Create a *sending-only* key scoped to that domain.
4. In `supabase/.env`: `EMAIL_PROVIDER=resend`, `RESEND_API_KEY=re_...`,
   `RESEND_SENDER_EMAIL=no-reply@notify.<church domain>`. Then run `just smtp-apply`.

| Field    | Value                         |
|----------|-------------------------------|
| Host     | `smtp.resend.com`, port `587` |
| Username | `resend` (the literal word)   |
| Password | the API key                   |
| Sender   | an address on the verified domain |

---

## Troubleshooting

**A `500` from `/auth/v1/invite` or `/auth/v1/recover`** means the email failed to send. The admin
sees "Failed to send the invite email". **Dashboard → Logs → Auth** gives the reason:

- **"Username and Password not accepted"** (Gmail): the account password was used instead of an
  App Password, or 2-Step Verification is off.
- **"does not match a verified Sender Identity"** (Resend): the sender is not on the verified
  domain, or verification has not finished.
- **Daily limit reached** (Gmail): wait, or move to Resend.
- **Connection or TLS errors**: check the host and port `587`.

**An invite link says "invalid or has expired".** The links last 24 hours and work once. The
admin uses **Resend invite** in the worker's menu on the Workers page. Once somebody has set a
password, resending is refused and they use "Forgot password?" instead.

**`just smtp-apply` fails with 401.** The personal access token is wrong or revoked; create one
at https://supabase.com/dashboard/account/tokens.
