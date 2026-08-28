import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useLayoutEffect,
  useMemo,
  useState,
} from "react";

import {
  type ApiConfig,
} from "../shared/api";

export type DisplayDensity = "compact" | "standard" | "large";

export const DISPLAY_DENSITY_ATTRIBUTE = "data-display-density";
export const DISPLAY_DENSITY_EVENT = "cmp:display-density-change";
export const DISPLAY_DENSITY_STORAGE_KEY =
  "cmp.material-platform.client-preferences.v1";
export const DEFAULT_DISPLAY_DENSITY: DisplayDensity = "standard";

export const DISPLAY_DENSITY_CHOICES: ReadonlyArray<{
  value: DisplayDensity;
  label: string;
}> = [
  { value: "compact", label: "Compact" },
  { value: "standard", label: "Standard" },
  { value: "large", label: "Large" },
];

interface ClientPreferenceEnvelope {
  version: 1;
  displayDensityByScope: Record<string, DisplayDensity>;
}

interface DisplayDensityContextValue {
  density: DisplayDensity;
  setDensity: (density: DisplayDensity) => void;
  resetDensity: () => void;
}

interface DisplayDensityProviderProps {
  config: ApiConfig;
  children: ReactNode;
}

const defaultContext: DisplayDensityContextValue = {
  density: DEFAULT_DISPLAY_DENSITY,
  setDensity: () => undefined,
  resetDensity: () => undefined,
};

const DisplayDensityContext =
  createContext<DisplayDensityContextValue>(defaultContext);

function isDisplayDensity(value: unknown): value is DisplayDensity {
  return value === "compact" || value === "standard" || value === "large";
}

function readJwtClaims(accessToken: string): Record<string, unknown> {
  const payload = accessToken.split(".")[1];
  if (!payload || typeof window === "undefined") return {};
  try {
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(
      normalized.length + ((4 - (normalized.length % 4)) % 4),
      "=",
    );
    const bytes = Uint8Array.from(window.atob(padded), (character) =>
      character.charCodeAt(0),
    );
    const decoded: unknown = JSON.parse(new TextDecoder().decode(bytes));
    return typeof decoded === "object" && decoded !== null
      ? (decoded as Record<string, unknown>)
      : {};
  } catch {
    return {};
  }
}

