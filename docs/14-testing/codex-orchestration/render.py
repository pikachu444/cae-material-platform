from __future__ import annotations

import html
import json
import struct
import tomllib
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parents[2]
SOURCE = ROOT / "workflow-template.html"
HTML_OUTPUT = ROOT / "workflow.html"
OUTPUTS = {
    "ko": {
        "svg": ROOT / "workflow-ko.svg",
        "png": ROOT / "workflow-ko.png",
    },
    "en": {
        "svg": ROOT / "workflow-en.svg",
        "png": ROOT / "workflow-en.png",
    },
}
EXPECTED_FLOW_ROLES = [
    "AUDIT",
    "FIX",
    "HOOK",
    "MAIN",
    "MAIN + AUDIT",
    "OWNER",
    "REVIEW",
    "WRITE",
]
EXPECTED_AGENT_ROLES = ["AUDIT", "FIX", "MAIN", "REVIEW", "WRITE"]


def read_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def configured_labels() -> dict[str, str]:
    config = read_toml(PROJECT_ROOT / ".codex/config.toml")
    agents = {
        "audit": read_toml(PROJECT_ROOT / ".codex/agents/requirements-auditor-sol-high.toml"),
        "write": read_toml(PROJECT_ROOT / ".codex/agents/implementer-luna-max.toml"),
        "fix": read_toml(PROJECT_ROOT / ".codex/agents/correction-luna-max.toml"),
        "review": read_toml(PROJECT_ROOT / ".codex/agents/reviewer-terra-high.toml"),
    }

    def agent_label(agent: dict[str, object]) -> str:
        return (
            f"{agent['model']} · reasoning {agent['model_reasoning_effort']}"
            f" · {agent['sandbox_mode']}"
        )

    concurrency = dict(config["agents"])["max_concurrent_threads_per_session"]
    return {
        "config-main": f"{config['model']} · reasoning {config['model_reasoning_effort']}",
        "config-audit": agent_label(agents["audit"]),
        "config-write": agent_label(agents["write"]),
        "config-fix": agent_label(agents["fix"]),
        "config-review": agent_label(agents["review"]),
        "config-concurrency": f"max_concurrent_threads_per_session = {concurrency}",
    }


def inject_config(page: Page, labels: dict[str, str]) -> None:
    page.evaluate(
        """(values) => {
          for (const [id, value] of Object.entries(values)) {
            const node = document.getElementById(id);
            if (!node) throw new Error(`missing configured label: ${id}`);
            node.textContent = value;
          }
        }""",
        labels,
    )


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"not a PNG: {path}")
    return struct.unpack(">II", data[16:24])


