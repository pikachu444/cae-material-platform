import { useCallback, useEffect, useState } from "react";

interface PolymerFitChartSizeOptions {
  fallbackWidth: number;
  fallbackHeight: number;
  minWidth: number;
  minHeight: number;
}

/** Keeps feature-owned SVG coordinates aligned with the actual plot pane. */
export function usePolymerFitChartSize({
  fallbackWidth,
  fallbackHeight,
  minWidth,
  minHeight,
}: PolymerFitChartSizeOptions) {
  const [element, setElement] = useState<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ width: fallbackWidth, height: fallbackHeight });
  const ref = useCallback((node: HTMLDivElement | null) => setElement(node), []);

  useEffect(() => {
    if (!element || typeof ResizeObserver === "undefined") return undefined;
    const update = () => {
      const bounds = element.getBoundingClientRect();
      if (bounds.width < 1 || bounds.height < 1) return;
      setSize({
        width: Math.max(minWidth, Math.round(bounds.width)),
        height: Math.max(minHeight, Math.round(bounds.height)),
      });
    };
    const observer = new ResizeObserver(update);
    observer.observe(element);
    update();
    return () => observer.disconnect();
  }, [element, minHeight, minWidth]);

  return { ref, size };
}
