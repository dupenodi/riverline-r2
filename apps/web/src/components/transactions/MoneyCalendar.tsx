"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import {
  dayNet,
  itemsByDay,
  money,
  type MoneyItem,
  type TransactionsState,
} from "@/lib/transactions";
import styles from "./calendar.module.css";

const WEEKDAYS = ["S", "M", "T", "W", "T", "F", "S"];
const POPOVER_ESTIMATE_H = 160;

type Tone = "quiet" | "out" | "in" | "both" | "today";

const TONE_LABEL: Record<Tone, string> = {
  quiet: "Nothing recorded",
  out: "Money going out",
  in: "Money coming in",
  both: "Money in and out",
  today: "Today",
};

function toneFor(dayItems: MoneyItem[], isToday: boolean): Tone {
  if (isToday && dayItems.length === 0) return "today";
  const hasIn = dayItems.some((i) => i.direction === "incoming");
  const hasOut = dayItems.some((i) => i.direction === "outgoing");
  if (hasIn && hasOut) return "both";
  if (hasIn) return "in";
  if (hasOut) return "out";
  if (isToday) return "today";
  return "quiet";
}

function daysInMonth(year: number, monthIndex: number): number {
  return new Date(year, monthIndex + 1, 0).getDate();
}

type Anchor = {
  left: number;
  top: number;
  placeAbove: boolean;
};

type MoneyCalendarProps = {
  state: TransactionsState | { items: MoneyItem[] };
};

export function MoneyCalendar({ state }: MoneyCalendarProps) {
  const items = state.items;
  const [openDay, setOpenDay] = useState<number | null>(null);
  const [anchor, setAnchor] = useState<Anchor | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRefs = useRef<Map<number, HTMLButtonElement>>(new Map());
  const popoverId = useId();

  const now = new Date();
  const year = now.getFullYear();
  const monthIndex = now.getMonth();
  const today = now.getDate();
  const totalDays = daysInMonth(year, monthIndex);
  const firstWeekday = new Date(year, monthIndex, 1).getDay();
  const monthLabel = now.toLocaleString(undefined, {
    month: "long",
    year: "numeric",
  });
  const byDay = itemsByDay(items);

  function close() {
    setOpenDay(null);
    setAnchor(null);
  }

  function placeFromButton(button: HTMLButtonElement): Anchor {
    const rect = button.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    const placeAbove = spaceBelow < POPOVER_ESTIMATE_H;
    return {
      left: rect.left + rect.width / 2,
      top: placeAbove ? rect.top - 6 : rect.bottom + 6,
      placeAbove,
    };
  }

  function openForDay(day: number, button: HTMLButtonElement) {
    setOpenDay((prev) => {
      if (prev === day) {
        setAnchor(null);
        return null;
      }
      setAnchor(placeFromButton(button));
      return day;
    });
  }

  useLayoutEffect(() => {
    if (openDay == null) return;
    const button = buttonRefs.current.get(openDay);
    if (!button) return;
    setAnchor(placeFromButton(button));
  }, [openDay]);

  useEffect(() => {
    if (openDay == null) return;

    const onPointer = (event: MouseEvent) => {
      const target = event.target as Node;
      if (rootRef.current?.contains(target)) return;
      close();
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    const onReposition = () => {
      const button = buttonRefs.current.get(openDay);
      if (!button) {
        close();
        return;
      }
      setAnchor(placeFromButton(button));
    };

    window.addEventListener("mousedown", onPointer);
    window.addEventListener("keydown", onKey);
    window.addEventListener("resize", onReposition);
    window.addEventListener("scroll", onReposition, true);
    return () => {
      window.removeEventListener("mousedown", onPointer);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", onReposition);
      window.removeEventListener("scroll", onReposition, true);
    };
  }, [openDay]);

  if (items.length === 0) return null;

  const openItems = openDay != null ? (byDay.get(openDay) ?? []) : [];
  const openIsToday = openDay === today;
  const openTone =
    openDay != null ? toneFor(openItems, openIsToday) : "quiet";
  const openNet = dayNet(openItems);

  return (
    <div className={styles.wrap} ref={rootRef}>
      <div className={styles.inner}>
        <div className={styles.head}>
          <h2 className={styles.title}>{monthLabel}</h2>
          <p className={styles.legend}>
            <span className={styles.dotIn} aria-hidden /> In
            <span className={styles.dotOut} aria-hidden /> Out
          </p>
        </div>

        <div className={styles.cal}>
          <div className={styles.calHead}>
            {WEEKDAYS.map((letter, index) => (
              <span key={`${letter}-${index}`} className={styles.weekday}>
                {letter}
              </span>
            ))}
          </div>

          <div className={styles.calBody}>
            {Array.from({ length: firstWeekday }, (_, index) => (
              <span key={`pad-${index}`} className={styles.pad} aria-hidden />
            ))}

            {Array.from({ length: totalDays }, (_, index) => {
              const day = index + 1;
              const dayItems = byDay.get(day) ?? [];
              const isToday = day === today;
              const tone = toneFor(dayItems, isToday);
              const open = openDay === day;
              const net = dayNet(dayItems);
              const clickable = dayItems.length > 0;

              return (
                <div
                  key={day}
                  className={[styles.cell, open ? styles.cellOpen : ""]
                    .filter(Boolean)
                    .join(" ")}
                >
                  <span className={styles.cellNum} data-today={isToday}>
                    {day}
                  </span>
                  <button
                    type="button"
                    ref={(el) => {
                      if (el) buttonRefs.current.set(day, el);
                      else buttonRefs.current.delete(day);
                    }}
                    className={[styles.swatch, styles[`tone_${tone}`]].join(" ")}
                    aria-label={`${day} ${monthLabel}. ${TONE_LABEL[tone]}${
                      dayItems.length
                        ? `. Net ${net >= 0 ? "+" : "−"}${money(Math.abs(net))}`
                        : ""
                    }`}
                    aria-expanded={open}
                    aria-controls={open ? popoverId : undefined}
                    disabled={!clickable}
                    onClick={(event) => openForDay(day, event.currentTarget)}
                  />
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {openDay != null && anchor ? (
        <div
          id={popoverId}
          className={[
            styles.popover,
            styles.popoverOpen,
            anchor.placeAbove ? styles.popoverAbove : styles.popoverBelow,
          ].join(" ")}
          role="dialog"
          style={{ left: anchor.left, top: anchor.top }}
        >
          <p className={styles.popoverDate}>
            {openDay} {now.toLocaleString(undefined, { month: "short" })}
            {openIsToday ? " · today" : ""}
          </p>
          {openItems.length === 0 ? (
            <p className={styles.popoverEmpty}>Nothing on this day.</p>
          ) : (
            <>
              <p className={styles.popoverBalance} data-num>
                {openNet >= 0 ? "+" : "−"}
                {money(Math.abs(openNet))}
              </p>
              <p className={styles.popoverTone}>{TONE_LABEL[openTone]}</p>
              <ul className={styles.popoverMoves}>
                {openItems.map((item) => (
                  <li key={item.id}>
                    <span>{item.label}</span>
                    <span data-num>
                      {item.direction === "incoming" ? "+" : "−"}
                      {money(item.amount)}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}
