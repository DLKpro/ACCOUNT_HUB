-- V0001__initial.sql — Initial vault schema.
--
-- See docs/design/03-vault.md for the full design.
-- This migration creates the five tables that survive from the Python schema
-- (LinkedEmail, OAuthState, ScanSession, DiscoveredAccount, ClosureRequest).
-- Auth-only tables (User, EmailVerificationToken, PasswordResetToken) are NOT
-- ported — master-password unlock replaces their reason for existing.
--
-- Conventions:
--   - Primary keys are INTEGER AUTOINCREMENT (SQLite rowid-based; stable across rewrites).
--   - Timestamps are INTEGER unix seconds. No TEXT dates.
--   - Single-user vault: no user_id columns.
--   - On-disk token fields are TEXT (plaintext inside the SQLCipher envelope).
--   - Booleans are INTEGER 0/1.

PRAGMA foreign_keys = ON;

-- =============================================================================
-- linked_email: an email address linked to a provider via OAuth.
-- =============================================================================
CREATE TABLE linked_email (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    email             TEXT NOT NULL UNIQUE,
    provider          TEXT NOT NULL
                      CHECK (provider IN ('google', 'microsoft', 'apple', 'meta')),
    provider_user_id  TEXT,
    access_token      TEXT,
    refresh_token     TEXT,
    token_expires_at  INTEGER,
    scopes            TEXT,                 -- JSON array of granted scope strings
    is_verified       INTEGER NOT NULL DEFAULT 0
                      CHECK (is_verified IN (0, 1)),
    created_at        INTEGER NOT NULL,
    updated_at        INTEGER NOT NULL
);

-- =============================================================================
-- oauth_state: in-flight OAuth flow state. PKCE verifier + OIDC nonce.
-- Rows are short-lived (~10 min). Consumed on callback; pruned on expiry.
-- =============================================================================
CREATE TABLE oauth_state (
    state             TEXT PRIMARY KEY,
    provider          TEXT NOT NULL,
    code_verifier     TEXT NOT NULL,        -- PKCE (RFC 7636)
    nonce             TEXT,                 -- OIDC nonce (NULL for non-OIDC providers)
    loopback_port     INTEGER,              -- Apple relay encodes this in `state`; denormalized here for diagnostics
    created_at        INTEGER NOT NULL,
    expires_at        INTEGER NOT NULL
);

-- =============================================================================
-- scan_session: one user-initiated scan across all linked emails.
-- =============================================================================
CREATE TABLE scan_session (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    status            TEXT NOT NULL
                      CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    emails_scanned    INTEGER NOT NULL DEFAULT 0,
    accounts_found    INTEGER NOT NULL DEFAULT 0,
    error_message     TEXT,                 -- populated on 'failed'
    started_at        INTEGER NOT NULL,
    completed_at      INTEGER
);

-- =============================================================================
-- discovered_account: an external account found during a scan.
-- =============================================================================
CREATE TABLE discovered_account (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_session_id   INTEGER NOT NULL
                      REFERENCES scan_session(id) ON DELETE CASCADE,
    linked_email_id   INTEGER
                      REFERENCES linked_email(id) ON DELETE SET NULL,
    email             TEXT NOT NULL,
    service_name      TEXT NOT NULL,
    source            TEXT NOT NULL
                      CHECK (source IN ('oauth_profile', 'hibp', 'scanner')),
    confidence        REAL
                      CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    breach_date       INTEGER,              -- only populated for 'hibp'-sourced rows
    created_at        INTEGER NOT NULL
);

-- =============================================================================
-- closure_request: user-initiated account closure tracking.
-- =============================================================================
CREATE TABLE closure_request (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    discovered_account_id INTEGER
                          REFERENCES discovered_account(id) ON DELETE SET NULL,
    service_name          TEXT NOT NULL,
    method                TEXT NOT NULL
                          CHECK (method IN ('api', 'web_link', 'email_request', 'manual')),
    status                TEXT NOT NULL
                          CHECK (status IN ('pending', 'in_progress', 'completed', 'failed')),
    deletion_url          TEXT,
    notes                 TEXT,
    created_at            INTEGER NOT NULL,
    completed_at          INTEGER
);

-- =============================================================================
-- Indexes. Chosen to match common query patterns:
--   - prune expired oauth_state rows on a timer
--   - list discoveries for a given scan
--   - list discoveries for a given linked email (audit trail)
--   - filter closure requests by status (UI pending/in-progress views)
--   - filter linked emails by provider (UI per-provider views)
-- =============================================================================
CREATE INDEX idx_oauth_state_expires              ON oauth_state(expires_at);
CREATE INDEX idx_discovered_account_scan          ON discovered_account(scan_session_id);
CREATE INDEX idx_discovered_account_linked_email  ON discovered_account(linked_email_id);
CREATE INDEX idx_closure_request_status           ON closure_request(status);
CREATE INDEX idx_linked_email_provider            ON linked_email(provider);
