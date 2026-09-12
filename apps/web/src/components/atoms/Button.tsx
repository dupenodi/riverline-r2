import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Icon } from "./Icon";
import styles from "./atoms.module.css";

export type ButtonVariant =
  | "primary"
  | "secondary"
  | "danger"
  | "ghost"
  | "chip"
  | "start";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  children: ReactNode;
};

export function Button({
  variant = "primary",
  children,
  className,
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={[styles.button, styles[variant], className]
        .filter(Boolean)
        .join(" ")}
      {...rest}
    >
      {variant === "start" ? (
        <>
          <span className={styles.startIcon}>
            <Icon name="microphone" size={14} />
          </span>
          {children}
        </>
      ) : (
        children
      )}
    </button>
  );
}
