import { useEffect, useRef } from "react";

function resultsRegion(): HTMLElement | null {
  return document.querySelector<HTMLElement>('[data-reader-scroll="connected"]')
    ?? document.querySelector<HTMLElement>('[data-reader-workspace="connected"]');
}

export function useReaderReturnFocus(expanded: boolean, previewClosed = false) {
  const scrollTop = useRef(0);
  const focusId = useRef<string | null>(null);

  const remember = (id: string) => {
    const region = resultsRegion();
    scrollTop.current = region?.scrollTop ?? 0;
    focusId.current = id;
  };

  useEffect(() => {
    if (expanded || !focusId.current) return;
    const id = focusId.current;
    const frame = window.requestAnimationFrame(() => {
      const region = resultsRegion();
      region?.scrollTo?.({ top: scrollTop.current, behavior: "auto" });
      document.querySelector<HTMLButtonElement>(`[data-result-row-id="${id}"]`)?.focus({ preventScroll: true });
      focusId.current = null;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [expanded, previewClosed]);

  return remember;
}
