"use client";

import { Card } from "./Card";
import styles from "./cards.module.css";

type MissingInfoCardProps = {
  missing: string[];
  wouldSharpen: string[];
};

/**
 * What is still needed, and — kept deliberately separate — what would only
 * sharpen the answer. Mixing the two once made the agent refuse to plan until
 * it knew which day someone eats out; keeping them apart on screen is the same
 * distinction the planner makes.
 */
export function MissingInfoCard({ missing, wouldSharpen }: MissingInfoCardProps) {
  if (!missing.length && !wouldSharpen.length) return null;

  return (
    <Card
      title={missing.length ? "Still needed" : "Would sharpen this"}
      signature={[...missing, ...wouldSharpen].join("|")}
      tone={missing.length ? "warn" : "plain"}
    >
      {missing.length ? (
        <ul className={styles.checklist}>
          {missing.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}

      {wouldSharpen.length ? (
        <>
          {missing.length ? (
            <p className={styles.subheading}>Nice to know, not required</p>
          ) : null}
          <ul className={styles.checklistSoft}>
            {wouldSharpen.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      ) : null}
    </Card>
  );
}
