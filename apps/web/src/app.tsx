import { Suspense, useEffect, useMemo } from "react";
import { ApplicationShell } from "./design/application-shell";
import { DisplayDensityProvider } from "./design/display-density";
import { useBrowserNavigation } from "./app/navigation";
import {
  ProductSessionBoundary,
  useProductSession,
} from "./app/product-session";
import { RouteComposition } from "./app/route-composition";
import { parseAppRoute } from "./app/routes";

export function App() {
  const { location, navigate, replace } = useBrowserNavigation();
  const route = useMemo(() => parseAppRoute(location), [location]);
  const session = useProductSession();

  useEffect(() => {
    if (route.id === "root-redirect") replace(route.to);
  }, [replace, route]);

  if (session.status !== "ready") {
    return (
      <div className="session-shell">
        <main>
          <ProductSessionBoundary
            loading={session.status === "loading"}
            onRetry={session.retry}
          />
        </main>
      </div>
    );
  }

  return (
    <DisplayDensityProvider config={session.config}>
      <ApplicationShell path={route.pathname} navigate={navigate}>
        <Suspense fallback={<p className="loading-state">Loading workspace…</p>}>
          <RouteComposition
            route={route}
            config={session.config}
            navigate={navigate}
            onOpenConnection={session.retry}
          />
        </Suspense>
      </ApplicationShell>
    </DisplayDensityProvider>
  );
}
