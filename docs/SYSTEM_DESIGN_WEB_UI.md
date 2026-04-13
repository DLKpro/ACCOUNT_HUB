# System Design: Account Hub Web UI

**Status:** Proposed
**Date:** 2026-04-13
**Author:** System design session

---

## 1. Context & Problem

Account Hub is currently CLI-only. Users must run terminal commands to register, link emails via OAuth, run discovery scans, and manage account closures. This limits adoption to technical users comfortable with CLIs.

A web UI will:
- Make Account Hub accessible to non-technical users
- Provide visual dashboards for scan results and closure progress
- Simplify OAuth flows (browser-native instead of loopback servers)
- Enable real-time scan progress feedback

---

## 2. Requirements

### Functional
| Feature | Priority | Notes |
|---------|----------|-------|
| Register / login / logout | P0 | Auth flow with token management |
| Link emails via OAuth | P0 | Google, Microsoft, Apple, Meta |
| Run discovery scans | P0 | Trigger scan, show progress, display results |
| View scan history | P1 | Paginated list of past scans |
| Export scan results to CSV | P1 | Download button |
| Request account closure | P1 | Per-service deletion flow with guided instructions |
| Track closure progress | P1 | Dashboard of pending/completed closures |
| Deletion registry browser | P2 | Search deletion instructions for any service |
| Account settings / delete | P2 | Profile view, danger zone |

### Non-Functional
| Requirement | Target |
|-------------|--------|
| Initial load | < 2s on 3G |
| Auth token refresh | Transparent, no user-visible expiry |
| Accessibility | WCAG 2.1 AA |
| Browser support | Last 2 versions of Chrome, Firefox, Safari, Edge |
| Mobile responsive | Full functionality on 375px+ |

### Constraints
- API already exists at `localhost:8000` with CORS for `localhost:3000`
- OAuth loopback flows need redesign for web (no local HTTP servers)
- No backend changes to core API (additive only)
- Single developer, minimize maintenance burden

---

## 3. High-Level Architecture

```
                    ┌─────────────────────────────┐
                    │        Web Browser           │
                    │                              │
                    │  ┌───────────────────────┐   │
                    │  │   React SPA (Vite)    │   │
                    │  │                       │   │
                    │  │  Pages:               │   │
                    │  │  /login, /register     │   │
                    │  │  /dashboard            │   │
                    │  │  /emails               │   │
                    │  │  /scan/:id             │   │
                    │  │  /closures             │   │
                    │  │  /settings             │   │
                    │  └──────────┬────────────┘   │
                    │             │ HTTP/JSON       │
                    └─────────────┼─────────────────┘
                                  │
                    ┌─────────────┴─────────────────┐
                    │     FastAPI Backend            │
                    │     (existing, minimal changes)│
                    │                                │
                    │  + GET /oauth/web-callback     │
                    │    (new: browser redirect)     │
                    │                                │
                    │  Existing endpoints unchanged  │
                    └───────────────┬────────────────┘
                                    │
                    ┌───────────────┴────────────────┐
                    │     PostgreSQL + Scanners       │
                    │     (unchanged)                 │
                    └────────────────────────────────┘
```

### Key Decision: SPA vs SSR

**Decision: SPA (Single Page Application)**

| Factor | SPA | SSR (Next.js) |
|--------|-----|---------------|
| Complexity | Lower | Higher (server component model) |
| API integration | Direct fetch to existing API | Needs API proxy layer |
| OAuth flows | Browser redirects naturally | Same |
| SEO needs | None (authenticated app) | Unnecessary |
| Deployment | Static files (Cloudflare Pages) | Needs Node.js server |
| Bundle size | ~150KB gzipped | ~200KB+ |

SPA wins because this is a fully authenticated app with no SEO needs, and the API already exists.

---

