export const API_BASE = process.env.EXPO_PUBLIC_BACKEND_URL || "http://localhost:8000";

export function getStoredStaff(){if(typeof window==="undefined")return null;try{return JSON.parse(window.localStorage.getItem("fabclean_staff")||"null");}catch{return null;}}
export function getStoredToken(){if(typeof window==="undefined")return "";return window.localStorage.getItem("fabclean_session")||"";}
export function setStoredSession(staff:any,token:string){if(typeof window!=="undefined"){if(staff&&token){window.localStorage.setItem("fabclean_staff",JSON.stringify(staff));window.localStorage.setItem("fabclean_session",token);}else{window.localStorage.removeItem("fabclean_staff");window.localStorage.removeItem("fabclean_session");}}}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token=getStoredToken();
  const res = await fetch(`${API_BASE}/api${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(token?{"X-Session-Token":token}:{}), ...(options.headers || {}) }
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const error:any = new Error(data?.detail || "Request failed");
    error.status = res.status;
    if (res.status === 401) setStoredSession(null,"");
    throw error;
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" })
};