function claim(
  claims: Record<string, unknown>,
  ...names: string[]
): string | undefined {
  for (const name of names) {
    const value = claims[name];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return undefined;
}

export function displayDensityScope(config: ApiConfig): string {
  const claims = readJwtClaims(config.accessToken);
  const values = [
    config.baseUrl.replace(/\/$/, "") || "local-api",
    claim(claims, "organization_id", "org_id") ?? "local-organization",
    claim(claims, "workspace_id", "project_id") ?? "local-workspace",
    claim(claims, "principal_id", "sub", "user_id") ?? "anonymous",
  ];
  return values.map((value) => encodeURIComponent(value)).join("|");
}

function emptyEnvelope(): ClientPreferenceEnvelope {
  return { version: 1, displayDensityByScope: {} };
}

function writeEnvelope(
  storage: Storage,
  envelope: ClientPreferenceEnvelope,
): void {
  try {
    storage.setItem(DISPLAY_DENSITY_STORAGE_KEY, JSON.stringify(envelope));
  } catch {
    // Browser-local preferences are optional; Standard remains a safe fallback.
  }
}

function readEnvelope(
  storage: Storage,
  scope: string,
): ClientPreferenceEnvelope {
  let raw: string | null = null;
  try {
    raw = storage.getItem(DISPLAY_DENSITY_STORAGE_KEY);
  } catch {
    return emptyEnvelope();
  }
  if (raw === null) return emptyEnvelope();

  try {
    const candidate: unknown = JSON.parse(raw);
    if (
      typeof candidate !== "object" ||
      candidate === null ||
      !("version" in candidate) ||
      candidate.version !== 1 ||
      !("displayDensityByScope" in candidate) ||
      typeof candidate.displayDensityByScope !== "object" ||
      candidate.displayDensityByScope === null ||
      Array.isArray(candidate.displayDensityByScope)
    ) {
      throw new Error("Unsupported client preference envelope");
    }

    const source = candidate.displayDensityByScope as Record<string, unknown>;
    const repaired = emptyEnvelope();
    let changed = false;
    for (const [key, value] of Object.entries(source)) {
      if (isDisplayDensity(value)) repaired.displayDensityByScope[key] = value;
      else changed = true;
    }
    if (!isDisplayDensity(source[scope])) {
      repaired.displayDensityByScope[scope] = DEFAULT_DISPLAY_DENSITY;
      changed = true;
    }
    if (changed) writeEnvelope(storage, repaired);
    return repaired;
  } catch {
    const repaired = emptyEnvelope();
    repaired.displayDensityByScope[scope] = DEFAULT_DISPLAY_DENSITY;
    writeEnvelope(storage, repaired);
    return repaired;
  }
}

export function readDisplayDensity(
  config: ApiConfig,
  storage: Storage = window.localStorage,
): DisplayDensity {
  const scope = displayDensityScope(config);
  return (
    readEnvelope(storage, scope).displayDensityByScope[scope] ??
    DEFAULT_DISPLAY_DENSITY
  );
}

export function applyDisplayDensity(density: DisplayDensity): void {
  if (typeof document === "undefined") return;
  const safeDensity = isDisplayDensity(density)
    ? density
    : DEFAULT_DISPLAY_DENSITY;
  const previous = document.documentElement.getAttribute(
    DISPLAY_DENSITY_ATTRIBUTE,
  );
  document.documentElement.setAttribute(
    DISPLAY_DENSITY_ATTRIBUTE,
    safeDensity,
  );
  if (previous !== safeDensity && typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent<{ density: DisplayDensity }>(DISPLAY_DENSITY_EVENT, {
        detail: { density: safeDensity },
      }),
    );
  }
}

export function bootstrapDisplayDensity(config: ApiConfig): DisplayDensity {
  const density = readDisplayDensity(config);
  applyDisplayDensity(density);
  return density;
}

export function persistDisplayDensity(
  config: ApiConfig,
  density: DisplayDensity,
  storage: Storage = window.localStorage,
): DisplayDensity {
  const safeDensity = isDisplayDensity(density)
    ? density
    : DEFAULT_DISPLAY_DENSITY;
  const scope = displayDensityScope(config);
  const envelope = readEnvelope(storage, scope);
  envelope.displayDensityByScope[scope] = safeDensity;
  writeEnvelope(storage, envelope);
  applyDisplayDensity(safeDensity);
  return safeDensity;
}

export function DisplayDensityProvider({
  config,
  children,
}: DisplayDensityProviderProps) {
  const scope = displayDensityScope(config);
  const [density, setDensityState] = useState<DisplayDensity>(() =>
    bootstrapDisplayDensity(config),
  );

  useLayoutEffect(() => {
    const restored = bootstrapDisplayDensity(config);
    setDensityState(restored);
  }, [config, scope]);

  const setDensity = useCallback(
    (next: DisplayDensity) => {
      setDensityState(persistDisplayDensity(config, next));
    },
    [config],
  );

  const resetDensity = useCallback(() => {
    setDensityState(
      persistDisplayDensity(config, DEFAULT_DISPLAY_DENSITY),
    );
  }, [config]);

  const value = useMemo(
    () => ({ density, setDensity, resetDensity }),
    [density, resetDensity, setDensity],
  );

  return (
    <DisplayDensityContext.Provider value={value}>
      {children}
    </DisplayDensityContext.Provider>
  );
}

export function useDisplayDensity(): DisplayDensityContextValue {
  return useContext(DisplayDensityContext);
}
