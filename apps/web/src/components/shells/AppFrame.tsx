"use client";

import type { ReactNode } from "react";
import { BrandMark } from "@/components/atoms";
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
      <header
        className={[
          styles.topBar,
          transparent ? styles.topBarTransparent : "",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        <BrandMark size="sm" />
        {meta ? <div className={styles.topMeta}>{meta}</div> : null}
      </header>

      <div className={styles.main}>{children}</div>
    </div>
  );
}
