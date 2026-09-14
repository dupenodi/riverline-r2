"use client";

import { useState } from "react";
import { CallShell } from "@/components/shells/CallShell";
import { EndedShell } from "@/components/shells/EndedShell";
import { MoneyBoard } from "@/components/transactions/MoneyBoard";
import type {
  DerivedDay,
  DerivedMove,
  DerivedState,
  TransactionsState,
} from "@/lib/transactions";
import styles from "./preview.module.css";

const START = { y: 2026, m: 9, d: 14 };

function iso(y: number, m: number, d: number): string {
  const dt = new Date(y, m - 1, d);
  const yy = dt.getFullYear();
  const mm = String(dt.getMonth() + 1).padStart(2, "0");
  const dd = String(dt.getDate()).padStart(2, "0");
  return `${yy}-${mm}-${dd}`;
}

function walk(
  cash: number,
  ledger: Record<string, { inn: number; out: number; moves: DerivedMove[] }>,
): DerivedState {
  const days: DerivedDay[] = [];
  let closing = cash;
  let crunch = { date: iso(START.y, START.m, START.d), amount: cash };
  for (let i = 0; i < 30; i++) {
    const dt = new Date(START.y, START.m - 1, START.d + i);
    const key = iso(dt.getFullYear(), dt.getMonth() + 1, dt.getDate());
    const hit = ledger[key] ?? { inn: 0, out: 0, moves: [] };
    closing = closing + hit.inn - hit.out;
    days.push({
      date: key,
      in: hit.inn,
      out: hit.out,
      closing,
      moves: hit.moves,
    });
    if (closing < crunch.amount) crunch = { date: key, amount: closing };
  }
  return { finish: closing, crunch, days };
}

