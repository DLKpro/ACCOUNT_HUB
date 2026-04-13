# Account Hub

A CLI-based identity aggregation tool that allows users to link multiple email accounts (Google, Microsoft, Apple, Meta), discover all accounts associated with those email addresses, and request closure of discovered accounts.

---

## Overview

Account Hub lets you:
- Sign in with a single Account Hub username and password
- Link multiple email addresses via OAuth (Gmail, Outlook, iCloud, Facebook)
- Run a single search that scans across all linked emails to find associated accounts
- Request closure of discovered accounts with guided deletion instructions
- Export results to CSV
- Delete your Account Hub account and all stored data

---

## Features

- **Unified Login** -- One Account Hub account to manage all your linked email identities
- **Multi-Provider OAuth** -- Google (loopback redirect), Microsoft (device code flow), Apple (JWT client secret), Meta (loopback redirect)
- **Multi-Email Linking** -- Link as many email addresses as you have across providers
- **Account Discovery** -- Pluggable scanner architecture with OAuth profile detection and Have I Been Pwned breach lookups
- **Account Closure** -- Tiered deletion system: API-based, web link, email request, or manual. Includes a registry of 20+ services with deletion URLs and difficulty ratings
- **CSV Export** -- Export all discovered accounts to spreadsheet
- **Account Self-Deletion** -- Permanently delete your Account Hub account with cascading purge of all data

---

## Tech Stack

| Layer | Technology |
|---|---|
| CLI | Python + [Typer](https://typer.tiangolo.com/) (with Rich) |
| Backend API | [FastAPI](https://fastapi.tiangolo.com/) |
| Database | PostgreSQL |
| ORM | SQLAlchemy 2.0 (async, with asyncpg) |
| Migrations | Alembic |
| OAuth | [Authlib](https://authlib.org/) |
| HTTP Client | httpx (async) |
| Auth | bcrypt (passlib) + JWT (python-jose) |
| Token Encryption | Fernet (cryptography) |
| Config | pydantic-settings |

---

## Project Structure

```
account_hub/
  config.py                       # Pydantic Settings (env-driven config)
  cli/
    main.py                       # Typer app entry point
    auth_commands.py              # register, login, logout, me
    email_commands.py             # link, list, unlink
    search_commands.py            # run, results, history, export
    close_commands.py             # request, complete, list, info, delete-account
    helpers.py                    # Credential file I/O, API client
  api/
    main.py                       # FastAPI app factory
    dependencies.py               # get_db, get_current_user
    routers/
      auth.py                     # /auth/register, login, refresh, me, delete
      emails.py                   # /emails (list, delete)
      oauth.py                    # /oauth/initiate, callback, poll
      search.py                   # /search (create, detail, history, export)
      accounts.py                 # /accounts/close, close-requests, close-info
  db/
    base.py                       # Async engine + session factory
    models.py                     # User, LinkedEmail, OAuthState, ScanSession,
                                  # DiscoveredAccount, ClosureRequest
    migrations/                   # Alembic
  services/
    user_service.py               # Registration, authentication, account deletion
    oauth_service.py              # OAuth flow orchestration (loopback + device code)
    email_service.py              # Linked email CRUD with token revocation
    discovery_service.py          # Scanner orchestration
    export_service.py             # CSV generation
    closure_service.py            # Account closure lifecycle
  oauth/
    providers.py                  # Provider registry + OAuthProviderConfig
    google.py / microsoft.py / apple.py / meta.py
  security/
    hashing.py                    # bcrypt password hashing
    jwt.py                        # JWT access/refresh token management
    encryption.py                 # Fernet encryption for OAuth tokens at rest
  discovery/
    base.py                       # Abstract BaseScanner
    oauth_profile.py              # Confirms provider accounts for linked emails
    hibp.py                       # Have I Been Pwned breach lookups
    gravatar.py                   # Gravatar profile detection
  data/
    deletion_registry.json        # Service deletion URLs and instructions
tests/                            # 164+ tests (unit + integration)
```

---

## Getting Started

### Prerequisites

- Python 3.9+
- PostgreSQL
- OAuth app credentials for each provider (Google, Microsoft, Apple, Meta)

### Installation

```bash
git clone https://github.com/DLKpro/ACCOUNT_HUB.git
cd ACCOUNT_HUB
pip install -e ".[dev]"
```

### Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

### Database Setup

```bash
alembic upgrade head
```

### Usage

```bash
# Start the API server
accounthub server

# Create your account
accounthub auth register

# Log in
accounthub auth login

# Link an email address
accounthub email link google

# Run an account discovery scan
accounthub search run

# View scan results
accounthub search results

# Export results to CSV
accounthub search export -o results.csv

# Request closure of a discovered account
accounthub close request <account-id>

# Look up deletion instructions for a service
accounthub close info Twitter

# Delete your Account Hub account
accounthub close delete-account
```

### Running Tests

```bash
pytest tests/ -v
```

---

## Security

- **Passwords**: bcrypt hashed, never stored in plaintext
- **OAuth tokens at rest**: Fernet encrypted (AES-128-CBC + HMAC)
- **JWTs**: HS256 signed, type claim prevents token confusion
- **OAuth state**: Cryptographically random, single-use, 10 min TTL
- **Credential file**: `~/.accounthub/credentials.json` with 0600 permissions
- **Rate limiting**: slowapi on auth and search endpoints
- **Token revocation**: OAuth tokens revoked with provider on email unlink

---

## Roadmap

- [x] Multi-provider OAuth (Google, Microsoft, Apple, Meta)
- [x] Multi-email linking
- [x] Account discovery (OAuth profile + HIBP breaches)
- [x] CSV export
- [x] Account closure system with deletion registry
- [x] Account self-deletion
- [ ] Web UI
- [ ] Additional discovery scanners
- [ ] Expand deletion registry

---

## License

TBD
