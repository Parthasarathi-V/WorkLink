# WorkLink: verified hyperlocal part-time work platform (MVP)

A Django implementation of the WorkLink Project Specification v1.0. It is a **demo/MVP with test data, not a live service**.
No paid APIs, SMS or payment gateway are used. Matching is rule-based (not AI).

## Quick start

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

python manage.py makemigrations accounts notifications jobs applications trust
python manage.py migrate
python manage.py seed_demo        # demo admin, workers, businesses, jobs (local only)
python manage.py runserver
```
Open http://127.0.0.1:8000/. Bootstrap loads from a CDN, so you need an internet connection in the browser.

Run checks and tests:

```bash
python manage.py check
python manage.py test
```

## Demo accounts (created by `seed_demo`, local only)

| Role | Username | Password |
|---|---|---|
| Admin / coordinator | `admin` | `admin12345` |
| Worker (approved) | `asha`, `ravi` | `demo12345` |
| Worker (not verified) | `neha` | `demo12345` |
| Business (approved) | `chaipoint`, `quickprint` | `demo12345` |
| Business (pending) | `newmart` | `demo12345` |

## Demo script (the spec's first milestone)

1. Log in as `chaipoint`: Manage jobs, then publish or view a listing.
2. Log in as `asha`: browse Jobs (sort by "Best match"), open a job, **Apply**.
3. As `chaipoint`: open the applicants, shortlist, then **Selected**.
4. As `asha`: open the application and **Accept**.
5. After the worker "starts", both `asha` and `chaipoint` click **Confirm joining**. A placement and fee record (free placement) appear.
6. Check status history, in-site notifications, messages (phone numbers are blocked), complaints, reviews.
7. As `admin` (/admin/): approve verification submissions, moderate jobs/reviews, resolve complaints, handle disputed joinings, update fee and protection cases, view the Audit events.

## Where each spec module lives

| Spec module | App / file |
|---|---|
| Auth, roles, profiles, verification | `accounts/` (models, forms, views, admin) |
| Jobs, search, rule-based matching | `jobs/` (`matching.py` has the weights) |
| Applications, status history, joining, placements, fees, protection | `applications/` (`services.py` holds all workflow rules) |
| Notifications and audit log | `notifications/` |
| Complaints and reviews | `trust/` |
| Admin dashboard | Django admin (per-app `admin.py`) |

## Business policy configuration

All in `config/settings.py` under `WORKLINK`: free placements (3), protection days (14), proposed refund percent (75, recorded only),
default fee (0, undecided), whether workers must be verified before applying, public browsing, upload size limit.
**Fee, refund and eligibility terms are proposals and need review before real-world use.**

## Privacy and security notes

- Verification files are stored in `private_uploads/` (not served publicly) and are only downloadable by the owner or staff (staff access is audit-logged).
- Uploads are limited to PDF/PNG/JPG, 5 MB, checked by extension and file signature, and saved under generated names.
- Phones and addresses are never shown to the other party; messages/notes/reviews block phone numbers and emails (a heuristic, not a guarantee).
- Every view checks login, role and object ownership. All status changes are validated server-side inside transactions.
- Before any public deployment: set `WORKLINK_DEBUG=0`, `WORKLINK_SECRET_KEY`, `WORKLINK_ALLOWED_HOSTS`, use HTTPS, secure cookies, a production database,
  rate limiting, backups, file scanning, and a data-retention policy.

## Not included (per spec)

Payments, AI matching, accommodation listings, SMS/email delivery, identity-verification providers, native apps.