## 4. Frontend Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Framework | React 19 + TypeScript | Industry standard, strong ecosystem |
| Build tool | Vite | Fast dev server, optimized builds |
| Routing | React Router v7 | Client-side routing, loader patterns |
| State: server | TanStack Query v5 | Cache, refetch, optimistic updates |
| State: client | Zustand | Lightweight auth/UI state |
| UI components | shadcn/ui + Radix | Accessible, composable, unstyled primitives |
| Styling | Tailwind CSS v4 | Utility-first, small bundle |
| Forms | React Hook Form + Zod | Validation, type-safe schemas |
| HTTP client | ky (or fetch wrapper) | Lightweight, interceptors for auth |
| Charts | Recharts | Scan result visualizations |
| Testing | Vitest + Testing Library | Fast unit/integration tests |
| E2E | Playwright | Cross-browser end-to-end |

---

## 5. Page Architecture & Routing

```
/                        → Redirect to /dashboard or /login
/login                   → Login form
/register                → Registration form
/dashboard               → Overview: linked emails, recent scan, closure stats
/emails                  → Linked emails list + link new email button
/emails/link/:provider   → OAuth flow for specific provider
/scan                    → Run new scan + history list
/scan/:id                → Scan detail: results table, export button
/closures                → Closure requests list + request new
/closures/:id            → Closure detail with instructions
/browse                  → Deletion registry browser (public, no auth)
/settings                → Profile, change password, delete account
```

### Layout Structure

```
┌─────────────────────────────────────────────┐
│  Sidebar (desktop) / Header (mobile)        │
│  ┌─────┬───────────────────────────────┐    │
│  │ Nav │  Page Content                  │    │
│  │     │                                │    │
│  │ 🏠  │  [Breadcrumb]                  │    │
│  │ 📧  │                                │    │
│  │ 🔍  │  ┌──────────────────────┐      │    │
│  │ 🗑️  │  │  Main Content Area   │      │    │
│  │ ⚙️  │  │                      │      │    │
│  │     │  └──────────────────────┘      │    │
│  └─────┴───────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

---

## 6. Auth & Token Management

### Token Storage

```typescript
// auth-store.ts (Zustand)
interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
}
```

**Storage**: `localStorage` for refresh token, in-memory for access token.

- Access token (30-min TTL): Stored in Zustand store (memory only)
- Refresh token (7-day TTL): Stored in `localStorage` (survives page reload)
- On app load: attempt silent refresh from stored refresh token

### Auto-Refresh Interceptor

```typescript
// api-client.ts
async function apiFetch(path: string, options?: RequestInit) {
  let response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${authStore.getState().accessToken}`,
      ...options?.headers,
    },
  });

  // Auto-refresh on 401
  if (response.status === 401 && authStore.getState().refreshToken) {
    await authStore.getState().refresh();
    // Retry original request with new token
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${authStore.getState().accessToken}`,
        ...options?.headers,
      },
    });
  }

  return response;
}
```

---

## 7. OAuth Flow Redesign for Web

### Problem
CLI uses loopback HTTP servers on `127.0.0.1:{random_port}`. Browsers can't do this.

### Solution: Web Redirect Flow

Add a single new API endpoint:

```
GET /oauth/web-callback?code=...&state=...
```

This endpoint:
1. Validates the state parameter (same as existing callback)
2. Exchanges the code for tokens (same logic)
3. Redirects the browser to: `http://localhost:3000/emails/link/complete?status=success&email=...`

### Flow Diagram

```
Browser                    API                       Provider
  │                         │                           │
  ├─ POST /oauth/initiate ──►                           │
  │  {provider, redirect_port: null}                    │
  │                         │                           │
  ◄─ {auth_url, state} ────┤                           │
  │                         │                           │
  ├─ window.location = auth_url ───────────────────────►│
  │                         │                           │
  │ (user authorizes)       │                           │
  │                         │                           │
  ◄─────────────────────────────── redirect to ─────────┤
  │  /oauth/web-callback?code=xxx&state=yyy             │
  │                         │                           │
  ├─ GET /oauth/web-callback ►                          │
  │                         ├─ exchange code ───────────►│
  │                         ◄─ tokens ──────────────────┤
  │                         ├─ store in DB              │
  │                         │                           │
  ◄─ 302 → /emails/link/   │                           │
  │   complete?status=      │                           │
  │   success&email=...     │                           │
```