def inspect_source(page: Page) -> dict[str, object]:
    return page.evaluate(
        """() => ({
          width: document.documentElement.scrollWidth,
          height: document.documentElement.scrollHeight,
          title: document.querySelector('h1')?.textContent,
          subtitle: document.querySelector('header p')?.textContent,
          decisions: document.querySelectorAll('.decision').length,
          nodes: document.querySelectorAll('.main-node, .writer-node, .review-node, .hook-node, .correction-node, .terminal').length,
          agentCards: document.querySelectorAll('.agent-card').length,
          flowRoleCount: document.querySelectorAll('[data-flow-role]').length,
          flowRoles: [...new Set(Array.from(document.querySelectorAll('[data-flow-role]')).map((node) => node.dataset.flowRole))].sort(),
          agentRoles: [...new Set(Array.from(document.querySelectorAll('[data-agent-role]')).map((node) => node.dataset.agentRole))].sort(),
          modelTermsInFlowRoles: Array.from(document.querySelectorAll('[data-flow-role]')).filter((node) => /gpt|luna|terra|sol|high|max|xhigh/i.test(node.textContent || '')).length,
          roleStyleMismatches: Array.from(document.querySelectorAll('[data-flow-role]')).filter((node) => {
            const shape = node.previousElementSibling;
            const role = node.dataset.flowRole;
            const expectedClasses = {
              'MAIN': ['main-node', 'main-decision'],
              'AUDIT': ['audit-node'],
              'WRITE': ['writer-node'],
              'FIX': ['correction-node'],
              'REVIEW': ['review-node'],
              'OWNER': ['owner-node'],
              'HOOK': ['hook-node'],
              'MAIN + AUDIT': ['audit-node'],
            }[role] || [];
            return !shape || !expectedClasses.some((className) => shape.classList.contains(className));
          }).length,
          criticalRouteOverlaps: Array.from(document.querySelectorAll('path[data-avoid]')).flatMap((route) => {
            const failures = [];
            const length = route.getTotalLength();
            for (const targetId of route.dataset.avoid.split(' ').filter(Boolean)) {
              const target = document.getElementById(targetId);
              const box = target.getBBox();
              let overlaps = false;
              for (let distance = 1; distance < length; distance += 2) {
                const point = route.getPointAtLength(distance);
                if (point.x > box.x + 2 && point.x < box.x + box.width - 2 && point.y > box.y + 2 && point.y < box.y + box.height - 2) {
                  overlaps = true;
                  break;
                }
              }
              if (overlaps) failures.push(`${route.id}->${targetId}`);
            }
            return failures;
          }),
          agentTextRight: Math.max(...Array.from(document.querySelectorAll('.agent-title, .agent-meta, .agent-desc')).map((node) => {
            const box = node.getBBox();
            return box.x + box.width;
          })),
          outOfCanvasText: Array.from(document.querySelectorAll('svg text')).filter((node) => {
            const box = node.getBBox();
            return box.x < 0 || box.y < 0 || box.x + box.width > 2400 || box.y + box.height > 1500;
          }).length,
          configuredLabels: Object.fromEntries(Array.from(document.querySelectorAll('[id^="config-"]')).map((node) => [node.id, node.textContent])),
        })"""
    )


def validate_source(metrics: dict[str, object], labels: dict[str, str]) -> None:
    if metrics["width"] != 2400 or metrics["height"] != 1600:
        raise RuntimeError(f"unexpected document geometry: {metrics}")
    if metrics["decisions"] != 6 or int(metrics["nodes"]) < 15 or metrics["agentCards"] != 5:
        raise RuntimeError(f"flowchart nodes are incomplete: {metrics}")
    if float(metrics["agentTextRight"]) > 2334 or metrics["outOfCanvasText"] != 0:
        raise RuntimeError(f"flowchart text exceeds its panel: {metrics}")
    if metrics["criticalRouteOverlaps"]:
        raise RuntimeError(f"critical routes overlap unrelated nodes: {metrics}")
    if metrics["configuredLabels"] != labels:
        raise RuntimeError(f"agent configuration labels are stale: {metrics}")
    if (
        metrics["flowRoleCount"] != 18
        or metrics["flowRoles"] != EXPECTED_FLOW_ROLES
        or metrics["agentRoles"] != EXPECTED_AGENT_ROLES
        or metrics["modelTermsInFlowRoles"] != 0
        or metrics["roleStyleMismatches"] != 0
    ):
        raise RuntimeError(f"workflow role labels do not match agent cards: {metrics}")


def export_svg(page: Page, destination: Path, *, title: str, subtitle: str) -> None:
    payload = page.evaluate(
        """() => ({
          styles: Array.from(document.styleSheets).flatMap((sheet) => Array.from(sheet.cssRules)).map((rule) => rule.cssText).join('\\n'),
          flow: document.querySelector('#flow').innerHTML,
        })"""
    )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="2400" height="1600" viewBox="0 0 2400 1600" role="img" aria-labelledby="document-title document-desc" style="display:block;width:2400px;height:1600px">
