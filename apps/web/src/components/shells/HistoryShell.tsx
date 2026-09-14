"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/atoms";
import { PlanView } from "@/components/plan/PlanView";
import {
  getSessionHistory,
  listSessions,
  type SessionHistory,
  type SessionListItem,
} from "@/lib/agent-api";
import {
  acceptSnapshot,
  EMPTY_SNAPSHOT,
  type FinanceSnapshot,
} from "@/lib/finance";
import { AppFrame } from "./AppFrame";
import styles from "./shells.module.css";

type HistoryShellProps = {
  onBack: () => void;
};

function formatWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatDuration(total: number | null): string {
  if (total == null || total <= 0) return "";
  const m = Math.floor(total / 60);
  const s = total % 60;
  if (m === 0) return `${s}s`;
  return `${m}m ${String(s).padStart(2, "0")}s`;
}

function toFinance(raw: SessionHistory["finance"]): FinanceSnapshot {
  if (!raw) return EMPTY_SNAPSHOT;
  return acceptSnapshot(EMPTY_SNAPSHOT, raw);
}

export function HistoryShell({ onBack }: HistoryShellProps) {
  const [rows, setRows] = useState<SessionListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<SessionHistory | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const list = await listSessions();
        if (!cancelled) setRows(list);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load calls");
          setRows([]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function openSession(sessionId: string) {
    setLoadingId(sessionId);
    setError(null);
    try {
      const history = await getSessionHistory(sessionId);
      setDetail(history);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open call");
    } finally {
      setLoadingId(null);
    }
  }

  if (detail) {
    const finance = toFinance(detail.finance);
    const turns = detail.transcript;
    const title = detail.session.name?.trim() || "Past call";
    const duration = formatDuration(detail.session.duration_seconds);

    return (
      <AppFrame>
        <div className={styles.historyPage}>
          <div className={styles.historyBar}>
            <div>
              <h1 className={styles.historyTitle}>{title}</h1>
              <p className={styles.historyMeta}>
                {formatWhen(detail.session.created_at)}
                {duration ? ` · ${duration}` : ""}
              </p>
            </div>
            <Button variant="secondary" onClick={() => setDetail(null)}>
              All calls
            </Button>
          </div>

          {finance.plan || finance.facts.length > 0 ? (
            <div className={styles.planScroll}>
              <PlanView snapshot={finance} />
            </div>
          ) : null}

          {turns.length > 0 ? (
            <div className={styles.recap}>
              {turns.map((turn) => (
                <p key={turn.seq} className={styles.recapLine}>
                  <span className={styles.recapSpeaker}>
                    {turn.role === "agent" ? "Kubera" : "You"}
                    {turn.interrupted ? " · cut short" : ""}
                  </span>
                  <span>{turn.text}</span>
                </p>
              ))}
            </div>
          ) : (
            <p className={styles.historyEmpty}>No transcript saved for this call.</p>
          )}
        </div>
      </AppFrame>
    );
  }

  return (
    <AppFrame>
      <div className={styles.historyPage}>
        <div className={styles.historyBar}>
          <div>
            <h1 className={styles.historyTitle}>Past calls</h1>
            <p className={styles.historyMeta}>Transcripts and plans from earlier sessions.</p>
          </div>
          <Button variant="secondary" onClick={onBack}>
            Back
          </Button>
        </div>

        {error ? (
          <p className={styles.errorBanner} role="alert">
            {error}
          </p>
        ) : null}

        {rows == null ? (
          <p className={styles.historyEmpty}>Loading…</p>
        ) : rows.length === 0 ? (
          <p className={styles.historyEmpty}>No saved calls yet. Talk to Kubera once.</p>
        ) : (
          <ul className={styles.historyList}>
            {rows.map((row) => {
              const duration = formatDuration(row.duration_seconds);
              const label = row.name?.trim() || "Untitled call";
              return (
                <li key={row.session_id}>
                  <button
                    type="button"
                    className={styles.historyRow}
                    onClick={() => void openSession(row.session_id)}
                    disabled={loadingId === row.session_id}
                  >
                    <span className={styles.historyRowTitle}>{label}</span>
                    <span className={styles.historyRowMeta}>
                      {formatWhen(row.created_at)}
                      {duration ? ` · ${duration}` : ""}
                      {row.has_plan ? " · plan" : ""}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </AppFrame>
  );
}
