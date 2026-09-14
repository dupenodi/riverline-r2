"use client";

import Image from "next/image";
import { AppFrame } from "@/components/shells/AppFrame";
import styles from "./WelcomeScreen.module.css";

type WelcomeScreenProps = {
  onStart: () => void;
  busy?: boolean;
};

/**
 * What the four minutes will be about, and nothing else.
 *
 * The three lines under the button are the shape of the conversation. A voice
 * product that opens with only a microphone button leaves the user guessing
 * what they are about to be asked, and they hesitate.
 */
export function WelcomeScreen({ onStart, busy = false }: WelcomeScreenProps) {
  return (
    <AppFrame>
      <div className={styles.body}>
        <Image
          src="/kubera-logo.png"
          alt=""
          width={52}
          height={52}
          className={styles.logo}
          priority
        />
        <h1 className={styles.title}>Thirty days, out loud.</h1>
        <p className={styles.lede}>
          I&rsquo;ll ask you a few things about your money, then work out
          whether the next thirty days hold &mdash; and what to change if they
          don&rsquo;t.
        </p>

        <ol className={styles.steps}>
          <li>
            <span className={styles.stepNum}>1</span>
            What you have, what&rsquo;s coming in, what has to go out
          </li>
          <li>
            <span className={styles.stepNum}>2</span>
            I read it back so you can correct anything
          </li>
          <li>
            <span className={styles.stepNum}>3</span>
            Your thirty days, day by day, with what to change
          </li>
        </ol>

        <button
          type="button"
          className={styles.start}
          onClick={onStart}
          disabled={busy}
        >
          {busy ? "Starting…" : "Start the call"}
        </button>
        <p className={styles.fine}>
          About four minutes &middot; uses your microphone
        </p>
      </div>
    </AppFrame>
  );
}
