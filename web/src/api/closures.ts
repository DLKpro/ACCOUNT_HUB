import type {
  ClosureRequestResponse,
  ClosureInfoResponse,
} from "@/types/api";
import { apiFetch } from "./client";

export const closuresApi = {
  list: () => apiFetch<ClosureRequestResponse[]>("/accounts/close-requests"),

  request: (discoveredAccountId: string) =>
    apiFetch<ClosureRequestResponse>("/accounts/close", {
      method: "POST",
      body: JSON.stringify({ discovered_account_id: discoveredAccountId }),
    }),

  complete: (requestId: string) =>
    apiFetch<ClosureRequestResponse>("/accounts/close/complete", {
      method: "POST",
      body: JSON.stringify({ request_id: requestId }),
    }),

  info: (serviceName: string) =>
    apiFetch<ClosureInfoResponse>(
      `/accounts/close-info/${encodeURIComponent(serviceName)}`,
    ),
};
