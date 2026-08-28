import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  type ApiConfig,
} from "../shared/api";
import mainSource from "../main.tsx?raw";
import { ApplicationShell } from "./application-shell";
import {
  bootstrapDisplayDensity,
  DisplayDensityProvider,
  DISPLAY_DENSITY_ATTRIBUTE,
  DISPLAY_DENSITY_EVENT,
  DISPLAY_DENSITY_STORAGE_KEY,
  displayDensityScope,
  persistDisplayDensity,
  readDisplayDensity,
} from "./display-density";

function token(claims: Record<string, string>): string {
  const payload = window
    .btoa(JSON.stringify(claims))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
  return `header.${payload}.signature`;
}

function config(
  user = "user-a",
  workspace = "workspace-a",
): ApiConfig {
  return {
    baseUrl: "/api/v1",
    accessToken: token({
      sub: user,
      organization_id: "organization-a",
      project_id: workspace,
    }),
  };
}

beforeEach(() => {
  window.localStorage.clear();
  document.documentElement.removeAttribute(DISPLAY_DENSITY_ATTRIBUTE);
});

describe("display density preference", () => {
  it("uses Standard by default and applies a saved value before the shell mounts", () => {
    expect(bootstrapDisplayDensity(config())).toBe("standard");
    expect(
      document.documentElement.getAttribute(DISPLAY_DENSITY_ATTRIBUTE),
    ).toBe("standard");

    persistDisplayDensity(config(), "compact");
    document.documentElement.removeAttribute(DISPLAY_DENSITY_ATTRIBUTE);

    expect(bootstrapDisplayDensity(config())).toBe("compact");
    expect(
      document.documentElement.getAttribute(DISPLAY_DENSITY_ATTRIBUTE),
    ).toBe("compact");
  });

  it("keeps one product-wide value per active user and workspace scope", () => {
    const first = config("user-a", "workspace-a");
    const second = config("user-a", "workspace-b");
    const third = config("user-b", "workspace-a");

    persistDisplayDensity(first, "compact");
    persistDisplayDensity(second, "large");

    expect(displayDensityScope(first)).not.toBe(displayDensityScope(second));
    expect(displayDensityScope(first)).not.toBe(displayDensityScope(third));
    expect(readDisplayDensity(first)).toBe("compact");
    expect(readDisplayDensity(second)).toBe("large");
    expect(readDisplayDensity(third)).toBe("standard");
  });

  it("repairs malformed, legacy, and unsupported values to Standard", () => {
    window.localStorage.setItem(DISPLAY_DENSITY_STORAGE_KEY, "not-json");
    expect(bootstrapDisplayDensity(config())).toBe("standard");

    const repaired = JSON.parse(
      window.localStorage.getItem(DISPLAY_DENSITY_STORAGE_KEY) ?? "null",
    ) as { version: number; displayDensityByScope: Record<string, string> };
    expect(repaired.version).toBe(1);
    expect(
      repaired.displayDensityByScope[displayDensityScope(config())],
    ).toBe("standard");

    window.localStorage.setItem(
      DISPLAY_DENSITY_STORAGE_KEY,
      JSON.stringify({
        version: 1,
        displayDensityByScope: {
          [displayDensityScope(config())]: "comfortable",
        },
      }),
    );
    expect(readDisplayDensity(config())).toBe("standard");
  });

  it("exposes keyboard-native selection and a density-only reset in the shell", () => {
    const onDensityChange = vi.fn();
    window.addEventListener(DISPLAY_DENSITY_EVENT, onDensityChange);
    render(
      <DisplayDensityProvider config={config()}>
        <ApplicationShell path="/materials" navigate={vi.fn()}>
          <p>Workspace</p>
        </ApplicationShell>
      </DisplayDensityProvider>,
    );

    fireEvent.click(screen.getByText("Demo user"));
    const large = screen.getByRole("radio", { name: "Large" });
    large.focus();
    fireEvent.click(large);
    expect((large as HTMLInputElement).checked).toBe(true);
    expect(readDisplayDensity(config())).toBe("large");

    fireEvent.keyDown(large, { key: "Escape" });
    const densityMenuSummary = screen.getByText("Demo user").closest("summary");
    expect(
      screen.getByText("Demo user").closest("details")?.hasAttribute("open"),
    ).toBe(false);
    expect(document.activeElement).toBe(densityMenuSummary);

    fireEvent.click(densityMenuSummary!);

    fireEvent.click(
      screen.getByRole("button", { name: "Reset display density" }),
    );
    expect(
      (screen.getByRole("radio", { name: "Standard" }) as HTMLInputElement)
        .checked,
    ).toBe(true);
    expect(readDisplayDensity(config())).toBe("standard");
    expect(onDensityChange).toHaveBeenCalled();
    window.removeEventListener(DISPLAY_DENSITY_EVENT, onDensityChange);
  });

  it("boots the density attribute before React creates the root", () => {
    expect(mainSource.indexOf("bootstrapDisplayDensity(loadApiConfig())")).toBeGreaterThan(
      -1,
    );
    expect(mainSource.indexOf("bootstrapDisplayDensity(loadApiConfig())")).toBeLessThan(
      mainSource.indexOf("createRoot(document.getElementById"),
    );
  });
});
