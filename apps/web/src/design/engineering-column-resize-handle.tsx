import type { KeyboardEvent, PointerEvent } from "react";
import { COLUMN_RESIZE_KEYBOARD_STEP } from "./metrics";

interface EngineeringColumnResizeHandleProps {
  label: string;
  width: number;
  min: number;
  max: number;
  onChange: (width: number) => void;
}

export function EngineeringColumnResizeHandle({ label, width, min, max, onChange }: EngineeringColumnResizeHandleProps) {
  const clamp = (value: number) => Math.max(min, Math.min(max, value));

  function beginResize(event: PointerEvent<HTMLSpanElement>): void {
    event.preventDefault();
    document.documentElement.classList.add("engineering-column-resizing");
    const startX = event.clientX;
    const startWidth = width;
    const move = (moveEvent: globalThis.PointerEvent) => onChange(clamp(startWidth + moveEvent.clientX - startX));
    const stop = () => {
      document.documentElement.classList.remove("engineering-column-resizing");
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop, { once: true });
  }

  function resizeWithKeyboard(event: KeyboardEvent<HTMLSpanElement>): void {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    onChange(clamp(width + (event.key === "ArrowRight" ? COLUMN_RESIZE_KEYBOARD_STEP : -COLUMN_RESIZE_KEYBOARD_STEP)));
  }

  return <span className="engineering-column-resize-handle" role="separator" aria-label={`Resize ${label} column`} aria-orientation="vertical" aria-valuemin={min} aria-valuemax={max} aria-valuenow={width} tabIndex={0} onPointerDown={beginResize} onKeyDown={resizeWithKeyboard} />;
}
