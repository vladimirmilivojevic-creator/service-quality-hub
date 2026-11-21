// Small fetch wrapper for the FastAPI backend.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TOKEN_KEY = "sqh-token";
export const LOGOUT_EVENT = "sqh:logout";

export function getToken(): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

function authHeaders(init: RequestInit = {}): Headers {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return headers;
}

async function check(response: Response): Promise<Response> {
  if (response.ok) return response;
  const body = await response.json().catch(() => ({}));
  const detail = typeof body.detail === "string" ? body.detail : response.statusText;
  if (response.status === 401 && getToken()) {
    setToken(null); // expired token: AuthProvider hears this and sends the user to /login
    window.dispatchEvent(new Event(LOGOUT_EVENT));
  }
  throw new ApiError(response.status, detail || "Request failed");
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = authHeaders(init);
  if (init.body && typeof init.body === "string") headers.set("Content-Type", "application/json");
  const response = await check(await fetch(`${API_URL}${path}`, { ...init, headers }));
  return response.json() as Promise<T>;
}

/** POST a file as multipart form data (CSV import). */
export async function upload<T>(path: string, file: File): Promise<T> {
  const body = new FormData();
  body.append("file", file);
  const response = await check(await fetch(`${API_URL}${path}`, { method: "POST", body, headers: authHeaders() }));
  return response.json() as Promise<T>;
}

/** Download a file that needs the login token (the Excel report). */
export async function download(path: string, fallbackName: string) {
  const response = await check(await fetch(`${API_URL}${path}`, { headers: authHeaders() }));
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

export async function login(email: string, password: string): Promise<string> {
  // FastAPI's OAuth2 password flow expects form data with "username" and "password"
  const body = new URLSearchParams({ username: email, password });
  const response = await fetch(`${API_URL}/auth/login`, { method: "POST", body });
  if (!response.ok) throw new ApiError(response.status, "Incorrect email or password");
  const data: { access_token: string } = await response.json();
  return data.access_token;
}
