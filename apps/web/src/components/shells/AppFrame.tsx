"use client";

import { useState, type ReactNode } from "react";
import { BrandMark } from "@/components/atoms";
import styles from "./shells.module.css";

type AppFrameProps = {
  meta?: ReactNode;
  children: ReactNode;
  transparent?: boolean;
  /**
   * The side panel. Present from the moment the app opens rather than
   * appearing once there is something to put in it: a column that arrives
   * mid-sentence moves everything else on screen, and a user who has never
   * seen it has no reason to expect their numbers anywhere.
   */
  sidebar?: ReactNode;
  /** Bumped when the sidebar's contents change, to mark the phone tab. */
  sidebarVersion?: number;
  sidebarLabel?: string;
};

export function AppFrame({
  meta,
  children,
  transparent = false,
  sidebar = null,
  sidebarVersion = 0,
  sidebarLabel = "What I have",
}: AppFrameProps) {
  // Two panes side by side on a wide screen; one at a time on a phone, where
  // showing both would leave neither legible.
  const [pane, setPane] = useState<"voice" | "cards">("voice");
  // Whatever was on screen the last time the user switched panes. Updates land
  // while they are watching the conversation instead, and the dot is the only
  // hint they get that the other pane moved.
  const [seenVersion, setSeenVersion] = useState(sidebarVersion);
  const unseen = pane !== "cards" && sidebarVersion > seenVersion;

  const show = (next: "voice" | "cards") => {
    setPane(next);
    setSeenVersion(sidebarVersion);
  };

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

      {sidebar ? (
        <>
          <div className={styles.callSplit} data-pane={pane}>
            <div className={styles.callMain}>{children}</div>
            <aside className={styles.callCards} aria-label={sidebarLabel}>
              {sidebar}
            </aside>
          </div>

          {/* Only reachable below the split breakpoint; on a wide screen both
              panes are visible at once and there is nothing to switch. */}
          <nav className={styles.paneTabs} aria-label="View">
            <button
              type="button"
              onClick={() => show("voice")}
              aria-pressed={pane === "voice"}
              className={pane === "voice" ? styles.paneTabOn : styles.paneTab}
            >
              Conversation
            </button>
            <button
              type="button"
              onClick={() => show("cards")}
              aria-pressed={pane === "cards"}
              className={pane === "cards" ? styles.paneTabOn : styles.paneTab}
            >
              {sidebarLabel}
              {unseen ? (
                <i className={styles.paneDot} aria-label="updated" />
              ) : null}
            </button>
          </nav>
        </>
      ) : (
        children
      )}
    </div>
  );
}