### Microsoft (Device Code) — No Change Needed
Device code flow already works in browsers:
1. Display verification URI and user code
2. User opens link in new tab, enters code
3. Frontend polls `POST /oauth/poll` every N seconds
4. On success, update UI

### API Addition Required

```python
# account_hub/api/routers/oauth.py (new endpoint)

@router.get("/web-callback")
async def web_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Browser redirect callback for OAuth. Exchanges code, redirects to frontend."""
    # Extract user_id from state (stored in OAuthState table)
    oauth_state = await db.execute(
        select(OAuthState).where(OAuthState.state == state)
    )
    state_row = oauth_state.scalar_one_or_none()
    if not state_row:
        return RedirectResponse("/login?error=invalid_state")

    try:
        result = await handle_oauth_callback(
            db, state_row.user_id, state_row.provider, code, state
        )
        return RedirectResponse(
            f"http://localhost:3000/emails/link/complete"
            f"?status=success&email={result.email_address}&provider={result.provider}"
        )
    except EmailAlreadyLinkedError:
        return RedirectResponse(
            "http://localhost:3000/emails/link/complete?status=already_linked"
        )
    except (TokenExchangeFailedError, UserInfoFailedError):
        return RedirectResponse(
            "http://localhost:3000/emails/link/complete?status=error"
        )
```

**OAuth provider config change**: For web mode, `redirect_uri` becomes `http://localhost:8000/oauth/web-callback` instead of `http://127.0.0.1:{port}/callback`. This requires registering this redirect URI with each OAuth provider.

---

## 8. Key UI Components

### Dashboard Page
```
┌─────────────────────────────────────────────┐
│  Welcome back, {username}                    │
│                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │ 3 Emails │ │ 12 Accts │ │ 2 Pending│    │
│  │  linked   │ │discovered│ │ closures │    │
│  └──────────┘ └──────────┘ └──────────┘    │
│                                              │
│  ┌─ Recent Scan ───────────────────────┐    │
│  │ April 13 · 3 emails · 12 accounts  │    │
│  │ [View Results]  [Run New Scan]      │    │
│  └─────────────────────────────────────┘    │
│                                              │
│  ┌─ Linked Emails ────────────────────┐     │
│  │ ✉ user@gmail.com    Google   [x]  │     │
│  │ ✉ user@outlook.com  Microsoft [x] │     │
│  │ [+ Link Another Email]            │     │
│  └────────────────────────────────────┘     │
└─────────────────────────────────────────────┘
```

### Scan Results Page
```
┌─────────────────────────────────────────────┐
│  Scan Results                                │
│  April 13, 2026 · 3 emails · 12 accounts    │
│  [Export CSV]                                │
│                                              │
│  Filter: [All ▼] [All Sources ▼] [Search...] │
│                                              │
│  ┌─ Email: user@gmail.com ────────────┐     │
│  │ Google Account    confirmed  oauth  │     │
│  │ Gravatar          confirmed  grav   │     │
│  │ Twitter           confirmed  grav   │     │
│  │ Adobe             confirmed  hibp   │     │
│  │    ⚠ Breach: 2023-10-15            │     │
│  │ [Request Closure] for each row      │     │
│  └─────────────────────────────────────┘     │
│                                              │
│  ┌─ Email: user@outlook.com ──────────┐     │
│  │ Microsoft Account confirmed  oauth  │     │
│  │ LinkedIn          confirmed  hibp   │     │
│  │    ⚠ Breach: 2024-01-20            │     │
│  └─────────────────────────────────────┘     │
└─────────────────────────────────────────────┘
```

