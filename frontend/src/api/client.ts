import { COGNITO_ENABLED } from "./cognito";
import type {
  ClassifyResult,
  CollectorProfile,
  Credentials,
  FieldIssue,
  Impact,
  Meta,
  PickupDraft,
  QueueItem,
  TrackedPickup,
  UploadTicket,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/+$/, "");

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: FieldIssue[];

  constructor(status: number, code: string, message: string, details: FieldIssue[] = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

interface RequestOptions {
  body?: unknown;
  credentials?: Credentials;
  signal?: AbortSignal;
}

interface ErrorPayload {
  error?: { code?: string; message?: string; details?: FieldIssue[] };
}

async function request<T>(
  method: "GET" | "POST",
  path: string,
  { body, credentials, signal }: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["content-type"] = "application/json";
  if (credentials) {
    // Cognito: `key` holds the ID token. Local dev: `key` is the derived shared key.
    headers["authorization"] = COGNITO_ENABLED
      ? `Bearer ${credentials.key}`
      : `Bearer ${credentials.collectorId}:${credentials.key}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: signal ?? null,
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiError(0, "NETWORK", "Can't reach the server. Check your connection and try again.");
  }

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = (payload as ErrorPayload | null)?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "UNKNOWN",
      error?.message ?? "Something went wrong. Please try again.",
      error?.details ?? [],
    );
  }
  return payload as T;
}

/** The ticket is either an S3 presigned POST (production) or the dev server (local). */
export async function uploadImage(ticket: UploadTicket, image: Blob): Promise<void> {
  const form = new FormData();
  for (const [name, value] of Object.entries(ticket.fields)) form.append(name, value);
  form.append("file", image, "photo.jpg"); // S3 requires the file to be the last field

  let response: Response;
  try {
    response = await fetch(ticket.url, { method: "POST", body: form });
  } catch {
    throw new ApiError(0, "NETWORK", "The photo could not be uploaded. Check your connection.");
  }
  if (!response.ok) throw new ApiError(response.status, "UPLOAD_FAILED", "The photo could not be uploaded.");
}

export const api = {
  meta: (signal?: AbortSignal) => request<Meta>("GET", "/meta", signal ? { signal } : {}),
  startUpload: () => request<UploadTicket>("POST", "/uploads", { body: { content_type: "image/jpeg" } }),
  classify: (imageKey: string) => request<ClassifyResult>("POST", "/classify", { body: { image_key: imageKey } }),
  createPickup: (draft: PickupDraft) => request<TrackedPickup>("POST", "/pickups", { body: draft }),
  getPickup: (id: string, signal?: AbortSignal) =>
    request<TrackedPickup>("GET", `/pickups/${encodeURIComponent(id)}`, signal ? { signal } : {}),
  impact: (signal?: AbortSignal) => request<Impact>("GET", "/impact", signal ? { signal } : {}),
  collector: {
    me: (credentials: Credentials) => request<CollectorProfile>("GET", "/collector/me", { credentials }),
    queue: (credentials: Credentials, signal?: AbortSignal) =>
      request<{ pickups: QueueItem[] }>("GET", "/collector/pickups", signal ? { credentials, signal } : { credentials }),
    confirm: (credentials: Credentials, id: string) =>
      request<QueueItem>("POST", `/collector/pickups/${encodeURIComponent(id)}/confirm`, { credentials }),
    collect: (credentials: Credentials, id: string, weightG: number) =>
      request<QueueItem>("POST", `/collector/pickups/${encodeURIComponent(id)}/collect`, {
        credentials,
        body: { weight_g: weightG },
      }),
  },
};
