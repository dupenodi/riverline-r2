import type { ReactNode } from "react";
import { Button, Icon } from "@/components/atoms";
import { AppFrame } from "./AppFrame";
import styles from "./shells.module.css";

type MicBlockedShellProps = {
  onRetry: () => void;
  onBack: () => void;
  sidebar?: ReactNode;
};

export function MicBlockedShell({
  onRetry,
  onBack,
  sidebar = null,
}: MicBlockedShellProps) {
  return (
    <AppFrame sidebar={sidebar}>
      <div className={styles.body}>
        <div className={styles.micBlockedIcon} aria-hidden>
          <Icon name="microphone-slash" size={18} />
        </div>
        <div>
          <h1 className={styles.title}>I can&apos;t hear you yet</h1>
          <p className={styles.subtitle}>
            Your browser is blocking the microphone for this page. Allow it in
            the address bar, then try again.
          </p>
        </div>
        <div className={styles.actions}>
          <Button variant="primary" onClick={onRetry}>
            Try the microphone again
          </Button>
          <Button variant="secondary" onClick={onBack}>
            Back
          </Button>
        </div>
      </div>
    </AppFrame>
  );
}
