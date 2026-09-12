import styles from "./atoms.module.css";

type HearingStripProps = {
  text?: string;
  partial?: string;
  active?: boolean;
};

export function HearingStrip({
  text = "",
  partial = "",
  active = true,
}: HearingStripProps) {
  return (
    <div className={styles.hearing}>
      <div className={styles.hearingMeta}>
        {active ? (
          <div className={styles.waveform} aria-hidden>
            <span className={styles.waveBar} />
            <span className={styles.waveBar} />
            <span className={styles.waveBar} />
            <span className={styles.waveBar} />
          </div>
        ) : null}
        <span
          className={[
            styles.hearingLabel,
            active ? "" : styles.hearingIdle,
          ]
            .filter(Boolean)
            .join(" ")}
        >
          {active ? "Hearing you" : "You said"}
        </span>
      </div>
      <p className={styles.hearingText}>
        {text}
        {partial ? (
          <span className={styles.hearingPartial}>{partial}</span>
        ) : null}
      </p>
    </div>
  );
}
