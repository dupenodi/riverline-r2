"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import {
  dayNet,
  itemsByDay,
  money,
  type DerivedDay,
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

function toneForMoves(day: DerivedDay, isToday: boolean): Tone {
  if (isToday && day.moves.length === 0) return "today";
  const hasIn = day.in > 0;
  const hasOut = day.out > 0;
  if (hasIn && hasOut) return "both";
  if (hasIn) return "in";
  if (hasOut) return "out";
  if (isToday) return "today";
  return "quiet";
}

function toneForItems(dayItems: MoneyItem[], isToday: boolean): Tone {
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

function parseISODate(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function formatRange(days: DerivedDay[]): string {
  const start = parseISODate(days[0].date);
  const end = parseISODate(days[days.length - 1].date);
  const a = start.toLocaleString(undefined, { day: "numeric", month: "short" });
  const b = end.toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
  return `${a} – ${b}`;
}

type Anchor = {
  left: number;
  top: number;
  placeAbove: boolean;
};

type MoneyCalendarProps = {
  state: TransactionsState | { items: MoneyItem[]; derived?: TransactionsState["derived"] };
};

export function MoneyCalendar({ state }: MoneyCalendarProps) {
  const derived = "derived" in state ? state.derived : null;
  const rolling = derived?.days && derived.days.length === 30 ? derived : null;
  if (rolling) {
    return <RollingCalendar days={rolling.days} crunchDate={rolling.crunch.date} />;
  }
  return <MonthCalendar items={"items" in state ? state.items : []} />;
}

function RollingCalendar({
  days,
  crunchDate,
}: {
  days: DerivedDay[];
  crunchDate: string;
}) {
  const [openDate, setOpenDate] = useState<string | null>(null);
  const [anchor, setAnchor] = useState<Anchor | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRefs = useRef<Map<string, HTMLButtonElement>>(new Map());
  const popoverId = useId();
  const todayIso = days[0].date;
  const firstWeekday = parseISODate(todayIso).getDay();
  const openDay = openDate ? days.find((d) => d.date === openDate) : null;

  function close() {
    setOpenDate(null);
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

  function openFor(date: string, button: HTMLButtonElement) {
    setOpenDate(date);
    setAnchor(placeFromButton(button));
  }

  useLayoutEffect(() => {
    if (openDate == null) return;
    const button = buttonRefs.current.get(openDate);
    if (!button) return;
    setAnchor(placeFromButton(button));
  }, [openDate]);

  useEffect(() => {
    if (openDate == null) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    const onReposition = () => {
      const button = buttonRefs.current.get(openDate);
      if (!button) {
        close();
        return;
      }
      setAnchor(placeFromButton(button));
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("resize", onReposition);
    window.addEventListener("scroll", onReposition, true);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", onReposition);
      window.removeEventListener("scroll", onReposition, true);
    };
  }, [openDate]);

  return (
    <div className={styles.wrap} ref={rootRef}>
      <div className={styles.inner}>
        <div className={styles.head}>
          <h2 className={styles.title}>{formatRange(days)}</h2>
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
            {days.map((day, index) => {
              const date = parseISODate(day.date);
              const isToday = index === 0;
              const monthStart =
                index === 0 ||
                parseISODate(days[index - 1].date).getMonth() !== date.getMonth();
              const tone = toneForMoves(day, isToday);
              const crunch = day.date === crunchDate;
              const hoverable = isToday || day.moves.length > 0;
              const open = openDate === day.date;
              return (
                <div
                  key={day.date}
                  className={[styles.cell, open ? styles.cellOpen : ""]
                    .filter(Boolean)
                    .join(" ")}
                  data-short={day.closing < 0 ? "true" : undefined}
                  data-crunch={crunch ? "true" : undefined}
                  onMouseEnter={
                    hoverable
                      ? () => {
                          const button = buttonRefs.current.get(day.date);
                          if (button) openFor(day.date, button);
                        }
                      : undefined
                  }
                  onMouseLeave={hoverable ? close : undefined}
                >
                  <span
                    className={styles.cellNum}
                    data-today={isToday}
                    data-month={monthStart && !isToday ? "start" : undefined}
                  >
                    {monthStart && !isToday
                      ? date.toLocaleString(undefined, { day: "numeric", month: "short" })
                      : date.getDate()}
                  </span>
                  <button
                    type="button"
                    ref={(el) => {
                      if (el) buttonRefs.current.set(day.date, el);
                      else buttonRefs.current.delete(day.date);
                    }}
                    className={[styles.swatch, styles[`tone_${tone}`]].join(" ")}
                    aria-label={`${date.toDateString()}. ${TONE_LABEL[tone]}. Close ${money(day.closing)}`}
                    aria-expanded={open}
                    aria-controls={open ? popoverId : undefined}
                    disabled={!hoverable}
                    tabIndex={hoverable ? 0 : -1}
                    onFocus={
                      hoverable
                        ? (event) => openFor(day.date, event.currentTarget)
                        : undefined
                    }
                    onBlur={hoverable ? close : undefined}
                  />
                </div>
              );
            })}
          </div>
        </div>
      </div>
      {openDay && anchor ? (
        <div
          id={popoverId}
          className={[
            styles.popover,
            styles.popoverOpen,
            anchor.placeAbove ? styles.popoverAbove : styles.popoverBelow,
          ].join(" ")}
          role="tooltip"
          style={{ left: anchor.left, top: anchor.top }}
        >
          <p className={styles.popoverDate}>
            {parseISODate(openDay.date).toLocaleString(undefined, {
              day: "numeric",
              month: "short",
            })}
            {openDay.date === todayIso ? " · today" : ""}
            {openDay.date === crunchDate ? " · crunch" : ""}
          </p>
          <p className={styles.popoverBalance} data-num>
            {openDay.closing < 0 ? "−" : ""}
            {money(Math.abs(openDay.closing))}
          </p>
          <p className={styles.popoverTone}>{TONE_LABEL[toneForMoves(openDay, openDay.date === todayIso)]}</p>
          {openDay.moves.length === 0 ? (
            <p className={styles.popoverEmpty}>Nothing on this day.</p>
          ) : (
            <ul className={styles.popoverMoves}>
              {openDay.moves.map((move) => (
                <li key={`${move.id}-${move.label}`}>
                  <span>{move.label}</span>
                  <span data-num>
                    {move.kind === "income" ? "+" : "−"}
                    {money(move.amount)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}

function MonthCalendar({ items }: { items: MoneyItem[] }) {
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
    setOpenDay(day);
    setAnchor(placeFromButton(button));
  }

  useLayoutEffect(() => {
    if (openDay == null) return;
    const button = buttonRefs.current.get(openDay);
    if (!button) return;
    setAnchor(placeFromButton(button));
  }, [openDay]);

  useEffect(() => {
    if (openDay == null) return;
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
    window.addEventListener("keydown", onKey);
    window.addEventListener("resize", onReposition);
    window.addEventListener("scroll", onReposition, true);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", onReposition);
      window.removeEventListener("scroll", onReposition, true);
    };
  }, [openDay]);

  if (items.length === 0) return null;

  const openItems = openDay != null ? (byDay.get(openDay) ?? []) : [];
  const openIsToday = openDay === today;
  const openTone = openDay != null ? toneForItems(openItems, openIsToday) : "quiet";
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
              const tone = toneForItems(dayItems, isToday);
              const open = openDay === day;
              const net = dayNet(dayItems);
              const hoverable = isToday || dayItems.length > 0;
              return (
                <div
                  key={day}
                  className={[styles.cell, open ? styles.cellOpen : ""]
                    .filter(Boolean)
                    .join(" ")}
                  onMouseEnter={
                    hoverable
                      ? () => {
                          const button = buttonRefs.current.get(day);
                          if (button) openForDay(day, button);
                        }
                      : undefined
                  }
                  onMouseLeave={hoverable ? close : undefined}
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
                    disabled={!hoverable}
                    tabIndex={hoverable ? 0 : -1}
                    onFocus={
                      hoverable
                        ? (event) => openForDay(day, event.currentTarget)
                        : undefined
                    }
                    onBlur={hoverable ? close : undefined}
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
          role="tooltip"
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
