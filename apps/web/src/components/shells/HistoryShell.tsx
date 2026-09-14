"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/atoms";
import { MoneyBoard } from "@/components/transactions/MoneyBoard";
import {
  getSessionHistory,
  listSessions,
  type SessionHistory,
  type SessionListItem,
} from "@/lib/agent-api";
import {
  EMPTY_TRANSACTIONS,
  acceptTransactions,
  hasBoard,
  type MoneyItem,
  type TransactionsState,
} from "@/lib/transactions";
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

function toItems(raw: SessionHistory["transactions"]): MoneyItem[] {
  return raw
    .filter(
      (row): row is SessionHistory["transactions"][number] & { day: number } =>
        typeof row.day === "number" && row.day >= 1 && row.day <= 31,
    )
    .map((row) => ({
      id: row.id,
      direction: row.direction,
      label: row.label,
      amount: row.amount,
      day: row.day,
    }));
}

function toState(detail: SessionHistory): TransactionsState {
  return acceptTransactions(EMPTY_TRANSACTIONS, {
    type: "finance",
    version: 1,
    name: detail.session.name,
    cash: detail.cash ?? null,
    items: toItems(detail.transactions),
    entries: detail.entries ?? [],
    missing: detail.missing ?? [],
    conflicts: [],
    derived: detail.derived,
    plan: detail.plan ?? null,
    advice: detail.advice ?? null,
  });
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
    const money = toState(detail);
    const turns = detail.transcript;
    const title = detail.session.name?.trim() || "Past call";
    const duration = formatDuration(detail.session.duration_seconds);
    const hasMoney = hasBoard(money);
    const hasTurns = turns.length > 0;

    return (
      <AppFrame>
        <div className={styles.callReview}>
          <div className={styles.callReviewBar}>
            <div>
              <h1 className={styles.callReviewTitle}>{title}</h1>
              <p className={styles.callReviewMeta}>
                {formatWhen(detail.session.created_at)}
                {duration ? ` · ${duration}` : ""}
              </p>
            </div>
            <Button variant="secondary" onClick={() => setDetail(null)}>
              All calls
            </Button>
          </div>

          {hasMoney ? (
            <div className={styles.planScroll}>
              <MoneyBoard state={money} />
            </div>
          ) : (
            <div className={styles.reviewEmpty}>
              <p className={styles.reviewEmptyTitle}>
                {hasTurns ? "No money recorded" : "Nothing saved"}
              </p>
              <p className={styles.reviewEmptyCopy}>
                {hasTurns
                  ? "This call has a transcript, but no income or expenses were logged."
                  : "This call ended before anything was recorded."}
              </p>
            </div>
          )}

          {hasTurns ? (
            <div className={styles.recapCompact}>
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
          ) : hasMoney ? (
            <div className={styles.recapCompact}>
              <p className={styles.recapIdle}>No transcript for this call.</p>
            </div>
          ) : null}
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
            <p className={styles.historyMeta}>
              Transcripts and money from earlier sessions.
            </p>
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
          <div className={styles.reviewEmpty}>
            <p className={styles.reviewEmptyCopy}>Loading…</p>
          </div>
        ) : rows.length === 0 ? (
          <div className={styles.reviewEmpty}>
            <p className={styles.reviewEmptyTitle}>No saved calls yet</p>
            <p className={styles.reviewEmptyCopy}>
              Talk to Kubera once and your sessions will show up here.
            </p>
          </div>
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
                      {row.tx_count > 0 ? ` · ${row.tx_count} items` : ""}
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
