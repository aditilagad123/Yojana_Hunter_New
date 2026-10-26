const API_BASE_URL = typeof window !== 'undefined' ? '/api' : (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:5000/api');

export const AUTH_TOKEN_KEY = "yojana_auth_token";
export const AUTH_USER_KEY = "yojana_auth_user";

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

interface RequestOptions extends RequestInit {
  timeoutMs?: number;
}

export interface ApiResponse<T> {
  data: T | null;
  error?: string;
  status: number;
}

export async function apiFetch<T>(endpoint: string, options: RequestOptions = {}): Promise<T | null> {
  const { timeoutMs = 25000, ...customConfig } = options;
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);

  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...((customConfig.headers as Record<string, string>) || {}),
  };

  const config: RequestInit = {
    headers,
    signal: controller.signal,
    ...customConfig,
  };

  const url = `${API_BASE_URL}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;

  try {
    const response = await fetch(url, config);
    clearTimeout(id);

    if (!response.ok) {
      console.warn(`API request ${endpoint} failed with status ${response.status}`);
      return null;
    }

    return await response.json();
  } catch (error) {
    clearTimeout(id);
    return null;
  }
}

export async function apiFetchDetailed<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<ApiResponse<T>> {
  const { timeoutMs = 8000, ...customConfig } = options;
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);

  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...((customConfig.headers as Record<string, string>) || {}),
  };

  const config: RequestInit = {
    headers,
    signal: controller.signal,
    ...customConfig,
  };

  const url = `${API_BASE_URL}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;

  try {
    const response = await fetch(url, config);
    clearTimeout(id);

    const status = response.status;
    let json: any = null;
    try {
      json = await response.json();
    } catch {
      json = null;
    }

    if (!response.ok) {
      return {
        data: (json || null) as T | null,
        error: json?.message || json?.error || `Request failed with status ${status}`,
        status,
      };
    }

    return {
      data: json as T,
      status,
    };
  } catch (err: any) {
    clearTimeout(id);
    return {
      data: null,
      error: err.name === "AbortError" ? "Request timed out" : "Network error. Please verify the server is running.",
      status: 0,
    };
  }
}