### Closure Tracker
```
┌─────────────────────────────────────────────┐
│  Account Closures                            │
│                                              │
│  Pending (2)                                 │
│  ┌──────────────────────────────────────┐   │
│  │ Adobe    web  medium                  │   │
│  │ [Open Deletion Page] [Mark Complete]  │   │
│  │ Notes: 30-day grace period            │   │
│  ├──────────────────────────────────────┤   │
│  │ LinkedIn  web  easy                   │   │
│  │ [Open Deletion Page] [Mark Complete]  │   │
│  └──────────────────────────────────────┘   │
│                                              │
│  Completed (5)                               │
│  ┌──────────────────────────────────────┐   │
│  │ ✓ Twitter   Apr 10                    │   │
│  │ ✓ Spotify   Apr 8                     │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

---

## 9. Directory Structure

```
web/
├── public/
│   └── favicon.svg
├── src/
│   ├── main.tsx                    # Entry point
│   ├── App.tsx                     # Router + providers
│   ├── api/
│   │   ├── client.ts              # Fetch wrapper with auth interceptor
│   │   ├── auth.ts                # Auth API calls
│   │   ├── emails.ts              # Email API calls
│   │   ├── scan.ts                # Scan API calls
│   │   └── closures.ts            # Closure API calls
│   ├── stores/
│   │   └── auth-store.ts          # Zustand auth state
│   ├── hooks/
│   │   ├── use-auth.ts            # Auth hook
│   │   ├── use-emails.ts          # TanStack Query hooks
│   │   ├── use-scan.ts
│   │   └── use-closures.ts
│   ├── pages/
│   │   ├── login.tsx
│   │   ├── register.tsx
│   │   ├── dashboard.tsx
│   │   ├── emails.tsx
│   │   ├── email-link-complete.tsx
│   │   ├── scan.tsx
│   │   ├── scan-detail.tsx
│   │   ├── closures.tsx
│   │   ├── browse-registry.tsx
│   │   └── settings.tsx
│   ├── components/
│   │   ├── layout/
│   │   │   ├── sidebar.tsx
│   │   │   ├── header.tsx
│   │   │   └── auth-guard.tsx
│   │   ├── emails/
│   │   │   ├── email-list.tsx
│   │   │   ├── link-email-dialog.tsx
│   │   │   └── device-code-poller.tsx
│   │   ├── scan/
│   │   │   ├── scan-results-table.tsx
│   │   │   ├── scan-progress.tsx
│   │   │   └── scan-history-list.tsx
│   │   ├── closures/
│   │   │   ├── closure-card.tsx
│   │   │   └── closure-instructions.tsx
│   │   └── ui/                     # shadcn/ui components
│   │       ├── button.tsx
│   │       ├── card.tsx
│   │       ├── dialog.tsx
│   │       ├── input.tsx
│   │       ├── table.tsx
│   │       └── ...
│   ├── lib/
│   │   └── utils.ts               # cn() helper, formatters
│   └── types/
│       └── api.ts                  # Shared API response types
├── index.html
├── tailwind.config.ts
├── tsconfig.json
├── vite.config.ts
└── package.json
```

---

## 10. API Backend Changes (Minimal)

| Change | File | Scope |
|--------|------|-------|
| Add `GET /oauth/web-callback` | `api/routers/oauth.py` | New endpoint (~30 lines) |
| Add `WEB_REDIRECT_URI` config | `config.py` | 1 new setting |
| Update `initiate_oauth` | `services/oauth_service.py` | Pass redirect_uri mode |
| Add frontend origin to CORS | `api/main.py` | Config-driven origins |

**No changes to**: database models, existing endpoints, CLI, security, scanners.

---

## 11. Deployment Architecture

### Development
```
localhost:3000  →  Vite dev server (React SPA)
localhost:8000  →  Uvicorn (FastAPI API)
localhost:5432  →  PostgreSQL (Docker)
```

### Production
```
                    ┌──────────────────┐
                    │  Cloudflare CDN  │
                    │  (static SPA)    │
                    │  app.dlopro.com  │
                    └────────┬─────────┘
                             │
                    ┌────────┴─────────┐
                    │  Cloudflare      │
                    │  Worker (proxy)  │
                    │  or fly.io       │
                    │  api.dlopro.com  │
                    └────────┬─────────┘
                             │
                    ┌────────┴─────────┐
                    │  PostgreSQL      │
                    │  (Neon / Supabase│
                    │   / fly.io)      │
                    └──────────────────┘
