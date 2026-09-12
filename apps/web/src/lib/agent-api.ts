/**
 * Agent session API types + helpers (scaffold).
 * Browser talks to the agent directly via NEXT_PUBLIC_AGENT_URL.
 */

const AGENT_URL =
  process.env.NEXT_PUBLIC_AGENT_URL?.replace(/\/$/, "") ||
  "http://localhost:7860";

export type SessionStatus =
  | "starting"
  | "ready"
  | "ending"
  | "ended"
  | "error";

export type CallUiStatus =
  | "idle"
  | "mic_blocked"
  | "starting"
  | "connecting"
  | "ready"
  | "ending"
  | "ended"
  | "error";

export interface RoomInfo {
  url: string;
  name: string;
  expires_at: string;
}

export interface SessionCreated {
  session_id: string;
  status: SessionStatus;
  room: RoomInfo;
  client: { token: string };
}

export interface SessionStatusPayload {
  session_id: string;
  status: SessionStatus;
  room: RoomInfo;
  created_at: string;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    request_id?: string | null;
  };
}

export function getAgentUrl(): string {
  return AGENT_URL;
}

export async function createSession(userId?: string): Promise<SessionCreated> {
  const res = await fetch(`${AGENT_URL}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(
      userId ? { client: { user_id: userId } } : {},
    ),
  });

  const data = (await res.json()) as SessionCreated | ApiError;
  if (!res.ok) {
    const err = data as ApiError;
    throw new Error(err.error?.message || `createSession failed (${res.status})`);
  }
  return data as SessionCreated;
}

export async function getSession(
  sessionId: string,
): Promise<SessionStatusPayload> {
  const res = await fetch(`${AGENT_URL}/sessions/${sessionId}`);
  const data = (await res.json()) as SessionStatusPayload | ApiError;
  if (!res.ok) {
    const err = data as ApiError;
    throw new Error(err.error?.message || `getSession failed (${res.status})`);
  }
  return data as SessionStatusPayload;
}

/**
 * Fire-and-forget session teardown for page unload.
 *
 * `keepalive` lets the request outlive the document, which `sendBeacon` cannot
 * do here because the agent expects DELETE.
 */
export function endSessionBeacon(sessionId: string): void {
  try {
    void fetch(`${AGENT_URL}/sessions/${sessionId}`, {
      method: "DELETE",
      keepalive: true,
    });
  } catch {
    /* the page is going away regardless */
  }
}

export async function endSession(sessionId: string): Promise<void> {
  const res = await fetch(`${AGENT_URL}/sessions/${sessionId}`, {
    method: "DELETE",
  });
  if (res.status === 204) return;
  if (res.status === 404) return; // treat unknown as already gone for hang-up UX

  let message = `endSession failed (${res.status})`;
  try {
    const data = (await res.json()) as ApiError;
    if (data.error?.message) message = data.error.message;
  } catch {
    /* ignore */
  }
  throw new Error(message);
}
