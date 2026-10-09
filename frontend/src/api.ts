import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";

export const API_BASE = process.env.EXPO_PUBLIC_BACKEND_URL || "http://localhost:8000";
let staff: any = null;
let token = "";
let generation = 0;
const listeners = new Set<() => void>();
export const subscribeSession = (listener: () => void) => {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
};
const emit = () => listeners.forEach(listener => listener());
export async function readPreference(key: string) {
  if (Platform.OS !== "web") return SecureStore.getItemAsync(key);
  return typeof window === "undefined" ? null : window.localStorage.getItem(key);
}
export async function writePreference(key: string, value: string | null) {
  if (Platform.OS !== "web") {
    if (value === null) await SecureStore.deleteItemAsync(key);
    else await SecureStore.setItemAsync(key, value);
  } else if (typeof window !== "undefined") {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  }
}
export const sessionReady = (async () => {
  try {
    token = await readPreference("fabclean_session") || "";
    staff = JSON.parse(await readPreference("fabclean_staff") || "null");
    if (Platform.OS === "web") await writePreference("fabclean-dashboard-cache", null);
  } catch { token = ""; staff = null; }
})();
export function getStoredStaff() { return staff; }
export function getStoredToken() { return token; }
export function invalidateRequests() { generation += 1; }
export function notifySessionChanged() { emit(); }
export async function setStoredSession(nextStaff: any, nextToken: string, notify = true) {
  await sessionReady;
  const changed = token !== nextToken || staff?.id !== nextStaff?.id;
  staff = nextStaff;
  token = nextToken;
  invalidateRequests();
  await Promise.all([
    writePreference("fabclean_staff", nextStaff && nextToken ? JSON.stringify(nextStaff) : null),
    writePreference("fabclean_session", nextStaff && nextToken ? nextToken : null)
  ]);
  if (changed && notify) emit();
}

export async function refreshSession() {
  await sessionReady;
  const nextToken = await readPreference("fabclean_session") || "";
  const nextStaff = JSON.parse(await readPreference("fabclean_staff") || "null");
  if (nextToken !== token || nextStaff?.id !== staff?.id) {
    token = nextToken; staff = nextStaff; invalidateRequests(); emit();
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  await sessionReady;
  const started = generation;
  const res = await fetch(`${API_BASE}/api${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(token ? {"X-Session-Token": token} : {}), ...(options.headers || {}) }
  });
  const text = await res.text();
  if (started !== generation) throw new Error("Active context changed; reload this screen.");
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const error: any = new Error(data?.detail || "Request failed");
    error.status = res.status;
    if (res.status === 401) await setStoredSession(null, "");
    throw error;
  }
  if (path === "/context" && options.method === "PUT") {
    invalidateRequests();
    emit();
  }
  return data as T;
}
export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" })
};
