"use client";

import type { ReactNode } from "react";
import styles from "./shells.module.css";

type AppFrameProps = {
  meta?: ReactNode;
  children: ReactNode;
  transparent?: boolean;
};

export function AppFrame({
  meta,
  children,
  transparent = false,
}: AppFrameProps) {
  return (
    <div
      className={[styles.frame, transparent ? styles.frameTransparent : ""]
        .filter(Boolean)
        .join(" ")}
    >
      {meta ? (
        <header
          className={[
            styles.topBar,
            transparent ? styles.topBarTransparent : "",
          ]
            .filter(Boolean)
            .join(" ")}
        >
          <div className={styles.topMeta}>{meta}</div>
        </header>
      ) : null}

      <div className={styles.main}>{children}</div>
    </div>
  );
}
