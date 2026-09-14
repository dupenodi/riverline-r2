import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  EMPTY_TRANSACTIONS,
  acceptTransactions,
  entryAmount,
  hasBoard,
  hasCalendar,
} from "./transactions.ts";

describe("acceptTransactions", () => {
  it("keeps a newer snapshot and drops an older one", () => {
    const first = acceptTransactions(EMPTY_TRANSACTIONS, {
      type: "finance",
      version: 2,
      cash: 10000,
      entries: [
        {
          id: "rent",
          kind: "need",
          label: "Rent",
          amount: 20000,
          day: 5,
          cadence: "monthly",
          status: "due",
        },
      ],
      missing: [],
      conflicts: [],
      plan: { solvable: true, gap: null, gap_date: null },
    });
    const stale = acceptTransactions(first, {
      type: "finance",
      version: 1,
      cash: 1,
    });
    assert.equal(stale.cash, 10000);
    assert.equal(stale.entries[0]?.label, "Rent");
  });

  it("parses entries, missing, conflicts, and plan", () => {
    const next = acceptTransactions(EMPTY_TRANSACTIONS, {
      type: "finance",
      version: 1,
      cash: 8000,
      entries: [
        {
          id: "card",
          kind: "debt",
          label: "Card",
          amount: 22000,
          amount_min: null,
          day: 21,
          cadence: "monthly",
          status: "due",
        },
      ],
      missing: ["available"],
      conflicts: ["Card: 20000 then 22000"],
      plan: {
        solvable: false,
        gap: 1000,
        gap_date: "2026-09-21",
      },
    });
    assert.equal(next.cash, 8000);
    assert.equal(next.entries[0]?.kind, "debt");
    assert.deepEqual(next.missing, ["available"]);
    assert.equal(next.conflicts[0], "Card: 20000 then 22000");
    assert.equal(next.plan?.gap, 1000);
  });

  it("accepts owed as an incoming kind", () => {
    const next = acceptTransactions(EMPTY_TRANSACTIONS, {
      type: "finance",
      version: 1,
      cash: 10000,
      entries: [
        {
          id: "k",
          kind: "owed",
          label: "Karthik",
          amount: 5000,
          day: 24,
          cadence: "once",
          status: "due",
          on_date: "2026-09-24",
        },
      ],
      missing: [],
      conflicts: [],
      plan: {
        solvable: true,
        gap: null,
        gap_date: null,
      },
    });
    assert.equal(next.entries[0]?.kind, "owed");
    assert.equal(next.entries[0]?.on_date, "2026-09-24");
    assert.equal(next.plan?.solvable, true);
  });

  it("keeps overdue hits on derived", () => {
    const days = Array.from({ length: 30 }, (_, i) => {
      const day = 14 + i;
      const date =
        day <= 30 ? `2026-09-${String(day).padStart(2, "0")}` : `2026-10-${String(day - 30).padStart(2, "0")}`;
      return {
        date,
        in: 0,
        out: 0,
        closing: 40000,
        moves: [],
      };
    });
    const next = acceptTransactions(EMPTY_TRANSACTIONS, {
      type: "finance",
      version: 1,
      cash: 50000,
      derived: {
        finish: 30000,
        crunch: { date: "2026-10-05", amount: 30000 },
        days,
        overdue: [
          {
            id: "rent",
            label: "Rent",
            amount: 10000,
            kind: "need",
            date: "2026-09-05",
          },
        ],
      },
    });
    assert.equal(next.derived?.overdue?.[0]?.date, "2026-09-05");
  });
});

describe("board helpers", () => {
  it("shows a board when only cash or entries exist", () => {
    assert.equal(hasCalendar(EMPTY_TRANSACTIONS), false);
    assert.equal(hasBoard(EMPTY_TRANSACTIONS), false);
    const cashOnly = acceptTransactions(EMPTY_TRANSACTIONS, {
      type: "finance",
      version: 1,
      cash: 500,
    });
    assert.equal(hasBoard(cashOnly), true);
  });

  it("formats a range with a tilde", () => {
    assert.equal(
      entryAmount({
        id: "x",
        kind: "flex",
        label: "Food",
        amount: null,
        amount_min: 400,
        amount_max: 600,
        day: null,
        cadence: "daily",
        status: "unknown",
      }),
      "~₹400–₹600",
    );
  });
});
