"""Bounded Storybook before-capture for issue #261 M1E2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

STORIES = [
    "foundation-modelingworkspacelayout--default",
    "foundation-modelingworkspacelayout--ribbon-collapsed",
    "foundation-modelingworkspacelayout--export-reclaims-navigator",
    "governed-workflowcomponents--modeling-stage-selected-with-readiness",
    "governed-workflowcomponents--modeling-stage-blocked",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--phase", required=True, choices=("before", "after"))
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page_errors: list[str] = []
        console_errors: list[str] = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on(
            "console",
            lambda message: (
                console_errors.append(message.text) if message.type == "error" else None
            ),
        )

        def capture(story: str, width: int, height: int) -> None:
            page.set_viewport_size({"width": width, "height": height})
            page.goto(
                f"{args.base_url}/iframe.html?id={story}&viewMode=story", wait_until="networkidle"
            )
            page.wait_for_timeout(400)
            page.screenshot(path=str(output / f"{story}-{width}x{height}.png"), full_page=True)
            snapshot = page.evaluate(
                """
                () => {
                  const visible = (element) => {
                    const style = getComputedStyle(element);
                    const rect = element.getBoundingClientRect();
                    return style.display !== 'none'
                      && style.visibility !== 'hidden'
                      && rect.width > 0
                      && rect.height > 0;
                  };
                  const rules = [];
                  const visit = (list, atContext, href) => {
                    for (const rule of Array.from(list || [])) {
                      if (rule.type === CSSRule.STYLE_RULE) {
                        rules.push({
                          selector: rule.selectorText,
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
                    try { visit(sheet.cssRules, [], sheet.href || location.href); } catch (_) {}
                  }
                  const elements = Array.from(document.querySelectorAll(
                    'button,input,select,textarea,[role],h1,h2,h3,summary,[data-testid]',
                  )).filter(visible).slice(0, 180);
                  return {
                    text: document.body.innerText.slice(0, 12000),
                    overflow: {
                      body: getComputedStyle(document.body).overflow,
                      bodyX: getComputedStyle(document.body).overflowX,
                      bodyY: getComputedStyle(document.body).overflowY,
                      scrollWidth: document.documentElement.scrollWidth,
                      clientWidth: document.documentElement.clientWidth,
                      scrollHeight: document.documentElement.scrollHeight,
                      clientHeight: document.documentElement.clientHeight,
                    },
                    elements: elements.map((element) => {
                      const style = getComputedStyle(element);
                      return {
                        tag: element.tagName.toLowerCase(),
                        role: element.getAttribute('role'),
                        text: (
                          element.innerText || element.getAttribute('aria-label') || ''
                        ).slice(0, 240),
                        bounds: element.getBoundingClientRect().toJSON(),
                        computed: {
                          display: style.display,
                          visibility: style.visibility,
                          color: style.color,
                          backgroundColor: style.backgroundColor,
                          fontSize: style.fontSize,
                          gap: style.gap,
                          overflow: style.overflow,
                        },
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
                }
                """,
            )
            records.append(
                {
                    "story": story,
                    "viewport": [width, height],
                    "snapshot": snapshot,
                    "pageErrors": list(page_errors),
                    "consoleErrors": list(console_errors),
                }
            )

        for story in STORIES:
            capture(story, 1440, 900)
            if story.startswith("foundation-modelingworkspacelayout"):
                capture(story, 1181, 900)
                capture(story, 1180, 900)
            if story.startswith("governed-workflowcomponents"):
                capture(story, 901, 768)
                capture(story, 900, 768)
        (output / "storybook-cascade-provenance.json").write_text(
            json.dumps(
                {
                    "baseUrl": args.base_url,
                    "captureMetadata": {
                        "browserZoomPercent": 100,
                        "deviceScaleFactor": 1,
                        "visualViewportScale": 1,
                        "phase": args.phase,
                        "evidenceStatus": f"{args.phase}-relocation Storybook provenance",
                    },
                    "stories": STORIES,
                    "records": records,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        browser.close()


if __name__ == "__main__":
    main()
