"use client";

import {
  currentPlan,
  factsOfKind,
  type FinanceSnapshot,
} from "@/lib/finance";
import { CashflowCalendar } from "./CashflowCalendar";
import { ConflictCard } from "./ConflictCard";
import { LedgerCard } from "./LedgerCard";
import { MissingInfoCard } from "./MissingInfoCard";
import { PlanCard } from "./PlanCard";
import { PositionCard } from "./PositionCard";
import styles from "./cards.module.css";

/**
 * Every card, in the order they matter, each appearing only once it has
 * something to say. All of it is a pure function of one snapshot, so the screen
 * cannot drift out of step with what the user just heard.
 */
export function FinancePanel({ snapshot }: { snapshot: FinanceSnapshot }) {
  const plan = currentPlan(snapshot);
  const planned = snapshot.plan != null;

  const cutIds = new Set(snapshot.plan?.cut.map((movement) => movement.fact_id) ?? []);
  const minimumIds = new Set(
    snapshot.plan?.actions
      .filter((action) => action.kind === "pay_minimum")
      .map((action) => action.fact_id) ?? [],
  );

  if (!snapshot.facts.length) {
    return (
      <div className={styles.panel}>
        <p className={styles.emptyState}>
          Your month appears here as you talk — what you have, what is due, and
          where it gets tight.
        </p>
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      {plan ? <PositionCard plan={plan} planned={planned} /> : null}
      {snapshot.plan ? <PlanCard plan={snapshot.plan} /> : null}
      {plan ? <CashflowCalendar plan={plan} planned={planned} /> : null}
      <ConflictCard conflicts={snapshot.conflicts} />
      <MissingInfoCard
        missing={snapshot.missing}
        wouldSharpen={snapshot.would_sharpen}
      />
      <LedgerCard kind="balance" facts={factsOfKind(snapshot, "balance")} />
      <LedgerCard kind="income" facts={factsOfKind(snapshot, "income")} />
      <LedgerCard
        kind="essential"
        facts={factsOfKind(snapshot, "essential")}
        cutIds={cutIds}
      />
      <LedgerCard
        kind="debt"
        facts={factsOfKind(snapshot, "debt")}
        minimumIds={minimumIds}
      />
      <LedgerCard
        kind="optional"
        facts={factsOfKind(snapshot, "optional")}
        cutIds={cutIds}
      />
    </div>
  );
}
