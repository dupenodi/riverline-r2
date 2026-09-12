import styles from "./atoms.module.css";

export type VoiceMood = "idle" | "listening" | "speaking" | "muted" | "ending";

type AmbientBackdropProps = {
  mood?: VoiceMood;
  /** Quicker motion when user audio is coming in */
  active?: boolean;
};

export function AmbientBackdrop({
  mood = "idle",
  active = false,
}: AmbientBackdropProps) {
  return (
    <div
      className={[styles.ambient, active ? styles.ambientActive : ""]
        .filter(Boolean)
        .join(" ")}
      data-mood={mood}
      aria-hidden
    >
      <div className={styles.ambientBase} />
      <div className={styles.ambientBlobA} />
      <div className={styles.ambientBlobB} />
      <div className={styles.ambientBlobC} />
      <div className={styles.ambientWash} />
    </div>
  );
}
