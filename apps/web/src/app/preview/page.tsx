"use client";

import { useState } from "react";
import { CallShell } from "@/components/shells/CallShell";
import { EndedShell } from "@/components/shells/EndedShell";
import { MoneyCalendar } from "@/components/transactions/MoneyCalendar";
import type { TransactionsState } from "@/lib/transactions";
import styles from "./preview.module.css";

const SAMPLE: TransactionsState = {
  type: "transactions",
  version: 1,
  name: "Priya",
  items: [
    { id: "1", direction: "incoming", label: "Salary", amount: 50000, day: 1 },
    { id: "2", direction: "outgoing", label: "Rent", amount: 20000, day: 5 },
    { id: "3", direction: "outgoing", label: "HDFC EMI", amount: 8500, day: 10 },
    { id: "4", direction: "outgoing", label: "Electricity", amount: 1200, day: 15 },
    { id: "5", direction: "incoming", label: "Freelance", amount: 8000, day: 20 },
  ],
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
      <h1 className={styles.title}>Money calendar preview</h1>
      <MoneyCalendar state={SAMPLE} />
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
