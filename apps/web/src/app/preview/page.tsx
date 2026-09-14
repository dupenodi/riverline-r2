"use client";

import { useState } from "react";
import { PlanView } from "@/components/plan/PlanView";
import { CallShell } from "@/components/shells/CallShell";
import { EndedShell } from "@/components/shells/EndedShell";
import fixtures from "@/lib/fixtures/snapshots.json";
import type { FinanceSnapshot } from "@/lib/finance";
import styles from "./preview.module.css";

/**
 * Plan screens driven by recorded planner output instead of a phone call.
 */

const CASES: { key: keyof typeof fixtures; label: string; blurb: string }[] = [
  {
    key: "early",
    label: "Mid-conversation",
    blurb: "A balance and two bills. No plan asked for yet.",
  },
  {
    key: "tight",
    label: "Tight but solvable",
    blurb: "Salary lands after the rent. Works, once two things are put off.",
  },
  {
    key: "unsolvable",
    label: "Does not balance",
    blurb: "Nothing left to cut. The gap is stated, not dressed up.",
  },
];

export default function PreviewPage() {
  const [active, setActive] = useState<keyof typeof fixtures>("tight");
  const [inCall, setInCall] = useState(false);
  const [ended, setEnded] = useState(false);
  const snapshot = fixtures[active] as unknown as FinanceSnapshot;
  const blurb = CASES.find((entry) => entry.key === active)?.blurb;

  if (ended) {
    return (
      <>
        <EndedShell
          durationSeconds={244}
          transcript={[]}
          finance={snapshot}
          reason="user"
          onRestart={() => setEnded(false)}
        />
        <button
          type="button"
          onClick={() => setEnded(false)}
          className={styles.escape}
        >
          Back to cards
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
          finance={snapshot}
          connectionLabel="Preview"
          onMute={() => {}}
          onEnd={() => setInCall(false)}
        />
        <button
          type="button"
          onClick={() => setInCall(false)}
          className={styles.escape}
        >
          Back to cards
        </button>
      </>
    );
  }

  return (
    <main className={styles.page}>
      <header className={styles.head}>
        <h1 className={styles.title}>Plan preview</h1>
        <div className={styles.tabs}>
          {CASES.map((entry) => (
            <button
              key={entry.key}
              type="button"
              onClick={() => setActive(entry.key)}
              className={active === entry.key ? styles.tabOn : styles.tab}
            >
              {entry.label}
            </button>
          ))}
        </div>
        <p className={styles.blurb}>{blurb}</p>
        <button
          type="button"
          onClick={() => setInCall(true)}
          className={styles.tab}
        >
          See it in the call layout
        </button>
        <button
          type="button"
          onClick={() => setEnded(true)}
          className={styles.tab}
        >
          See the hung-up screen
        </button>
      </header>

      {snapshot.plan ? (
        <div className={styles.planStage}>
          <PlanView snapshot={snapshot} />
        </div>
      ) : (
        <p className={styles.blurb}>No plan in this fixture yet.</p>
      )}
    </main>
  );
}
