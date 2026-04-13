import type {
  RegisterResponse,
  TokenResponse,
  UserResponse,
} from "@/types/api";
import { apiFetch } from "./client";

export const authApi = {
  register: (username: string, password: string) =>
    apiFetch<RegisterResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password }),
      skipAuth: true,
    }),

  login: (username: string, password: string) =>
    apiFetch<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
      skipAuth: true,
    }),

  refresh: (refreshToken: string) =>
    apiFetch<TokenResponse>("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
      skipAuth: true,
    }),

  me: () => apiFetch<UserResponse>("/auth/me"),

  forgotPassword: (username: string) =>
    apiFetch<{ message: string; reset_url?: string }>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ username }),
      skipAuth: true,
    }),

  resetPassword: (token: string, newPassword: string) =>
    apiFetch<{ message: string }>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, new_password: newPassword }),
      skipAuth: true,
    }),

  deleteAccount: (password: string) =>
    apiFetch<void>("/auth/account", {
      method: "DELETE",
      body: JSON.stringify({ password }),
    }),
};