```

| Component | Service | Cost |
|-----------|---------|------|
| SPA hosting | Cloudflare Pages | Free |
| API server | Fly.io or Railway | ~$5/mo |
| Database | Neon (serverless PG) | Free tier |
| Apple relay | Existing Cloudflare Worker | Free |
| Domain | dlopro.com (existing) | — |

---

## 12. Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Scaffold Vite + React + TypeScript project in `web/`
- [ ] Set up Tailwind CSS + shadcn/ui
- [ ] Build auth store (Zustand) + API client with interceptor
- [ ] Login + Register pages
- [ ] Auth guard + sidebar layout
- [ ] Dashboard page (static, calls `/auth/me`)

### Phase 2: Core Features (Week 2)
- [ ] Emails page: list linked emails, unlink
- [ ] Add `GET /oauth/web-callback` to API
- [ ] OAuth link flow: initiate → redirect → callback → success page
- [ ] Device code flow UI (Microsoft)
- [ ] Run scan + poll for completion
- [ ] Scan results page with filtering

### Phase 3: Closures & Polish (Week 3)
- [ ] Scan history page with pagination
- [ ] CSV export (download button)
- [ ] Closure request flow
- [ ] Closure tracker dashboard
- [ ] Deletion registry browser
- [ ] Settings page (profile, delete account)

### Phase 4: Production (Week 4)
- [ ] Responsive mobile layout
- [ ] Error boundaries + loading states
- [ ] Vitest unit tests for hooks/stores
- [ ] Playwright E2E tests for critical flows
- [ ] Deploy to Cloudflare Pages
- [ ] Configure production CORS origins

---

## 13. Trade-offs & Open Questions

### Decided
| Decision | Chosen | Alternative | Why |
|----------|--------|-------------|-----|
| SPA vs SSR | SPA (Vite) | Next.js | No SEO needs, simpler deployment |
| State management | Zustand + TanStack Query | Redux | Lighter weight, built-in cache |
| UI library | shadcn/ui | MUI, Ant Design | Composable, no vendor lock-in |
| Token storage | Memory + localStorage | HttpOnly cookies | API doesn't set cookies, Bearer auth |

### Open Questions
1. **Real-time scan updates** — Should we add WebSocket/SSE for live scan progress, or is polling sufficient? (Polling is simpler, scan takes 5-15s)
2. **Multi-tab support** — If user has multiple tabs, how do token refreshes sync? (BroadcastChannel API)
3. **Dark mode** — Ship with dark mode toggle from day 1, or add later? (Tailwind makes it easy)
4. **Onboarding flow** — First-time user wizard (register → link email → first scan), or let them explore?

---

## 14. Security Considerations for Web UI

| Concern | Mitigation |
|---------|------------|
| XSS | React auto-escapes, CSP headers, no `dangerouslySetInnerHTML` |
| CSRF | Bearer tokens (not cookies) = no CSRF risk |
| Token theft | Access token in memory (not localStorage), short TTL |
| Open redirect | Validate OAuth callback redirect URLs server-side |
| Rate limiting | Show user-friendly messages on 429, disable buttons |
| Account lockout | Display lockout message, countdown timer |
