"use client";

import { useEffect, useId, useRef, useState } from "react";
import {
  longDate,
  money,
  type DayCell,
  type Movement,
  type Plan,
} from "@/lib/finance";
import styles from "./plan.module.css";

/**
 * Thirty days as a weekday grid: date number + one colour per day.
 * Click the colour for that day's balance and movements.
 */

const WEEKDAYS = ["S", "M", "T", "W", "T", "F", "S"];

type Tone = "quiet" | "out" | "in" | "low" | "today";

function ambientIds(plan: Plan): Set<string> {
  const seen = new Map<string, number>();
  for (const cell of plan.timeline) {
    for (const movement of cell.movements) {
      seen.set(movement.fact_id, (seen.get(movement.fact_id) ?? 0) + 1);
    }
  }
  const threshold = Math.max(2, Math.round(plan.timeline.length / 3));
  return new Set(
    [...seen.entries()]
      .filter(([, days]) => days >= threshold)
      .map(([id]) => id),
  );
}

function toneFor(
  cell: DayCell,
  lowestDay: string,
  isToday: boolean,
  landed: Movement[],
): Tone {
  if (cell.day === lowestDay) return "low";
  if (isToday) return "today";
  if (!landed.length) return "quiet";
  if (landed.some((movement) => movement.kind === "income")) return "in";
  return "out";
}

const TONE_LABEL: Record<Tone, string> = {
  quiet: "Quiet day",
  out: "Money going out",
  in: "Money coming in",
  low: "Lowest balance",
  today: "Today",
};

export function MonthCalendar({ plan }: { plan: Plan }) {
  const [openDay, setOpenDay] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const popoverId = useId();

  useEffect(() => {
    if (!openDay) return;

    const onPointer = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpenDay(null);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpenDay(null);
    };

    window.addEventListener("mousedown", onPointer);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onPointer);
      window.removeEventListener("keydown", onKey);
    };
  }, [openDay]);

  if (!plan.timeline.length) return null;

  const lowest = plan.timeline.reduce((low, cell) =>
    cell.balance < low.balance ? cell : low,
  );
  const firstDay = new Date(`${plan.timeline[0].day}T00:00:00`).getDay();
  const ambient = ambientIds(plan);

  return (
    <div className={styles.cal} ref={rootRef}>
      <div className={styles.calHead}>
        {WEEKDAYS.map((letter, index) => (
          <span key={index} className={styles.weekday}>
            {letter}
          </span>
        ))}
      </div>

      <div className={styles.calBody}>
        {Array.from({ length: firstDay }, (_, index) => (
          <span key={`pad-${index}`} className={styles.pad} aria-hidden />
        ))}

        {plan.timeline.map((cell) => {
          const date = new Date(`${cell.day}T00:00:00`);
          const dayNumber = date.getDate();
          const isToday = cell.index === 0;
          const landed = cell.movements.filter(
            (movement) => !ambient.has(movement.fact_id),
          );
          const tone = toneFor(cell, lowest.day, isToday, landed);
          const open = openDay === cell.day;

          return (
            <div
              key={cell.day}
              className={[styles.cell, open ? styles.cellOpen : ""]
                .filter(Boolean)
                .join(" ")}
            >
              <span className={styles.cellNum}>
                <span className="num">{dayNumber}</span>
                {dayNumber === 1 ? (
                  <em className={styles.cellMonth}>
                    {date.toLocaleDateString("en-IN", { month: "short" })}
                  </em>
                ) : null}
              </span>

              <button
                type="button"
                className={[styles.swatch, styles[`tone_${tone}`]].join(" ")}
                aria-label={`${longDate(cell.day)}: ${TONE_LABEL[tone]}`}
                aria-expanded={open}
                aria-controls={open ? popoverId : undefined}
                onClick={() => setOpenDay(open ? null : cell.day)}
              />

              <div
                id={open ? popoverId : undefined}
                role="dialog"
                aria-label={longDate(cell.day)}
                aria-hidden={!open}
                className={[styles.popover, open ? styles.popoverOpen : ""]
                  .filter(Boolean)
                  .join(" ")}
              >
                <p className={styles.popoverDate}>{longDate(cell.day)}</p>
                <p className={`num ${styles.popoverBalance}`}>
                  {money(cell.balance)}
                </p>
                <p className={styles.popoverTone}>{TONE_LABEL[tone]}</p>
                {landed.length ? (
                  <ul className={styles.popoverMoves}>
                    {landed.map((movement) => (
                      <li key={`${movement.fact_id}-${movement.label}`}>
                        <span>{movement.label}</span>
                        <span className="num">
                          {movement.kind === "income" ? "+" : "−"}
                          {money(movement.amount)}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className={styles.popoverEmpty}>Nothing lands this day.</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
