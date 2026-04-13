import type {
  ScanStartResponse,
  ScanSummaryResponse,
  ScanDetailResponse,
} from "@/types/api";
import { apiFetch } from "./client";

export const scanApi = {
  start: () => apiFetch<ScanStartResponse>("/search", { method: "POST" }),

  history: (limit = 10, offset = 0) =>
    apiFetch<ScanSummaryResponse[]>(
      `/search/history?limit=${limit}&offset=${offset}`,
    ),

  detail: (sessionId: string) =>
    apiFetch<ScanDetailResponse>(`/search/${sessionId}`),

  exportCsv: async (sessionId: string): Promise<string> => {
    const { useAuthStore } = await import("@/stores/auth-store");
    const token = useAuthStore.getState().accessToken;
    const resp = await fetch(`/api/search/${sessionId}/export`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!resp.ok) throw new Error("Export failed");
    return resp.text();
  },
};
