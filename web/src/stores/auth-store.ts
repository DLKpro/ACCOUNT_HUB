import { create } from "zustand";
import { authApi } from "@/api/auth";
import type { UserResponse } from "@/types/api";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: UserResponse | null;
  isLoading: boolean;

  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<boolean>;
  fetchUser: () => Promise<void>;
  hydrate: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: null,
  refreshToken: null,
  user: null,
  isLoading: true,

  login: async (username, password) => {
    const data = await authApi.login(username, password);
    localStorage.setItem("refresh_token", data.refresh_token);
    set({ accessToken: data.access_token, refreshToken: data.refresh_token });
    const user = await authApi.me();
    set({ user });
  },

  register: async (username, password) => {
    const data = await authApi.register(username, password);
    localStorage.setItem("refresh_token", data.refresh_token);
    set({
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      user: {
        id: data.id,
        username: data.username,
        email: null,
        is_active: true,
        created_at: "",
      },
    });
  },

  logout: () => {
    localStorage.removeItem("refresh_token");
    set({ accessToken: null, refreshToken: null, user: null });
  },

  refresh: async () => {
    const rt = get().refreshToken ?? localStorage.getItem("refresh_token");
    if (!rt) return false;
    try {
      const data = await authApi.refresh(rt);
      localStorage.setItem("refresh_token", data.refresh_token);
      set({
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
      });
      return true;
    } catch {
      localStorage.removeItem("refresh_token");
      set({ accessToken: null, refreshToken: null, user: null });
      return false;
    }
  },

  fetchUser: async () => {
    try {
      const user = await authApi.me();
      set({ user });
    } catch {
      get().logout();
    }
  },

  hydrate: async () => {
    set({ isLoading: true });
    const rt = localStorage.getItem("refresh_token");
    if (rt) {
      set({ refreshToken: rt });
      const ok = await get().refresh();
      if (ok) await get().fetchUser();
    }
    set({ isLoading: false });
  },
}));
