import Image from "next/image";
import styles from "./atoms.module.css";

type BrandMarkProps = {
  size?: "md" | "sm";
  showName?: boolean;
};

const sizes = {
  sm: 15,
  md: 20,
} as const;

export function BrandMark({ size = "md", showName = true }: BrandMarkProps) {
  const px = sizes[size];

  return (
    <div className={styles.brand}>
      <Image
        src="/kubera-logo.png"
        alt=""
        width={px}
        height={px}
        className={[
          styles.brandMark,
          size === "sm" ? styles.brandMarkSm : "",
        ]
          .filter(Boolean)
          .join(" ")}
        aria-hidden
      />
      {showName ? (
        <span
          className={[
            styles.brandName,
            size === "sm" ? styles.brandNameSm : "",
          ]
            .filter(Boolean)
            .join(" ")}
        >
          Kubera
        </span>
      ) : null}
    </div>
  );
}
