export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}

// This is the sole type boundary for the server's versioned OpenAPI contract.
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (init?.method && init.method !== "GET") headers.set("X-CSRF-Token", csrf);
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  });
  const payload: unknown = await response.json();
  if (!response.ok) {
    const error = readError(payload);
    throw new ApiError(error.code, error.message, response.status);
  }
  return payload as T;
}
function readError(value: unknown): { code: string; message: string } {
  if (
    value &&
    typeof value === "object" &&
    "error" in value &&
    value.error &&
    typeof value.error === "object"
  ) {
    const item = value.error;
    if ("message" in item && typeof item.message === "string")
      return {
        code: "code" in item ? String(item.code) : "API_ERROR",
        message: item.message,
      };
  }
  return {
    code: "API_ERROR",
    message: "The request could not be completed. Refresh and try again.",
  };
}
export function errorMessage(value: unknown) {
  return value instanceof Error
    ? value.message
    : "Something went wrong. Try again.";
}
export function post<T>(path: string, body: unknown = {}) {
  return api<T>(path, { method: "POST", body: JSON.stringify(body) });
}
export function assetUrl(revision: string, file: string) {
  return `/api/v1/revisions/${revision}/assets/${encodeURIComponent(file)}`;
}
export function isActive(status?: string) {
  return status === "QUEUED" || status === "RUNNING";
}
