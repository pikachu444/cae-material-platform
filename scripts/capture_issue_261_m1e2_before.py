"""Bounded before-capture/provenance probe for issue #261 M1E2.

This is deliberately issue-specific: it records the current Modeling shell/family
selectors, focused state screenshots, and stylesheet rule provenance before the
M1E2 relocation. It is not a reusable browser framework.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

TARGET_SELECTORS = [
    ".modeling-stage-shell",
    ".modeling-stage-shell button",
    ".modeling-stage-shell button:last-child",
    ".modeling-stage-shell .modeling-stage-number",
    ".modeling-work-title",
    ".modeling-context-actions",
    ".modeling-advanced-menu",
    ".modeling-advanced-menu > summary",
    ".modeling-advanced-menu > summary::-webkit-details-marker",
    ".modeling-advanced-menu > div",
    ".modeling-advanced-menu button",
    ".modeling-advanced-menu button:hover",
    '.modeling-advanced-menu button[aria-selected="true"]',
    ".modeling-stage-shell",
    ".modeling-stage-shell button:nth-child(3)",
    ".modeling-stage-shell button:nth-child(-n + 3)",
    ".modeling-section-actions .method-registry-strip",
    ".modeling-split-workspace",
    ".modeling-main-panel",
    ".modeling-main-surface",
    ".modeling-split-workspace-no-navigator .modeling-main-surface",
    ".modeling-main-surface.has-dock",
    ".modeling-task-ribbon",
    ".modeling-workspace-shell",
    ".modeling-task-ribbon > .step-option-panel",
    (
        ".modeling-task-ribbon > .step-option-panel > "
        ":is(.workspace-inspector-heading, .section-heading)"
    ),
    ".modeling-main-surface > .persistent-modeling-plot",
    ".modeling-workspace-dock",
    ".modeling-main-surface.has-dock > .persistent-modeling-plot",
    ".modeling-ribbon-actions",
    ".modeling-ribbon-actions label",
    ".modeling-conflict-banner",
    ".modeling-conflict-banner > div",
    ".modeling-conflict-banner span",
    ".modeling-graph-workspace:not(.inspector-visible) .step-option-panel",
    ".modeling-section-actions",
    ".modeling-workspace-rail::-webkit-scrollbar",
    ".modeling-workspace-rail::-webkit-scrollbar-track",
    ".modeling-workspace-rail::-webkit-scrollbar-thumb",
    ".modeling-graph-workspace.inspector-visible .step-option-panel",
    ".persistent-modeling-plot > :is(.stage-diagnostics, .model-diagnostics-details, .digest-line)",
    ".modeling-main-surface",
    ".modeling-dataset-list",
    ".configured-step-list",
    ".configured-step-list > button.configured-step-add",
    ".dataset-curve-swatch",
    ".curve-visibility-toggle svg",
    '.curve-visibility-toggle[aria-pressed="true"]',
    ".rail-heading p",
    ".rail-statistics-action",
    ".rail-statistics-action > summary",
    ".rail-statistics-action small",
    ".configured-step-list > button > span:first-child",
    ".configured-step-list > button > span:last-child",
    ".curve-row-label > span",
    ".workspace-inspector-heading",
    ".workspace-inspector-heading p",
    ".advanced-workflow-settings .workspace-inspector-tabs",
    ".modeling-graph-workspace:not(.inspector-visible) .step-option-panel",
    ".modeling-graph-workspace.inspector-visible .step-option-panel",
    ".modeling-stage-shell button",
    ".modeling-context-actions",
    ".modeling-section-actions",
    ".modeling-ribbon-actions",
    ".modeling-advanced-menu > div",
    ".modeling-advanced-menu button",
    ".modeling-workspace-rail::-webkit-scrollbar",
    ".modeling-workspace-rail::-webkit-scrollbar-thumb",
    ".modeling-main-surface",
    ".method-registry-strip",
    ".method-pill",
    ".method-pill:hover",
    ".method-pill small",
    ".modeling-plot-empty",
    ".modeling-plot-empty p",
    ".workspace-inspector-tabs",
    ".workspace-inspector-tabs button",
    ".workspace-inspector-tabs span",
    ".modeling-support-drawer > summary",
    ".modeling-support-drawer > summary::-webkit-details-marker",
    ".modeling-support-drawer > summary > span:first-child",
    ".modeling-support-drawer > summary strong",
    ".modeling-support-drawer > summary small",
    ".modeling-support-drawer > summary > span:last-child",
    ".modeling-support-drawer[open] > summary",
    ".empty-tab-state",
    ".empty-tab-state p",
    ".family-modeling-panel",
    ".family-modeling-heading",
    ".family-modeling-heading h2",
    ".family-modeling-heading p:last-child",
    ".family-context-bar",
    ".family-context-bar label",
    ".family-context-bar select",
    ".family-context-error",
    ".family-modeling-heading",
    ".family-context-bar",
]

VIEWPORTS = [(1366, 768), (1440, 900), (1920, 1080), (2560, 1440), (3840, 2160)]
BREAKPOINTS = [(1181, 900), (1180, 900), (901, 768), (900, 768), (861, 768), (860, 768)]


def _safe_name(value: str) -> str:
    return value.replace("/", "-").replace("?", "-").replace("=", "-").replace("&", "-")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--phase", required=True, choices=("before", "after"))
    args = parser.parse_args()
    output = Path(args.output)
    states = output / "states"
    crops = output / "crops"
    states.mkdir(parents=True, exist_ok=True)
    crops.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900}, device_scale_factor=1
        )

        def capture(
            route: str, viewport: tuple[int, int], label: str, *, full: bool = False
        ) -> None:
            page = context.new_page()
            page_errors: list[str] = []
            console_errors: list[str] = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.on(
                "console",
                lambda message: (
                    console_errors.append(message.text) if message.type == "error" else None
                ),
            )
            page.set_viewport_size({"width": viewport[0], "height": viewport[1]})
            page.goto(f"{args.base_url}{route}", wait_until="networkidle")
            page.wait_for_timeout(1200)
            name = (
                f"{_safe_name(route.strip('/')) or 'modeling'}-{label}-{viewport[0]}x{viewport[1]}"
            )
            page.screenshot(path=str(states / f"{name}.png"), full_page=full)
            for crop_name, selector in {
                "header": "header",
                "navigator": ".modeling-stage-shell",
                "controls": ".modeling-task-ribbon",
                "graph": ".persistent-modeling-plot, .modeling-plot-empty",
            }.items():
                locator = page.locator(selector).first
                if locator.count() and locator.is_visible():
                    try:
                        locator.screenshot(path=str(crops / f"{name}-{crop_name}-100pct.png"))
                    except Exception:
                        pass
            provenance = page.evaluate(
                """
                (selectors) => {
                  const specificity = (selector) => {
                    const ids = (selector.match(/#[\\w-]+/g) || []).length;
                    const classes = (
                      selector.match(/\\.[\\w-]+|\\[[^\\]]+\\]|:(?!:)[\\w-]+/g) || []
                    ).length;
                    const elements = (
                      selector
                        .replace(/#[\\w-]+|\\.[\\w-]+|\\[[^\\]]+\\]|:{1,2}[\\w-]+/g, ' ')
                        .match(/(^|[ >+~])([a-z][\\w-]*)/gi) || []
                    ).length;
                    return [ids, classes, elements].join('-');
                  };
                  const rules = [];
                  const visit = (list, atContext, href) => {
                    for (const rule of Array.from(list || [])) {
                      if (rule.type === CSSRule.STYLE_RULE) {
                        rules.push({
                          selector: rule.selectorText,
                          specificity: specificity(rule.selectorText),
                          declaration: rule.style.cssText,
                          atContext,
                          sourceUrl: href,
                        });
                      } else if (rule.cssRules) {
                        visit(
                          rule.cssRules,
                          [...atContext, rule.conditionText || rule.name || ''],
                          href,
                        );
                      }
                    }
                  };
                  for (const sheet of Array.from(document.styleSheets)) {
                    try {
                      visit(sheet.cssRules, [], sheet.href || location.href);
                    } catch (_) {
                      /* cross-origin sheet */
                    }
                  }
                  const computedKeys = [
                    'display', 'position', 'visibility', 'opacity', 'color',
                    'backgroundColor', 'borderTopWidth', 'borderBottomWidth',
                    'gridTemplateColumns', 'gridTemplateRows', 'gap', 'padding',
                    'margin', 'width', 'height', 'minWidth', 'maxWidth',
                    'overflow', 'overflowX', 'overflowY',
                  ];
                  return selectors.map((selector) => {
                    const pseudo = selector.includes('::');
                    if (pseudo) return {selector, queryable: false, reason: 'pseudo-selector'};
                    let elements = [];
                    try {
                      elements = Array.from(document.querySelectorAll(selector)).slice(0, 3);
                    } catch (_) {
                      return {selector, queryable: false, reason: 'invalid-selector'};
                    }
                    return {
                      selector,
                      queryable: true,
                      matches: elements.map((element) => {
                        const computed = getComputedStyle(element);
                        return {
                          tag: element.tagName.toLowerCase(),
                          className: element.className,
                          bounds: element.getBoundingClientRect().toJSON(),
                          computed: Object.fromEntries(
                            computedKeys.map((key) => [key, computed[key]]),
                          ),
                          matchedRules: rules.filter((rule) => {
                            try {
                              return element.matches(rule.selector);
                            } catch (_) {
                              return false;
                            }
                          }),
                        };
                      }),
                    };
                  });
                }
                """,
                TARGET_SELECTORS,
            )
            stage_navigation_evidence = page.evaluate(
                """
                (assertBoundary) => {
                  const shell = document.querySelector('.modeling-stage-shell');
                  if (!shell) {
                    throw new Error(
                      'stage-shell boundary probe: .modeling-stage-shell is missing',
                    );
                  }
                  const shellRect = shell.getBoundingClientRect();
                  const viewport = { width: window.innerWidth, height: window.innerHeight };
                  const expectedStages = ['Data', 'Process', 'Fit', 'Export'];
                  const shellVisible = shellRect.width > 0
                    && shellRect.height > 0
                    && shellRect.bottom > 0
                    && shellRect.top < viewport.height;
                  const buttons = Array.from(shell.querySelectorAll('button'));
                  const records = buttons.map((button) => {
                    const rect = button.getBoundingClientRect();
                    const style = getComputedStyle(button);
                    const label = (
                      button.querySelector('strong')?.textContent || button.textContent || ''
                    ).trim();
                    const visible = style.display !== 'none'
                      && style.visibility !== 'hidden'
                      && Number(style.opacity) > 0
                      && rect.width > 0
                      && rect.height > 0
                      && rect.bottom > 0
                      && rect.right > 0
                      && rect.top < viewport.height
                      && rect.left < viewport.width;
                    const withinShellBounds = rect.left >= shellRect.left - 0.5
                      && rect.right <= shellRect.right + 0.5
                      && rect.top >= shellRect.top - 0.5
                      && rect.bottom <= shellRect.bottom + 0.5;
                    const reachable = visible
                      && !button.disabled
                      && button.tabIndex >= 0
                      && style.pointerEvents !== 'none';
                    return {
                      label,
                      bounds: rect.toJSON(),
                      visible,
                      withinShellBounds,
                      reachable,
                    };
                  });
                  const stage = (name) => records.find((record) => record.label === name) || null;
                  const allFourRendered = expectedStages.every((name) => stage(name) !== null);
                  const allFourVisible = expectedStages.every(
                    (name) => stage(name)?.visible === true,
                  );
                  const allFourWithinShellBounds = expectedStages.every(
                    (name) => stage(name)?.withinShellBounds === true,
                  );
                  const allFourReachable = expectedStages.every(
                    (name) => stage(name)?.reachable === true,
                  );
                  const exactlyFourButtons = buttons.length === expectedStages.length;
                  const passed = shellVisible
                    && exactlyFourButtons
                    && allFourRendered
                    && allFourVisible
                    && allFourWithinShellBounds
                    && allFourReachable;
                  if (assertBoundary && !passed) {
                    throw new Error(
                      `stage-shell boundary probe failed: count=${buttons.length}`
                      + ` rendered=${allFourRendered} visible=${allFourVisible}`
                      + ` withinShell=${allFourWithinShellBounds}`
                      + ` reachable=${allFourReachable}`,
                    );
                  }
                  return {
                    expectedStages,
                    buttonCount: buttons.length,
                    shellVisible,
                    shellBounds: shellRect.toJSON(),
                    buttons: records,
                    allFourRendered,
                    allFourVisible,
                    allFourWithinShellBounds,
                    allFourReachable,
                    assertion: assertBoundary ? 'pass' : 'not-required-for-non-boundary',
                  };
                }
                """,
                args.phase == "after" and label == "breakpoint" and viewport[0] <= 900,
            )
            records.append(
                {
                    "route": route,
                    "viewport": viewport,
                    "label": label,
                    "provenance": provenance,
                    "stageNavigationEvidence": stage_navigation_evidence,
                    "pageErrors": list(page_errors),
                    "consoleErrors": list(console_errors),
                }
            )
            page.close()

        def capture_state(route: str, label: str) -> None:
            page = context.new_page()
            page_errors: list[str] = []
            console_errors: list[str] = []
            state_evidence: dict[str, Any] = {"requested": label, "valid": True, "actions": []}
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.on(
                "console",
                lambda message: (
                    console_errors.append(message.text) if message.type == "error" else None
                ),
            )
            page.goto(f"{args.base_url}{route}", wait_until="networkidle")
            page.wait_for_timeout(1200)
            if label == "stage-hover":
                button = page.locator(".modeling-stage-shell button").first
                if not button.count():
                    raise RuntimeError("stage-hover target is missing")
                button.hover()
                state_evidence["actions"].append("hovered first stage button")
            elif label == "advanced-open":
                details = page.locator("details.modeling-advanced-menu")
                if details.count() != 1:
                    raise RuntimeError(
                        "advanced-open requires exactly one details.modeling-advanced-menu"
                    )
                summary = details.locator(":scope > summary")
                summary.scroll_into_view_if_needed()
                if not details.locator(":scope[open]").count():
                    summary.click()
                if not details.evaluate("element => element.open"):
                    raise RuntimeError("advanced-open target did not open")
                state_evidence["actions"].append("opened details.modeling-advanced-menu")
                state_evidence["target"] = "details.modeling-advanced-menu"
            elif label == "selected-pressed":
                button = page.locator(
                    ".modeling-stage-shell button, .workspace-inspector-tabs button, [aria-pressed]"
                ).first
                if not button.count():
                    raise RuntimeError("selected-pressed target is missing")
                button.click()
                state_evidence["actions"].append("clicked first selectable pressed control")
            elif label == "candidate-parameters-dock":
                trigger = page.get_by_role("button", name="Candidate parameters", exact=True)
                if trigger.count() != 1:
                    raise RuntimeError(
                        "candidate-parameters-dock requires exactly one Candidate parameters button"
                    )
                trigger.scroll_into_view_if_needed()
                if trigger.get_attribute("aria-expanded") != "true":
                    trigger.click()
                dock = page.locator(".modeling-workspace-dock")
                if dock.count() != 1 or not dock.is_visible():
                    raise RuntimeError(
                        "candidate-parameters-dock did not open .modeling-workspace-dock"
                    )
                if trigger.get_attribute("aria-expanded") != "true":
                    raise RuntimeError("Candidate parameters trigger is not aria-expanded=true")
                state_evidence["actions"].append("opened Candidate parameters workspace dock")
                state_evidence["target"] = (
                    "button[aria-label='Candidate parameters'] -> .modeling-workspace-dock"
                )
            elif label == "reload-resume":
                page.reload(wait_until="networkidle")
                page.wait_for_timeout(900)
                state_evidence["actions"].append("reloaded the route and waited for resume")
            page.screenshot(
                path=str(states / f"{_safe_name(route.strip('/'))}-{label}-1440x900.png")
            )
            provenance = page.evaluate(
                """
                (selectors) => {
                  const rules = [];
                  const visit = (list, atContext, href) => {
                    for (const rule of Array.from(list || [])) {
                      if (rule.type === CSSRule.STYLE_RULE) {
                        const idCount = (rule.selectorText.match(/#[\\w-]+/g) || []).length;
                        const classCount = (
                          rule.selectorText.match(
                            /\\.[\\w-]+|\\[[^\\]]+\\]|:(?!:)[\\w-]+/g,
                          ) || []
                        ).length;
                        rules.push({
                          selector: rule.selectorText,
                          specificity: `${idCount}-${classCount}-0`,
                          declaration: rule.style.cssText,
                          atContext,
                          sourceUrl: href,
                        });
                      } else if (rule.cssRules) {
                        visit(
                          rule.cssRules,
                          [...atContext, rule.conditionText || rule.name || ''],
                          href,
                        );
                      }
                    }
                  };
                  for (const sheet of Array.from(document.styleSheets)) {
                    try {
                      visit(sheet.cssRules, [], sheet.href || location.href);
                    } catch (_) {}
                  }
                  const keys = [
                    'display', 'position', 'visibility', 'color', 'backgroundColor',
                    'borderTopWidth', 'borderBottomWidth', 'gridTemplateColumns',
                    'gridTemplateRows', 'gap', 'padding', 'margin', 'width', 'height',
                    'overflow', 'overflowX', 'overflowY',
                  ];
                  return selectors.map((selector) => {
                    if (selector.includes('::')) {
                      return {selector, queryable: false, reason: 'pseudo-selector'};
                    }
                    let elements = [];
                    try {
                      elements = Array.from(document.querySelectorAll(selector)).slice(0, 3);
                    } catch (_) {
                      return {selector, queryable: false, reason: 'invalid-selector'};
                    }
                    return {
                      selector,
                      queryable: true,
                      matches: elements.map((element) => {
                        const style = getComputedStyle(element);
                        return {
                          tag: element.tagName.toLowerCase(),
                          className: element.className,
                          bounds: element.getBoundingClientRect().toJSON(),
                          computed: Object.fromEntries(
                            keys.map((key) => [key, style[key]]),
                          ),
                          matchedRules: rules.filter((rule) => {
                            try {
                              return element.matches(rule.selector);
                            } catch (_) {
                              return false;
                            }
                          }),
                        };
                      }),
                    };
                  });
                }
                """,
                TARGET_SELECTORS,
            )
            records.append(
                {
                    "route": route,
                    "viewport": [1440, 900],
                    "label": label,
                    "stateEvidence": state_evidence,
                    "provenance": provenance,
                    "pageErrors": list(page_errors),
                    "consoleErrors": list(console_errors),
                }
            )
            page.close()

        for route in ("/modeling?stage=data", "/datasets/processing?stage=data"):
            for viewport in VIEWPORTS:
                capture(route, viewport, "normal")
            for viewport in BREAKPOINTS:
                capture(route, viewport, "breakpoint")
            for label in ("stage-hover", "selected-pressed", "advanced-open"):
                capture_state(route, label)
            capture_state(route, "reload-resume")

        capture_state("/modeling?stage=fit", "candidate-parameters-dock")

        invalid_state_records = [
            {
                "route": record["route"],
                "label": record["label"],
                "reason": record["stateEvidence"].get("reason", "state assertion failed"),
            }
            for record in records
            if not record.get("stateEvidence", {}).get("valid", True)
        ]
        (output / "cascade-provenance.json").write_text(
            json.dumps(
                {
                    "baseUrl": args.base_url,
                    "captureMetadata": {
                        "browserZoomPercent": 100,
                        "deviceScaleFactor": 1,
                        "visualViewportScale": 1,
                        "phase": args.phase,
                        "evidenceStatus": (
                            f"{args.phase}-relocation; every captured state has an explicit "
                            "successful state assertion"
                        ),
                    },
                    "testOnlyStateContracts": [
                        {
                            "label": "stale-recipe-conflict",
                            "status": "N/A",
                            "reason": (
                                "No pre-existing exact fixture safely produces this server "
                                "conflict; M1E2 does not invent a behavior test for CSS "
                                "relocation."
                            ),
                            "tests": [],
                        },
                        {
                            "label": "family-context-error",
                            "tests": [
                                (
                                    "apps/web/src/material-modeling-workspace.test.tsx::blocks a "
                                    "stale URL Material revision instead of substituting its "
                                    "current head"
                                ),
                                (
                                    "apps/web/src/material-modeling-workspace.test.tsx::blocks a "
                                    "stale URL State revision instead of substituting its current "
                                    "head"
                                ),
                            ],
                        },
                        {
                            "label": "hidden-support-drawer",
                            "status": "test-only/N/A for live capture",
                            "reason": "The core layout intentionally hides this companion.",
                            "tests": [
                                (
                                    "apps/web/src/common-processing-workbench.test.tsx::"
                                    "characterizes exact Data, Process, Fit, and Export continuity "
                                    "with explicit recovery"
                                )
                            ],
                        },
                        {
                            "label": "uncalculated-process-plot",
                            "status": "test-only/N/A for live capture",
                            "reason": (
                                "The canonical seeded route resumes its saved Process preview, "
                                "and no immediate deterministic UI action guarantees an empty "
                                "plot without mutating demo data."
                            ),
                            "tests": [
                                (
                                    "apps/web/src/common-processing-workbench.test.tsx::restores "
                                    "history settings as a draft while preserving the saved "
                                    "Process current across rerender and reload"
                                ),
                                (
                                    "apps/web/src/common-processing-workbench.test.tsx::defers "
                                    "Process "
                                    "reconciliation until Material context resolves without empty "
                                    "workspace patches"
                                ),
                            ],
                        },
                    ],
                    "viewports": VIEWPORTS,
                    "breakpoints": BREAKPOINTS,
                    "targetSelectors": TARGET_SELECTORS,
                    "invalidStateRecords": invalid_state_records,
                    "records": records,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
