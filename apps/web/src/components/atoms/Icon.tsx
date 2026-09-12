import styles from "./atoms.module.css";

export type IconName =
  | "microphone"
  | "microphone-slash"
  | "phone-slash"
  | "wallet"
  | "check"
  | "list"
  | "spinner";

type IconProps = {
  name: IconName;
  size?: number;
  className?: string;
  "aria-hidden"?: boolean;
};

export function Icon({
  name,
  size = 16,
  className,
  "aria-hidden": ariaHidden = true,
}: IconProps) {
  const stroke = "currentColor";

  return (
    <span
      className={[styles.icon, className].filter(Boolean).join(" ")}
      style={{ width: size, height: size }}
      aria-hidden={ariaHidden}
    >
      {name === "microphone" ? (
        <svg
          className={styles.iconSvg}
          width={size}
          height={size}
          viewBox="0 0 16 16"
          fill="none"
        >
          <rect
            x="5.5"
            y="1.5"
            width="5"
            height="8"
            rx="2.5"
            stroke={stroke}
            strokeWidth="1.4"
          />
          <path
            d="M3.5 7.5a4.5 4.5 0 0 0 9 0"
            stroke={stroke}
            strokeWidth="1.4"
            strokeLinecap="round"
          />
          <path
            d="M8 12v2.5"
            stroke={stroke}
            strokeWidth="1.4"
            strokeLinecap="round"
          />
        </svg>
      ) : null}

      {name === "microphone-slash" ? (
        <svg
          className={styles.iconSvg}
          width={size}
          height={size}
          viewBox="0 0 16 16"
          fill="none"
        >
          <rect
            x="5.5"
            y="1.5"
            width="5"
            height="8"
            rx="2.5"
            stroke={stroke}
            strokeWidth="1.4"
          />
          <path
            d="M3.5 7.5a4.5 4.5 0 0 0 7.2 3.5"
            stroke={stroke}
            strokeWidth="1.4"
            strokeLinecap="round"
          />
          <path
            d="M8 12v2.5M2.5 2.5l11 11"
            stroke={stroke}
            strokeWidth="1.4"
            strokeLinecap="round"
          />
        </svg>
      ) : null}

      {name === "phone-slash" ? (
        <svg
          className={styles.iconSvg}
          width={size}
          height={size}
          viewBox="0 0 16 16"
          fill="none"
        >
          <path
            d="M3.2 6.8c2.2-2.2 7.4-2.2 9.6 0"
            stroke={stroke}
            strokeWidth="1.5"
            strokeLinecap="round"
          />
          <path
            d="M5.2 8.6c1.3-1.2 4.3-1.2 5.6 0"
            stroke={stroke}
            strokeWidth="1.5"
            strokeLinecap="round"
          />
          <path
            d="M2.5 2.5l11 11"
            stroke={stroke}
            strokeWidth="1.4"
            strokeLinecap="round"
          />
        </svg>
      ) : null}

      {name === "wallet" ? (
        <svg
          className={styles.iconSvg}
          width={size}
          height={size}
          viewBox="0 0 16 16"
          fill="none"
        >
          <rect
            x="2"
            y="4"
            width="12"
            height="9"
            rx="1.5"
            stroke={stroke}
            strokeWidth="1.4"
          />
          <path
            d="M2 6.5h12"
            stroke={stroke}
            strokeWidth="1.4"
          />
          <circle cx="11" cy="9.5" r="1" fill={stroke} />
        </svg>
      ) : null}

      {name === "check" ? (
        <svg
          className={styles.iconSvg}
          width={size}
          height={size}
          viewBox="0 0 16 16"
          fill="none"
        >
          <path
            d="M3.5 8.2 6.6 11.2 12.5 4.8"
            stroke={stroke}
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      ) : null}

      {name === "list" ? (
        <svg
          className={styles.iconSvg}
          width={size}
          height={size}
          viewBox="0 0 16 16"
          fill="none"
        >
          <rect
            x="2.5"
            y="3"
            width="11"
            height="10"
            rx="1.5"
            stroke={stroke}
            strokeWidth="1.4"
          />
          <path
            d="M5 6.5h6M5 9.5h6"
            stroke={stroke}
            strokeWidth="1.4"
            strokeLinecap="round"
          />
        </svg>
      ) : null}

      {name === "spinner" ? (
        <span
          style={{
            width: size,
            height: size,
            borderRadius: "50%",
            border: "2px solid var(--spinner-track)",
            borderTopColor: "var(--accent)",
            animation: "spin 0.8s linear infinite",
            display: "block",
          }}
        />
      ) : null}
    </span>
  );
}
