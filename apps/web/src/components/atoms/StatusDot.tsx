import styles from "./atoms.module.css";

export type StatusTone = "success" | "warn" | "accent" | "danger" | "muted";

type StatusDotProps = {
  tone?: StatusTone;
  label?: string;
  gap?: "sm" | "md";
};

const toneClass: Record<StatusTone, string> = {
  success: styles.dotSuccess,
  warn: styles.dotWarn,
  accent: styles.dotAccent,
  danger: styles.dotDanger,
  muted: styles.dotMuted,
};

export function StatusDot({
  tone = "success",
  label,
  gap = "sm",
}: StatusDotProps) {
  const dot = (
    <span className={[styles.dot, toneClass[tone]].join(" ")} aria-hidden />
  );

  if (!label) return dot;

  return (
    <span
      className={[styles.status, gap === "md" ? styles.statusGap : ""]
        .filter(Boolean)
        .join(" ")}
    >
      {dot}
      {label}
    </span>
  );
}
