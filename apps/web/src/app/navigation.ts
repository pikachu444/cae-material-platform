import { useCallback, useEffect, useState } from "react";

export type Navigate = (path: string) => void;

export interface BrowserNavigation {
  location: string;
  navigate: Navigate;
  replace: Navigate;
}

function currentBrowserLocation(): string {
  return `${window.location.pathname || "/"}${window.location.search}`;
}

function scrollToWorkspaceStart(): void {
  if (
    !window.navigator.userAgent.includes("jsdom") &&
    typeof window.scrollTo === "function"
  ) {
    window.scrollTo({ top: 0, left: 0 });
  }
}

/** Browser history remains the URL source of truth; React stores only its current projection. */
export function useBrowserNavigation(): BrowserNavigation {
  const [location, setLocation] = useState(currentBrowserLocation);

  useEffect(() => {
    const onPopState = () => setLocation(currentBrowserLocation());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = useCallback<Navigate>((nextPath) => {
    if (nextPath === currentBrowserLocation()) return;
    window.history.pushState({}, "", nextPath);
    setLocation(currentBrowserLocation());
    scrollToWorkspaceStart();
  }, []);

  const replace = useCallback<Navigate>((nextPath) => {
    if (nextPath === currentBrowserLocation()) return;
    window.history.replaceState({}, "", nextPath);
    setLocation(currentBrowserLocation());
  }, []);

  return { location, navigate, replace };
}
