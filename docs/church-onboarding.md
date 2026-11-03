# Church onboarding checklist

Everything needed to move the app from **a pilot in one department, running on the maintainer's
personal accounts** to **church-owned and church-wide**. The work in the repo is done. What is
left is accounts, DNS and people.

Progress is tracked in GitHub issue #112, *Church integration checklist*. Tick it there as well as
here.

The common thread: nothing the church depends on should stop working because one person is
unavailable. Every account below gets a church-owned login and at least two admins.

## 1. Email from the church's domain

The app's emails (invites, password resets) go out from a personal Gmail today. See
[smtp-setup.md](smtp-setup.md) for how the switch works.

| | Step | Who |
|---|---|---|
| ☐ | Find the church's Microsoft 365 / DNS administrator and agree a subdomain for app mail, e.g. `notify.<church domain>` | Maintainer + church |
| ☐ | Create the Resend account under a **church-owned** address, not a personal one, and add a second admin | Church |
| ☐ | Add `notify.<church domain>` in Resend and hand the DNS records (SPF, DKIM, MX, all on the subdomain) to the DNS administrator. The root domain's M365 records are not touched | Maintainer |
| ☐ | DNS administrator adds the records; wait for Resend to show the domain **Verified** | Church |
| ☐ | Confirm the root domain has a DMARC record (`_dmarc`); if not, add `p=none` with a reporting address to start | Church |
| ☐ | Create a **sending-only** Resend API key scoped to that domain; store it in the church's password manager and in `supabase/.env` | Maintainer |
| ☐ | Choose the sender (e.g. `no-reply@notify.<church domain>`) and a monitored M365 mailbox for replies | Church |
| ☐ | `EMAIL_PROVIDER=resend just smtp-apply`, then send yourself an invite and a password reset. Check that both arrive in the inbox, not spam, and that the headers show SPF, DKIM and DMARC `pass` | Maintainer |
| ☐ | Watch Resend's logs through the first real invites. To roll back: `EMAIL_PROVIDER=gmail just smtp-apply` | Maintainer |
| ☐ | **Only after Resend has been live and clean for a while:** revoke the Gmail App Password, remove `GMAIL_*` from `supabase/.env`, and decide whether to drop the Gmail entry from `scripts/auth_email.py` | Maintainer |

## 2. Ownership of the other accounts

| | Account | Used for | Who |
|---|---|---|---|
| ☐ | Supabase organisation | Database, sign-in, auth email settings | Church + maintainer |
| ☐ | Vercel | Frontend hosting | Church + maintainer |
| ☐ | Railway | Backend hosting | Church + maintainer |
| ☐ | Twilio | Text messages (and billing) | Church + maintainer |
| ☐ | GitHub repository | Code, issues, in-app feedback | Church + maintainer |
| ☐ | Password manager | A shared vault for all of the above | Church |

For each one: move it to (or invite) a church-owned login, make sure at least two people are
admins, and put billing on a church payment method.

## 3. Texts

| | Step | Who |
|---|---|---|
| ☐ | Confirm which number or sender ID the church wants texts to come from, and that the Twilio account is registered for it | Church + maintainer |

## 4. Rolling out beyond the pilot

| | Step | Who |
|---|---|---|
| ☐ | Create each department, and invite its head and assistant heads from the Workers page (they choose their own passwords) | Admin |
| ☐ | Heads import their rosters by CSV (`worker-import-sample.csv` on the import dialog) | Heads |
| ☐ | Heads send the first availability request to their department | Heads |
| ☐ | Point people at the Help page for how availability, rotas and texts work | Admin |

## 5. Later

| | Step |
|---|---|
| ☐ | Two-factor sign-in for administrators, and signing in with church Microsoft 365 accounts for staff: tracked in issue #111 |
