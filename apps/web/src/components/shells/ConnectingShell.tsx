import { BreathingOrb, Button, Icon, StatusDot } from "@/components/atoms";
import { AppFrame } from "./AppFrame";
import styles from "./shells.module.css";

type Step = "mic" | "session" | "room" | "assistant";

type ConnectingShellProps = {
  step: Step;
  onCancel?: () => void;
};

const STEPS: { key: Step; label: string }[] = [
  { key: "mic", label: "Microphone" },
  { key: "session", label: "Session started" },
  { key: "room", label: "Joining the room" },
  { key: "assistant", label: "Waking Kubera" },
];

export function ConnectingShell({ step, onCancel }: ConnectingShellProps) {
  const current = STEPS.findIndex((s) => s.key === step);

  return (
    <AppFrame meta={<StatusDot tone="warn" label="Joining" />}>
      <div className={styles.body}>
        <BreathingOrb state="connecting" />
        <div>
          <h1 className={styles.title}>Getting the line ready</h1>
          <p className={styles.hint}>Usually under a few seconds</p>
        </div>

        <ol className={styles.steps}>
          {STEPS.map(({ key, label }, index) => {
            const done = index < current;
            const active = index === current;
            return (
              <li
                key={key}
                className={[
                  styles.step,
                  done ? styles.stepDone : styles.stepPending,
                ].join(" ")}
                aria-current={active ? "step" : undefined}
              >
                {done ? (
                  <span className={styles.check} aria-hidden />
                ) : active ? (
                  <Icon name="spinner" size={14} />
                ) : (
                  <span className={styles.checkIdle} aria-hidden />
                )}
                {label}
              </li>
            );
          })}
        </ol>

        {onCancel ? (
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
      </div>
    </AppFrame>
  );
}
