export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface RegisterResponse extends TokenResponse {
  id: string;
  username: string;
  email: string;
  email_verified: boolean;
  verification_url?: string;
}

export interface UserResponse {
  id: string;
  username: string;
  email: string;
  email_verified: boolean;
  is_active: boolean;
  created_at: string;
}

export interface LinkedEmailResponse {
  id: string;
  email_address: string;
  provider: string;
  is_verified: boolean;
  is_primary: boolean;
  linked_at: string;
}

export interface ScanStartResponse {
  scan_session_id: string;
  status: string;
}

export interface ScanSummaryResponse {
  id: string;
  status: string;
  emails_scanned: number;
  accounts_found: number;
  created_at: string;
}

export interface DiscoveredAccountResponse {
  id: string;
  email_address: string;
  service_name: string;
  service_domain: string | null;
  source: string;
  confidence: string;
  breach_date: string | null;
  discovered_at: string;
}

export interface ScanDetailResponse {
  id: string;
  status: string;
  emails_scanned: number;
  accounts_found: number;
  started_at: string | null;
  completed_at: string | null;
  results: DiscoveredAccountResponse[];
}

export interface ClosureRequestResponse {
  id: string;
  service_name: string;
  method: string;
  status: string;
  deletion_url: string | null;
  requested_at: string;
  completed_at: string | null;
  notes: string | null;
}

export interface ClosureInfoResponse {
  service_name: string;
  deletion_url: string | null;
  difficulty: string;
  method: string;
  notes: string;
}

export interface InitiateResponse {
  auth_url: string | null;
  state: string | null;
  user_code: string | null;
  verification_uri: string | null;
  device_code: string | null;
  interval: number | null;
}

export interface LinkResponse {
  linked_email_id: string;
  email_address: string;
  provider: string;
}
