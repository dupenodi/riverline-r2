import styles from "./atoms.module.css";

type CallTimerProps = {
  /** Elapsed seconds */
  seconds: number;
};

function formatTime(total: number): string {
  const safe = Math.max(0, Math.floor(total));
  const m = Math.floor(safe / 60);
  const s = safe % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function CallTimer({ seconds }: CallTimerProps) {
  return (
    <time className={styles.timer} dateTime={`PT${Math.floor(seconds)}S`}>
      {formatTime(seconds)}
    </time>
  );
}