const SAMPLE: TransactionsState = {
  type: "finance",
  version: 4,
  name: "Priya",
  cash: 10000,
  items: [
    { id: "sal", direction: "incoming", label: "Salary", amount: 50000, day: 1 },
    { id: "rent", direction: "outgoing", label: "Rent", amount: 20000, day: 5 },
    { id: "emi", direction: "outgoing", label: "HDFC EMI", amount: 8500, day: 10 },
    { id: "elec", direction: "outgoing", label: "Electricity", amount: 1200, day: 15 },
    { id: "free", direction: "incoming", label: "Freelance", amount: 8000, day: 20 },
    { id: "card", direction: "outgoing", label: "Card", amount: 22000, day: 21 },
    { id: "flix", direction: "outgoing", label: "Netflix", amount: 499, day: 25 },
  ],
  entries: [
    {
      id: "sal",
      kind: "income",
      label: "Salary",
      amount: 50000,
      amount_min: null,
      amount_max: null,
      day: 1,
      cadence: "monthly",
      status: "paid",
    },
    {
      id: "free",
      kind: "income",
      label: "Freelance",
      amount: 8000,
      amount_min: null,
      amount_max: null,
      day: 20,
      cadence: "once",
      status: "unknown",
    },
    {
      id: "rent",
      kind: "need",
      label: "Rent",
      amount: 20000,
      amount_min: null,
      amount_max: null,
      day: 5,
      cadence: "monthly",
      status: "due",
    },
    {
      id: "elec",
      kind: "need",
      label: "Electricity",
      amount: 1200,
      amount_min: null,
      amount_max: null,
      day: 15,
      cadence: "monthly",
      status: "due",
    },
    {
      id: "card",
      kind: "debt",
      label: "Card",
      amount: 22000,
      amount_min: null,
      amount_max: null,
      day: 21,
      cadence: "monthly",
      status: "due",
    },
    {
      id: "emi",
      kind: "debt",
      label: "HDFC EMI",
      amount: 8500,
      amount_min: null,
      amount_max: null,
      day: 10,
      cadence: "monthly",
      status: "due",
    },
    {
      id: "flix",
      kind: "flex",
      label: "Netflix",
      amount: 499,
      amount_min: null,
      amount_max: null,
      day: 25,
      cadence: "monthly",
      status: "due",
    },
    {
      id: "zom",
      kind: "flex",
      label: "Zomato",
      amount: 200,
      amount_min: null,
      amount_max: null,
      day: null,
      cadence: "daily",
      status: "unknown",
    },
  ],
  missing: [],
  conflicts: ["Card: 20000 then 22000"],
  derived: walk(10000, {
    "2026-09-15": {
      inn: 0,
      out: 1200,
      moves: [{ id: "elec", label: "Electricity", amount: 1200, kind: "need" }],
    },
    "2026-09-20": {
      inn: 8000,
      out: 0,
      moves: [{ id: "free", label: "Freelance", amount: 8000, kind: "income" }],
    },
    "2026-09-21": {
      inn: 0,
      out: 22000,
      moves: [{ id: "card", label: "Card", amount: 22000, kind: "debt" }],
    },
    "2026-09-25": {
      inn: 0,
      out: 499,
      moves: [{ id: "flix", label: "Netflix", amount: 499, kind: "flex" }],
    },
    "2026-10-01": {
      inn: 50000,
      out: 0,
      moves: [{ id: "sal", label: "Salary", amount: 50000, kind: "income" }],
    },
    "2026-10-05": {
      inn: 0,
      out: 20000,
      moves: [{ id: "rent", label: "Rent", amount: 20000, kind: "need" }],
    },
    "2026-10-10": {
      inn: 0,
      out: 8500,
      moves: [{ id: "emi", label: "HDFC EMI", amount: 8500, kind: "debt" }],
    },
  }),
  plan: {
    solvable: false,
    steps: [
      { action: "delay", label: "Netflix", amount: 499, until: "2026-09-20" },
      { action: "pay_minimum", label: "Card", amount: 5000 },
      { action: "short", label: "gap", amount: 1000 },
    ],
    gap: 1000,
    gap_date: "2026-09-21",
  },
  advice: {
    points: [
      "Card ₹22,000 is due 21 Sep, before salary returns on 1 Oct — paying the ₹5,000 minimum keeps the bureau clean without emptying the month.",
      "Netflix ₹499 on 25 Sep can wait until freelance ₹8,000 lands on 20 Sep.",
      "Zomato ₹200 every day is ₹6,000 over 30 days; a cheaper week of cooking would cover the card minimum gap.",
    ],
    payoff: {
      lowest: -5699,
      date: "2026-09-25",
      ok: false,
      finish: 15801,
    },
  },
};

export default function PreviewPage() {
  const [inCall, setInCall] = useState(false);
  const [ended, setEnded] = useState(false);

  if (ended) {
    return (
      <>
        <EndedShell
          durationSeconds={244}
          transcript={[]}
          transactions={SAMPLE}
          reason="user"
          onRestart={() => setEnded(false)}
        />
        <button
          type="button"
          onClick={() => setEnded(false)}
          className={styles.escape}
        >
          Back
        </button>
      </>
    );
  }

  if (inCall) {
    return (
      <>
        <CallShell
          elapsedSeconds={187}
          muted={false}
          agentSpeaking={false}
          userSpeaking={false}
          thinking={false}
          transcript={[]}
          transactions={SAMPLE}
          connectionLabel="Preview"
          onMute={() => {}}
          onEnd={() => setInCall(false)}
        />
        <button
          type="button"
          onClick={() => setInCall(false)}
          className={styles.escape}
        >
          Back
        </button>
      </>
    );
  }

  return (
    <main className={styles.page}>
      <h1 className={styles.title}>Money board preview</h1>
      <div className={styles.frame}>
        <MoneyBoard state={SAMPLE} />
      </div>
      <div className={styles.actions}>
        <button type="button" onClick={() => setInCall(true)}>
          In call
        </button>
        <button type="button" onClick={() => setEnded(true)}>
          Ended
        </button>
      </div>
    </main>
  );
}
