import type { LinkedEmailResponse } from "@/types/api";
import { apiFetch } from "./client";

export const emailsApi = {
  list: () => apiFetch<LinkedEmailResponse[]>("/emails"),
  unlink: (emailId: string) =>
    apiFetch<void>(`/emails/${emailId}`, { method: "DELETE" }),
};
