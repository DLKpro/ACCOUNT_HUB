# AccountHub Legal Pages — Deployment Guide

Serves the Terms of Service and Privacy Policy at:
- `AccountHub.dlopro.ca/terms`
- `AccountHub.dlopro.ca/privacy`

## Prerequisites

1. Install Node.js (v18+)
2. Install Wrangler: `npm install -g wrangler`
3. Authenticate: `wrangler login`

## DNS Setup (one-time)

In your Cloudflare dashboard for `dlopro.ca`, ensure you have a DNS record for `AccountHub.dlopro.ca` (e.g., an AAAA record pointing to `100::` with Proxy enabled, or a CNAME).

## Deploy

```bash
cd accounthub-legal-site
npm install
npm run deploy
```

## Local Development

```bash
npm install
npm run dev
```

Then visit `http://localhost:8787/terms` or `http://localhost:8787/privacy`.

## Updating Content

Edit the HTML within `src/worker.js` (the `TERMS_HTML` and `PRIVACY_HTML` template literals), then re-deploy.

Standalone HTML files are also available in the parent folder (`terms.html`, `privacy.html`) for reference.
