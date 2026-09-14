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

/** DELETE on unload (`keepalive`; sendBeacon can't DELETE). */
export function endSessionBeacon(sessionId: string): void {
  try {
    void fetch(`${AGENT_URL}/sessions/${sessionId}`, {
      method: "DELETE",
      keepalive: true,
    });
  } catch {
    /* ignore */
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

export interface SessionListItem {
  session_id: string;
  status: string;
  created_at: string;
  ended_at: string | null;
  duration_seconds: number | null;
  ended_reason: string | null;
  name: string | null;
  tx_count: number;
}

export interface TranscriptTurn {
  seq: number;
  role: "user" | "agent";
  text: string;
  interrupted: boolean;
  created_at: string;
}

export interface MoneyItem {
  id: string;
  direction: "incoming" | "outgoing";
  label: string;
  amount: number;
  day?: number | null;
  created_at?: string | null;
}

export interface SessionHistory {
  session: SessionListItem;
  transcript: TranscriptTurn[];
  transactions: MoneyItem[];
  derived?: {
    finish: number;
    crunch: { date: string; amount: number };
    days: Array<{
      date: string;
      in: number;
      out: number;
      closing: number;
      moves: Array<{
        id: string;
        label: string;
        amount: number;
        kind: string;
      }>;
    }>;
    overdue?: Array<{
      id: string;
      label: string;
      amount: number;
      kind: string;
      date: string;
    }>;
  } | null;
  cash?: number | null;
  entries?: Array<Record<string, unknown>>;
  missing?: string[];
  plan?: {
    solvable: boolean;
    gap: number | null;
    gap_date: string | null;
  } | null;
  advice?: {
    points: string[];
    payoff: { lowest: number; date: string; ok: boolean; finish: number };
  } | null;
}

export async function listSessions(
  limit = 50,
): Promise<SessionListItem[]> {
  const res = await fetch(`${AGENT_URL}/sessions?limit=${limit}`);
  if (!res.ok) {
    throw new Error(`listSessions failed (${res.status})`);
  }
  return (await res.json()) as SessionListItem[];
}

export async function getSessionHistory(
  sessionId: string,
): Promise<SessionHistory> {
  const res = await fetch(`${AGENT_URL}/sessions/${sessionId}/history`);
  const data = (await res.json()) as SessionHistory | ApiError;
  if (!res.ok) {
    const err = data as ApiError;
    throw new Error(
      err.error?.message || `getSessionHistory failed (${res.status})`,
    );
  }
  return data as SessionHistory;
}
