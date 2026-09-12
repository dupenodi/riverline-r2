import { VoiceCall } from "@/components/VoiceCall";
import styles from "./page.module.css";

export default function Home() {
  return (
    <div className={styles.page}>
      <main className={styles.main}>
        <p className={styles.eyebrow}>Riverline take-home</p>
        <h1 className={styles.title}>Voice agent scaffold</h1>
        <p className={styles.lede}>
          Next.js frontend · Pipecat agent · Daily transport. Agent logic not
          wired yet.
        </p>
        <VoiceCall />
      </main>
    </div>
  );
}
