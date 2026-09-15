export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8005/api";

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

let refreshPromise: Promise<void> | null = null;

async function refreshSession(): Promise<void> {
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_URL}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    })
      .then((res) => {
        if (!res.ok) throw new ApiError(res.status, "refresh_failed", "Session expired");
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

/**
 * Shared response handling: on 401, refresh once and retry via `retry`;
 * `retry` is null on the retry attempt itself, so a refresh that also 401s
 * falls through to a normal error instead of looping forever.
 */
async function handleResponse<T>(res: Response, retry: (() => Promise<T>) | null): Promise<T> {
  if (res.status === 401 && retry) {
    try {
      await refreshSession();
      return await retry();
    } catch {
      // fall through to normal error handling below
    }
  }

  if (!res.ok) {
    const payload = await res.json().catch(() => ({ code: "unknown", message: res.statusText }));
    throw new ApiError(res.status, payload.code ?? "unknown", payload.message ?? res.statusText);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body } = options;

  const fire = () =>
    fetch(`${API_URL}${path}`, {
      method,
      credentials: "include",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });

  const res = await fire();
  return handleResponse<T>(res, async () => handleResponse<T>(await fire(), null));
}

/** Multipart upload — separate from apiRequest because a JSON Content-Type
 * header would break the multipart boundary the browser sets automatically. */
export async function apiUpload<T>(path: string, file: File, fieldName = "file"): Promise<T> {
  const fire = () => {
    const formData = new FormData();
    formData.append(fieldName, file);
    return fetch(`${API_URL}${path}`, { method: "POST", credentials: "include", body: formData });
  };

  const res = await fire();
  return handleResponse<T>(res, async () => handleResponse<T>(await fire(), null));
}
