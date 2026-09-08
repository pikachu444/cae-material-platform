import type { ButtonHTMLAttributes, PropsWithChildren } from "react";
import styles from "./Button.module.css";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "quiet" | "danger";
  size?: "sm" | "md";
}

export function Button({ variant = "secondary", size = "md", className = "", children, ...props }: PropsWithChildren<ButtonProps>) {
  return (
    <button className={`${styles.button} ${styles[variant]} ${styles[size]} ${className}`} {...props}>
      {children}
    </button>
  );
}