<style><![CDATA[
{payload['styles']}
.document-title {{ fill: #162536; font-family: "Segoe UI", "Malgun Gothic", "Noto Sans KR", sans-serif; font-size: 30px; font-weight: 650; }}
.document-subtitle {{ fill: #596777; font-family: "Segoe UI", "Malgun Gothic", "Noto Sans KR", sans-serif; font-size: 16px; }}
]]></style>
<title id="document-title">{html.escape(title)}</title>
<desc id="document-desc">{html.escape(subtitle)}</desc>
<rect x="0" y="0" width="2400" height="1600" fill="#f3f5f7" />
<rect x="0" y="0" width="2400" height="100" fill="#ffffff" />
<line x1="0" y1="100" x2="2400" y2="100" stroke="#cbd3dc" />
<text class="document-title" x="42" y="53">{html.escape(title)}</text>
<text class="document-subtitle" x="42" y="79">{html.escape(subtitle)}</text>
<g transform="translate(0 100)">
{payload['flow']}
</g>
</svg>
"""
    destination.write_text(svg, encoding="utf-8", newline="\n")


def export_html(page: Page, destination: Path) -> None:
    markup = page.evaluate("() => document.documentElement.outerHTML")
    destination.write_text(f"<!doctype html>\n{markup}\n", encoding="utf-8", newline="\n")


def main() -> int:
    results: list[dict[str, object]] = []
    labels = configured_labels()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            template_page = browser.new_page(viewport={"width": 2400, "height": 1600})
            try:
                template_page.goto(f"{SOURCE.as_uri()}?lang=ko")
                template_page.wait_for_load_state("networkidle")
                template_page.wait_for_function("document.fonts.status === 'loaded'")
                template_page.locator("#flow").wait_for(state="visible")
                inject_config(template_page, labels)
                validate_source(inspect_source(template_page), labels)
                export_html(template_page, HTML_OUTPUT)
            finally:
                template_page.close()

            for language, outputs in OUTPUTS.items():
                source_page = browser.new_page(viewport={"width": 2400, "height": 1600})
                try:
                    source_page.goto(f"{HTML_OUTPUT.as_uri()}?lang={language}")
                    source_page.wait_for_load_state("networkidle")
                    source_page.wait_for_function("document.fonts.status === 'loaded'")
                    source_page.locator("#flow").wait_for(state="visible")
                    metrics = inspect_source(source_page)
                    validate_source(metrics, labels)
                    export_svg(
                        source_page,
                        outputs["svg"],
                        title=str(metrics["title"]),
                        subtitle=str(metrics["subtitle"]),
                    )
                finally:
                    source_page.close()

                svg_page = browser.new_page(viewport={"width": 2400, "height": 1600})
                try:
                    svg_page.goto(outputs["svg"].as_uri())
                    svg_page.wait_for_load_state("networkidle")
                    svg_page.wait_for_function("document.fonts.status === 'loaded'")
                    svg_metrics = svg_page.evaluate(
                        """() => ({
                          width: document.documentElement.scrollWidth,
                          height: document.documentElement.scrollHeight,
                          viewBox: document.documentElement.getAttribute('viewBox'),
                          flowRoleCount: document.querySelectorAll('[data-flow-role]').length,
                          agentRoleCount: document.querySelectorAll('[data-agent-role]').length,
                        })"""
                    )
                    if svg_metrics != {
                        "width": 2400,
                        "height": 1600,
                        "viewBox": "0 0 2400 1600",
                        "flowRoleCount": 18,
                        "agentRoleCount": 5,
                    }:
                        raise RuntimeError(f"standalone SVG is incomplete: {svg_metrics}")
                    svg_page.screenshot(path=str(outputs["png"]), full_page=False)
                finally:
                    svg_page.close()

                dimensions = png_dimensions(outputs["png"])
                if dimensions != (2400, 1600):
                    raise RuntimeError(f"unexpected PNG dimensions for {outputs['png']}: {dimensions}")
                results.append(
                    {
                        "language": language,
                        "svg": str(outputs["svg"]),
                        "png": str(outputs["png"]),
                        "dimensions": list(dimensions),
                        "png_bytes": outputs["png"].stat().st_size,
                        "svg_bytes": outputs["svg"].stat().st_size,
                        "title": metrics["title"],
                    }
                )
        finally:
            browser.close()
    print(json.dumps({"renders": results}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
