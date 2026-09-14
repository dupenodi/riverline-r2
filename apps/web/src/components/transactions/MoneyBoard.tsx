"use client";

import { MoneyCalendar } from "./MoneyCalendar";
import { MoneyRail } from "./MoneyRail";
import type { TransactionsState } from "@/lib/transactions";
import styles from "./board.module.css";

type MoneyBoardProps = {
  state: TransactionsState;
};

export function MoneyBoard({ state }: MoneyBoardProps) {
  return (
    <div className={styles.board}>
      <div className={styles.calPane}>
        <MoneyCalendar state={state} />
      </div>
      <MoneyRail state={state} />
    </div>
  );
}
