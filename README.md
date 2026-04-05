# ACCOUNT_HUB

A CLI-based identity aggregation tool that allows users to link multiple email accounts (Google, Microsoft, Apple, Meta) and discover all accounts associated with those email addresses in one unified search.
 
---
 
## Overview
 
Account Hub lets you:
- Sign in with a single Account Hub username and password
- Link multiple email addresses from different providers (Gmail, Outlook, iCloud, etc.)
- Authenticate each email address through its respective OAuth provider
- Run a single search that scans across all linked emails to surface any accounts associated with those addresses
 
---
 
## Features
 
- **Unified Login** – One Account Hub account to manage all your linked email identities
- **Multi-Provider OAuth** – Supports Google, Microsoft, Apple, and Meta authentication
- **Multi-Email Linking** – Link as many email addresses as you have across providers
- **Account Discovery** – Searches internal systems and third-party services to find accounts tied to your emails
- **Aggregated Results** – All discovered accounts returned in a single consolidated output (CSV/spreadsheet)
 
---
 
## Tech Stack
 
| Layer | Technology |
|---|---|
| CLI | Python + [Typer](https://typer.tiangolo.com/) or [Click](https://click.palletsprojects.com/) |
| OAuth / Auth | [Authlib](https://authlib.org/) |
| Backend API | FastAPI |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| HTTP Requests | `requests` / `httpx` |
 
---
 
## OAuth Providers
 
- Google (Gmail)
- Microsoft (Outlook / Hotmail)
- Apple (iCloud)
- Meta (Facebook)
 
---
 
## Project Structure
 
```
account-hub/
├── cli/                    # CLI commands and entry points
│   └── main.py
├── auth/                   # OAuth flows for each provider
│   ├── google.py
│   ├── microsoft.py
│   ├── apple.py
│   └── meta.py
├── db/                     # Database models and queries
│   ├── models.py
│   └── session.py
├── discovery/              # Account discovery logic
│   └── scanner.py
├── api/                    # FastAPI backend (optional layer)
│   └── routes.py
├── output/                 # Result formatting and export
│   └── exporter.py
├── config.py               # App configuration and environment variables
├── requirements.txt
└── README.md
```
 
---
 
## Getting Started
 
### Prerequisites
 
- Python 3.11+
- PostgreSQL
- OAuth app credentials for each provider (Google, Microsoft, Apple, Meta)
 
### Installation
 
```bash
git clone https://github.com/your-org/account-hub.git
cd account-hub
pip install -r requirements.txt
```
 
### Environment Variables
 
Create a `.env` file in the root directory:
 
```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/accounthub
 
# Google OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
 
# Microsoft OAuth
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
 
# Apple OAuth
APPLE_CLIENT_ID=
APPLE_CLIENT_SECRET=
 
# Meta OAuth
META_CLIENT_ID=
META_CLIENT_SECRET=
 
# App
SECRET_KEY=your-secret-key
```
 
### Usage
 
```bash
# Create your Account Hub account
python -m cli.main register
 
# Log in to Account Hub
python -m cli.main login
 
# Link an email address
python -m cli.main link-email
 
# Run an account discovery search
python -m cli.main search
 
# Export results to spreadsheet
python -m cli.main export --format csv
```
 
---
 
## Roadmap
 
- [ ] OAuth integration with Google, Microsoft, Apple, Meta
- [ ] Multi-email linking
- [ ] Internal account discovery
- [ ] Third-party service scanning
- [ ] Aggregated CSV/spreadsheet export
- [ ] FastAPI backend layer
- [ ] Web UI (future)
 
---
 
## Contributing
 
This project is in early development. More contribution guidelines coming soon.
 
---
 
## License
 
TBD
