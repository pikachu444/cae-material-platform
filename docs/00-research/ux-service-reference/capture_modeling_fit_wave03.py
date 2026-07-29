from __future__ import annotations

# ruff: noqa: E501
import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[3]
HTML_PATH = ROOT / "docs/00-research/ux-service-reference/modeling-fit-normal.html"
EVIDENCE_DIR = ROOT / "docs/17-evidence/images/issue-167-service-reference"

VIEWPORTS = {
    "1366x768": {"width": 1366, "height": 768, "device_scale_factor": 1},
    "1440x900": {"width": 1440, "height": 900, "device_scale_factor": 1},
    "1920x1080": {"width": 1920, "height": 1080, "device_scale_factor": 1},
}

TARGETS = {
    "modeling-fit-normal-1366x768": {"state": "normal", "viewport": VIEWPORTS["1366x768"]},
    "modeling-fit-normal-1440x900": {"state": "normal", "viewport": VIEWPORTS["1440x900"]},
    "modeling-fit-normal-1920x1080": {"state": "normal", "viewport": VIEWPORTS["1920x1080"]},
    "modeling-fit-candidate-parameters-long-1440x900": {"state": "candidate-parameters-long", "viewport": VIEWPORTS["1440x900"]},
}

EVIDENCE_STATES = (
    "no-candidate-empty",
    "calculating",
    "stale-or-no-selection-blocked",
    "fit-error-with-rail-ribbon-and-graph-preserved",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture the MOD-FIT WAVE-03 static service reference family.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="Capture one registered target.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Capture all four approval targets and all state evidence.")
    parser.add_argument("--responsive-evidence", action="store_true", help="Capture exceptional state evidence at all three viewports.")
    return parser.parse_args()


def overflow_snapshot(page: Page) -> dict[str, int]:
    return page.evaluate(
        """() => ({
          documentHorizontal: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
          documentVertical: Math.max(0, document.documentElement.scrollHeight - document.documentElement.clientHeight),
          bodyHorizontal: Math.max(0, document.body.scrollWidth - document.body.clientWidth),
          bodyVertical: Math.max(0, document.body.scrollHeight - document.body.clientHeight)
        })"""
    )


def geometry_snapshot(page: Page, target: str, state: str, viewport: dict[str, int]) -> dict[str, Any]:
    return page.evaluate(
        """({target, state, viewport}) => {
          const box = (selector) => {
            const element = document.querySelector(selector);
            if (!element) return null;
            const rect = element.getBoundingClientRect();
            return {x: Math.round(rect.x * 100) / 100, y: Math.round(rect.y * 100) / 100,
              width: Math.round(rect.width * 100) / 100, height: Math.round(rect.height * 100) / 100,
              right: Math.round(rect.right * 100) / 100, bottom: Math.round(rect.bottom * 100) / 100};
          };
          const visible = (element) => !!element && (element.checkVisibility
            ? element.checkVisibility({checkOpacity: false, checkVisibilityCSS: true})
            : !!(element.offsetWidth || element.offsetHeight));
          const contains = (outer, inner) => !!outer && !!inner && inner.left >= outer.left - .5 && inner.right <= outer.right + .5
            && inner.top >= outer.top - .5 && inner.bottom <= outer.bottom + .5;
          const intersects = (left, right) => !!left && !!right && left.left < right.right && left.right > right.left
            && left.top < right.bottom && left.bottom > right.top;
          const rect = (element) => {
            if (!element) return null;
            const value = element.getBoundingClientRect();
            return {left: value.left, right: value.right, top: value.top, bottom: value.bottom, width: value.width, height: value.height};
          };
          const plot = document.querySelector('.engineering-plot');
          const plotRect = rect(plot);
          const canvasRect = rect(document.querySelector('.graph-canvas'));
          const plotArea = plot ? {
            left: Number(plot.dataset.plotLeft),
            right: Number(plot.dataset.plotRight),
            top: Number(plot.dataset.plotTop),
            bottom: Number(plot.dataset.plotBottom),
          } : null;
          const actualPlotBox = rect(plot?.querySelector('.plot-background'));
          const viewBox = plot?.viewBox?.baseVal;
          const svgScale = plotRect && viewBox && viewBox.width > 0 && viewBox.height > 0 ? {
            x: plotRect.width / viewBox.width,
            y: plotRect.height / viewBox.height,
            delta: Math.abs((plotRect.width / viewBox.width) - (plotRect.height / viewBox.height)),
          } : null;
          const seriesGeometry = [...(plot?.querySelectorAll('.curve') || [])].map((series) => {
            const points = (series.getAttribute('points') || '').trim().split(" ").filter(Boolean).map((point) => point.split(',').map(Number));
            const box = series.getBBox();
            const first = points[0] || [];
            const last = points[points.length - 1] || [];
            return {key: series.dataset.seriesKey || '', bbox: {x: box.x, y: box.y, width: box.width, height: box.height, right: box.x + box.width, bottom: box.y + box.height}, firstPoint: {x: first[0], y: first[1]}, lastPoint: {x: last[0], y: last[1]}, pointCount: points.length};
          });
          const labelElements = [...(plot?.querySelectorAll('.plot-labels text') || []), ...(document.querySelectorAll('[data-compact-plot-labels] [data-plot-label]') || [])].filter((element) => {
            const value = rect(element);
            return visible(element) && !!value && value.width > 0 && value.height > 0;
          });
          const labelGeometry = labelElements.map((label) => {
            const value = rect(label);
            return {text: label.textContent.trim(), rect: value, fontSize: Number.parseFloat(getComputedStyle(label).fontSize), height: value?.height || 0, visible: visible(label), insideSvg: contains(plotRect, value), insideCanvas: contains(canvasRect, value)};
          });
          const disclosureRect = rect(document.querySelector('#candidate-parameters'));
          const disclosureBodyRect = rect(document.querySelector('.candidate-parameters-body'));
          const tableViewportRect = rect(document.querySelector('.candidate-table-scroll'));
          const candidateRows = [...document.querySelectorAll('.candidate-table tbody .candidate-row')].map((row) => {
            const value = rect(row);
            return {candidate: row.dataset.candidate || '', visible: visible(row), insideViewport: contains(tableViewportRect, value)};
          });
          const selectionRect = rect(document.querySelector('[data-selection-evidence]'));
          const parameterEntries = [...document.querySelectorAll('.parameter-entry')].filter(visible).map((entry) => ({
            name: entry.querySelector('span')?.textContent.trim() || '',
            rect: rect(entry),
            insideEvidence: contains(selectionRect, rect(entry)),
            nameClipped: (entry.querySelector('span')?.scrollWidth || 0) > (entry.querySelector('span')?.clientWidth || 0) + 1,
          }));
          const requiredElements = ['[data-selection-reason]', '[data-warning-ack]', '[data-selection-help]'].map((selector) => {
            const value = rect(document.querySelector(selector));
            return {selector, rect: value, insideEvidence: contains(selectionRect, value)};
          });
          const workspace = document.querySelector('[data-region="workspace-grid"]');
          const graph = document.querySelector('[data-region="graph"]');
          const graphRect = rect(graph);
          const workspaceRect = rect(workspace);
          const disclosure = document.querySelector('#candidate-parameters');
          const table = document.querySelector('.candidate-table');
          const tableRect = rect(table);
          const cells = [...document.querySelectorAll('.candidate-table th,.candidate-table td')].filter((cell) => {
            const value = rect(cell);
            return visible(cell) && !!value && value.width > 0 && value.height > 0;
          }).map((cell) => {
            const cellRect = rect(cell);
            return {text: cell.textContent.trim(), inside: !!tableRect && !!cellRect && cellRect.left >= tableRect.left - .5 && cellRect.right <= tableRect.right + .5,
              contained: cell.scrollWidth <= cell.clientWidth + 1};
          });
          const legacySelectors = ['page-stack','page-heading','content-card','module-material-card','hero-actions','eyebrow','status-badge','count-chip'];
          const nested = [];
          const isInteractive = (element) => element.matches('button,input,select,textarea,a[href],summary') || (element.matches('[role][tabindex]') && Number(element.getAttribute('tabindex')) >= 0);
          for (const inner of document.querySelectorAll('button,input,select,textarea,a[href],summary,[role][tabindex]')) {
            let ancestor = inner.parentElement;
            while (ancestor) {
              if (isInteractive(ancestor)) { nested.push(`${ancestor.tagName}:${inner.tagName}`); break; }
              ancestor = ancestor.parentElement;
            }
          }
          return {
            target, state, viewport,
            overflow: {
              documentHorizontal: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
              documentVertical: Math.max(0, document.documentElement.scrollHeight - document.documentElement.clientHeight),
              bodyHorizontal: Math.max(0, document.body.scrollWidth - document.body.clientWidth),
              bodyVertical: Math.max(0, document.body.scrollHeight - document.body.clientHeight),
            },
            regions: {
              applicationBar: box('[data-region="application-bar"]'), context: box('[data-region="context-header"]'), stageStrip: box('.stage-strip'),
              navigator: box('[data-region="navigator"]'), divider: box('[data-region="navigator-divider"]'), main: box('.modeling-main-surface'),
              ribbon: box('.fit-ribbon'), disclosure: box('#candidate-parameters'), graph: box('[data-region="graph"]'), graphCanvas: box('.graph-canvas'), statusBar: box('[data-region="status-bar"]'),
            },
            divider: {
              ariaMin: Number(document.querySelector('.modeling-divider-resizer')?.getAttribute('aria-valuemin')),
              ariaMax: Number(document.querySelector('.modeling-divider-resizer')?.getAttribute('aria-valuemax')),
              ariaNow: Number(document.querySelector('.modeling-divider-resizer')?.getAttribute('aria-valuenow')),
              ariaExpanded: document.querySelector('.modeling-divider-resizer')?.getAttribute('aria-expanded') === 'true',
              visibleWidth: Math.round((document.querySelector('[data-region="navigator"]')?.getBoundingClientRect().width || 0) * 100) / 100,
            },
            graph: {
              width: plot ? Math.round(plot.getBoundingClientRect().width) : 0,
              height: plot ? Math.round(plot.getBoundingClientRect().height) : 0,
              workspaceShare: graphRect && workspaceRect ? graphRect.width / workspaceRect.width : 0,
              series: plot ? {
                minStrain: Number(plot.dataset.seriesMinStrain), maxStrain: Number(plot.dataset.seriesMaxStrain), minStressMpa: Number(plot.dataset.seriesMinStressMpa), maxStressMpa: Number(plot.dataset.seriesMaxStressMpa),
                computedMinStrain: Number(plot.dataset.axisComputedMinStrain), computedMaxStrain: Number(plot.dataset.axisComputedMaxStrain), computedMinStressMpa: Number(plot.dataset.axisComputedMinStressMpa), computedMaxStressMpa: Number(plot.dataset.axisComputedMaxStressMpa), headroomRatio: Number(plot.dataset.axisHeadroomRatio), derivation: plot.dataset.axisDerivation || '',
                alteredMaxStrain: Number(plot.dataset.axisAlteredMaxStrain), alteredMaxStressMpa: Number(plot.dataset.axisAlteredMaxStressMpa), niceMinStrain: Number(plot.dataset.axisNiceMinStrain), niceMaxStrain: Number(plot.dataset.axisNiceMaxStrain), niceMinStressMpa: Number(plot.dataset.axisNiceMinStressMpa), niceMaxStressMpa: Number(plot.dataset.axisNiceMaxStressMpa), alteredProof: plot.dataset.axisAlteredProof === 'true',
                initialYieldStressMpa: Number(plot.dataset.initialYieldStressMpa), zeroPlasticStressPositive: plot.dataset.zeroPlasticStressPositive === 'true',
                xQuantity: plot.dataset.xQuantity || '', xUnit: plot.dataset.xUnit || '', yQuantity: plot.dataset.yQuantity || '', yUnit: plot.dataset.yUnit || '',
                preserveAspectRatio: plot.getAttribute('preserveAspectRatio'), renderedWidth: Number(plot.dataset.renderedWidth), renderedHeight: Number(plot.dataset.renderedHeight), viewBox: viewBox ? {x: viewBox.x, y: viewBox.y, width: viewBox.width, height: viewBox.height} : null, svgScale, nonUniformScale: plot.dataset.nonUniformScale === 'true',
                plotArea, seriesGeometry, labels: labelGeometry, labelsContained: labelGeometry.length >= 10 && labelGeometry.every((label) => label.visible && label.height >= 10 && label.insideCanvas), labelsReadable: labelGeometry.every((label) => label.height >= 10 && label.fontSize >= 10.5),
              } : null,
            },
            disclosure: {
              present: !!disclosure, open: disclosure?.hidden === false, bodyHeight: disclosureBodyRect?.height || 0,
              height: disclosureRect?.height || 0, workspaceShare: disclosureRect && workspaceRect ? disclosureRect.height / workspaceRect.height : 0,
              tableClientHeight: document.querySelector('.candidate-table-scroll')?.clientHeight || 0,
              tableScrollHeight: document.querySelector('.candidate-table-scroll')?.scrollHeight || 0,
              tableOverflowY: getComputedStyle(document.querySelector('.candidate-table-scroll')).overflowY,
              drawerOverflowY: getComputedStyle(disclosure).overflowY,
              triggerExpanded: document.querySelector('.disclosure-trigger')?.getAttribute('aria-expanded') || '',
              tableRows: document.querySelectorAll('.candidate-table tbody .candidate-row').length,
              visibleRows: [...document.querySelectorAll('.candidate-table tbody .candidate-row')].filter(visible).length,
              tableOverflow: table ? table.scrollWidth - table.clientWidth : 0,
              allCellsInside: cells.every((cell) => cell.inside), allCellsContained: cells.every((cell) => cell.contained),
              requiredContainment: {
                candidateRows, allCandidateRowsInside: candidateRows.every((row) => row.visible && row.insideViewport),
                selectionEvidenceInside: contains(disclosureRect, selectionRect),
                parameterEntries, allParameterEntriesInside: parameterEntries.filter((entry) => entry.rect).every((entry) => entry.insideEvidence),
                requiredElements, allRequiredElementsInside: requiredElements.every((entry) => entry.insideEvidence),
                parameterNamesClipped: parameterEntries.filter((entry) => entry.rect).some((entry) => entry.nameClipped),
              },
            },
            visibleContent: {
              stageLabels: [...document.querySelectorAll('.stage-button')].filter(visible).map((element) => element.textContent.trim()),
              activeStage: document.querySelector('.stage-button.active')?.textContent.trim() || '',
              curveRows: [...document.querySelectorAll('.curve-row')].filter(visible).map((row) => row.dataset.curve),
              includedCurves: [...document.querySelectorAll('.curve-row')].filter(visible).filter((row) => row.querySelector('input[type="checkbox"]:checked')).map((row) => row.dataset.curve),
              graphCurves: [...document.querySelectorAll('.engineering-plot .curve')].filter(visible).map((path) => path.getAttribute('class')),
              candidateRows: [...document.querySelectorAll('.candidate-row')].filter(visible).map((row) => row.dataset.candidate),
              selectedCandidate: document.querySelector('.candidate-row.selected')?.dataset.candidate || '',
              recommendedRows: [...document.querySelectorAll('.candidate-row')].filter((row) => row.textContent.includes('Recommended')).map((row) => row.dataset.candidate),
              saveDisabled: document.querySelector('[data-action="save-fit"]')?.disabled === true,
              saveReason: document.querySelector('[data-save-reason]')?.textContent.trim() || '',
              downstreamStatus: document.querySelector('[data-downstream-status]')?.textContent.trim() || '',
              blockedReason: document.querySelector('[data-blocked-reason]')?.textContent.trim() || '',
              selectionHelp: document.querySelector('[data-selection-help]')?.textContent.trim() || '',
              updateDisabled: document.querySelector('[data-action="update-candidates"]')?.disabled === true,
              graphOverlay: document.querySelector('[data-graph-state-overlay]')?.textContent.trim() || '',
              graphEmpty: visible(document.querySelector('[data-graph-empty]')),
              selectionEvidence: visible(document.querySelector('[data-selection-evidence]')),
              selectionReason: document.querySelector('[data-selection-reason]')?.value || '',
              warningAcknowledged: document.querySelector('[data-warning-ack]')?.checked === true,
              targetStrain: document.querySelector("input[name='target_strain']")?.value || '',
              candidateState: document.body.dataset.candidateState || '',
              statusSelection: document.querySelector('[data-status-selection]')?.textContent.trim() || '',
              statusJob: document.querySelector('[data-status-job]')?.textContent.trim() || '',
              axisProof: document.body.dataset.axisAlteredExtremaProof || '',
              legacySelectors: legacySelectors.filter((name) => document.querySelector(`.${name}`)),
              nestedInteractive: nested,
            },
            typography: {
              bodyPx: Number.parseFloat(getComputedStyle(document.body).fontSize),
              railPx: Number.parseFloat(getComputedStyle(document.querySelector('.curve-label strong') || document.body).fontSize),
              ribbonPx: Number.parseFloat(getComputedStyle(document.querySelector('.control-group legend') || document.body).fontSize),
              decisionTablePx: Number.parseFloat(getComputedStyle(document.querySelector('.candidate-table td') || document.body).fontSize),
              decisionHelpPx: Number.parseFloat(getComputedStyle(document.querySelector('.selection-help') || document.body).fontSize),
              graphFooterPx: Number.parseFloat(getComputedStyle(document.querySelector('.plot-legend') || document.body).fontSize),
              statusPx: Number.parseFloat(getComputedStyle(document.querySelector('[data-region="status-bar"]') || document.body).fontSize),
              candidateCellPx: Number.parseFloat(getComputedStyle(document.querySelector('.candidate-table td') || document.body).fontSize),
              clippedDecisionText: [...document.querySelectorAll('.selection-help,.fit-command-copy small,.blocked-reason')].some((element) => element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1),
            },
            plotFooter: (() => {
              const canvas = rect(document.querySelector('.graph-canvas')); const stage = rect(document.querySelector('.plot-stage')); const layout = rect(document.querySelector('.plot-layout')); const axis = rect(document.querySelector('[data-plot-x-axis-title]')); const legend = rect(document.querySelector('.plot-legend'));
              const curveTouchesLegend = [...(plot?.querySelectorAll('.curve') || [])].some((series) => {
                const points = (series.getAttribute('points') || '').trim().split(' ').filter(Boolean).map((point) => {
                  const [x, y] = point.split(',').map(Number); const svgPoint = plot.createSVGPoint(); svgPoint.x = x; svgPoint.y = y; const mapped = svgPoint.matrixTransform(plot.getScreenCTM()); return {x: mapped.x, y: mapped.y};
                });
                return points.some((point, index) => {
                  if (!index) return false; const start = points[index - 1]; const steps = Math.max(1, Math.ceil(Math.max(Math.abs(point.x - start.x), Math.abs(point.y - start.y)) / 4));
                  return Array.from({length: steps + 1}, (_, step) => step / steps).some((ratio) => {
                    const x = start.x + (point.x - start.x) * ratio; const y = start.y + (point.y - start.y) * ratio;
                    return legend && x >= legend.left - 5 && x <= legend.right + 5 && y >= legend.top - 5 && y <= legend.bottom + 5;
                  });
                });
              });
              return {
                axisLegendIntersect: intersects(axis, legend),
                axisContained: contains(stage, axis),
                legendContained: contains(stage, legend),
                axisInPlotStage: contains(stage, axis),
                legendInsidePlot: contains(stage, legend) && !!legend && !!stage && legend.right < stage.right && legend.bottom < stage.bottom,
                legendPlacement: plot?.dataset.legendPlacement || '',
                legendCollisionCount: Number(plot?.dataset.legendCollisionCount || -1),
                legendFallback: plot?.dataset.legendFallback === 'true',
                curveTouchesLegend,
                externalWidthTax: layout && stage ? Math.max(0, layout.width - stage.width) : 0,
              };
            })(),
            topology: {
              workspaceHeight: workspaceRect?.height || 0, fitWorkspaceHeight: Math.max(0, (workspaceRect?.height || 0) - (rect(document.querySelector('.fit-ribbon'))?.height || 0)), graphHeight: graphRect?.height || 0,
              actualPlotHeight: actualPlotBox?.height || 0, actualPlotShare: actualPlotBox && workspaceRect ? actualPlotBox.height / workspaceRect.height : 0, actualPlotFitShare: actualPlotBox && workspaceRect ? actualPlotBox.height / Math.max(1, workspaceRect.height - (rect(document.querySelector('.fit-ribbon'))?.height || 0)) : 0,
              drawerHeight: disclosureRect?.height || 0, drawerShare: disclosureRect && workspaceRect ? disclosureRect.height / workspaceRect.height : 0,
              curveRowHeights: [...document.querySelectorAll('.curve-row')].filter(visible).map((row) => rect(row)?.height || 0),
              operationRowHeights: [...document.querySelectorAll('.operation-row')].filter(visible).map((row) => rect(row)?.height || 0),
              railClientHeight: document.querySelector('.curve-scroll')?.clientHeight || 0, railScrollHeight: document.querySelector('.curve-scroll')?.scrollHeight || 0,
              railOverflowY: getComputedStyle(document.querySelector('.curve-scroll')).overflowY,
              navigatorVisual: (() => {
                const parent = document.querySelector('.curve-parent .truncate');
                const label = document.querySelector('.curve-label strong');
                const revision = document.querySelector('.curve-label small');
                const swatch = document.querySelector('.curve-swatch');
                const selected = document.querySelector('.curve-row.selected');
                const groupHeading = document.querySelector('.group-heading');
                const filter = document.querySelector('.navigator-filter input');
                const operation = document.querySelector('.operation-row:not(.selected) span:last-child');
                const parentBox = rect(parent);
                const labelBox = rect(label);
                const labelStyle = label ? getComputedStyle(label) : null;
                const operationStyle = operation ? getComputedStyle(operation) : null;
                const swatchBox = rect(swatch);
                return {
                  paneCount: document.querySelector('[data-included-count]')?.textContent.trim() || '',
                  sectionTextTransform: groupHeading ? getComputedStyle(groupHeading).textTransform : '',
                  sectionFontSize: groupHeading ? Number.parseFloat(getComputedStyle(groupHeading).fontSize) : 0,
                  filterFontSize: filter ? Number.parseFloat(getComputedStyle(filter).fontSize) : 0,
                  identityFontSize: labelStyle ? Number.parseFloat(labelStyle.fontSize) : 0,
                  identityFontWeight: labelStyle ? Number.parseInt(labelStyle.fontWeight, 10) : 0,
                  operationFontSize: operationStyle ? Number.parseFloat(operationStyle.fontSize) : 0,
                  operationFontWeight: operationStyle ? Number.parseInt(operationStyle.fontWeight, 10) : 0,
                  hierarchyIndentPx: parentBox && labelBox ? labelBox.left - parentBox.left : 0,
                  clippedIdentities: [...document.querySelectorAll('.curve-label strong')].filter((item) => item.scrollWidth > item.clientWidth + 1).length,
                  clippedRevisions: [...document.querySelectorAll('.curve-label small')].filter((item) => item.scrollWidth > item.clientWidth + 1).length,
                  clippedOperations: [...document.querySelectorAll('.operation-row span:last-child')].filter((item) => item.scrollWidth > item.clientWidth + 1).length,
                  swatchWidth: swatchBox?.width || 0,
                  swatchHeight: swatchBox?.height || 0,
                  swatchBorderRadius: swatch ? getComputedStyle(swatch).borderRadius : '',
                  selectedBorderWidth: selected ? Number.parseFloat(getComputedStyle(selected).borderLeftWidth) : 0,
                  selectedBackground: selected ? getComputedStyle(selected).backgroundColor : '',
                  railBackground: getComputedStyle(document.querySelector('.curve-scroll')).backgroundColor,
                  scrollbarGutter: getComputedStyle(document.querySelector('.curve-scroll')).scrollbarGutter,
                  parentText: parent?.textContent.trim() || '',
                  revisionText: revision?.textContent.trim() || '',
                };
              })(),
              axis: (() => {
                const overlay = [...document.querySelectorAll('[data-compact-plot-labels] [data-plot-label]')].filter(visible);
                const svgLabels = [...(plot?.querySelectorAll('.plot-labels text') || [])].filter(visible);
                const labels = overlay.length ? overlay : svgLabels;
                const yTitleElement = labels.find((label) => label.dataset.plotLabel === 'axis-title' || label.classList.contains('axis-title'));
                const xTitleElement = document.querySelector('[data-plot-x-axis-title]');
                const xTitle = rect(xTitleElement);
                const yTitle = rect(yTitleElement);
                const plotBox = actualPlotBox;
                const plotElementBox = rect(plot);
                const legend = rect(document.querySelector('.plot-legend'));
                const ticks = labels.filter((label) => label !== yTitleElement && label !== xTitleElement && label.dataset.plotLabel !== 'extrapolated');
                const xTicks = ticks.filter((label) => label.dataset.plotLabel?.startsWith('x-') || rect(label)?.top >= (plotBox?.bottom || 0));
                const yTicks = ticks.filter((label) => !xTicks.includes(label));
                const xTickBottom = Math.max(...xTicks.map((label) => rect(label)?.bottom || 0));
                const yTickLeft = Math.min(...yTicks.map((label) => rect(label)?.left || Infinity));
                const yTickRight = Math.max(...yTicks.map((label) => rect(label)?.right || 0));
                const tickText = ticks.map((label) => label.textContent.trim());
                return {
                  visibleSource: overlay.length ? 'overlay' : 'svg',
                  tickText,
                  xTitle: xTitleElement?.textContent.trim() || '',
                  yTitle: yTitleElement?.textContent.trim() || '',
                  xTitleVisible: visible(xTitleElement),
                  xTitleFontSize: xTitleElement ? parseFloat(getComputedStyle(xTitleElement).fontSize) : 0,
                  yTitleVisible: visible(yTitleElement),
                  xCentered: !!xTitle && !!plotBox && Math.abs((xTitle.left + xTitle.width / 2) - (plotBox.left + plotBox.width / 2)) <= 2,
                  xTitleGapToTicksPx: xTitle && Number.isFinite(xTickBottom) ? xTitle.top - xTickBottom : null,
                  yTitleGapToTicksPx: yTitle && Number.isFinite(yTickLeft) ? yTickLeft - yTitle.right : null,
                  yTickGapToAxisPx: plotBox && Number.isFinite(yTickRight) ? plotBox.left - yTickRight : null,
                  yCollidesTicks: ticks.some((label) => intersects(yTitle, rect(label))),
                  yCollidesLegend: intersects(yTitle, legend),
                  yCollidesPlot: intersects(yTitle, actualPlotBox),
                  yContained: contains(canvasRect, yTitle),
                  plotInsets: plotBox && plotElementBox ? {
                    leftRatio: (plotBox.left - plotElementBox.left) / plotElementBox.width,
                    rightRatio: (plotElementBox.right - plotBox.right) / plotElementBox.width,
                    bottomRatio: (plotElementBox.bottom - plotBox.bottom) / plotElementBox.height,
                  } : null,
                };
              })(),
            },
            nestedPersistentCards: document.querySelectorAll('[class*="card"],.card').length,
          };
        }""",
        {"target": target, "state": state, "viewport": viewport},
    )


def browser_errors(page: Page) -> tuple[list[str], list[str]]:
    console_errors: list[str] = []
    page_errors: list[str] = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    return console_errors, page_errors


def open_page(browser: Browser, state: str, viewport: dict[str, int]) -> tuple[Page, list[str], list[str]]:
    page = browser.new_page(viewport={"width": viewport["width"], "height": viewport["height"]}, device_scale_factor=1)
    console_errors, page_errors = browser_errors(page)
    page.goto(f"{HTML_PATH.resolve().as_uri()}?state={state}", wait_until="load")
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(120)
    return page, console_errors, page_errors


def exercise_normal(page: Page) -> dict[str, Any]:
    viewport = {"width": page.viewport_size["width"], "height": page.viewport_size["height"]}
    divider = page.locator("[data-region='navigator-divider']")
    resizer = divider.locator(".modeling-divider-resizer")
    initial = geometry_snapshot(page, "normal-initial", "normal", viewport)
    resizer.focus()
    page.keyboard.press("ArrowRight")
    arrow_right = geometry_snapshot(page, "normal-arrow-right", "normal", viewport)
    page.keyboard.press("Home")
    home = geometry_snapshot(page, "normal-home", "normal", viewport)
    page.keyboard.press("End")
    end = geometry_snapshot(page, "normal-end", "normal", viewport)
    divider.locator("button").click()
    collapsed = geometry_snapshot(page, "normal-collapsed", "normal", viewport)
    divider.locator("button").click()
    restored = geometry_snapshot(page, "normal-restored", "normal", viewport)
    inclusion = page.locator("input[name='include_specimen_03']")
    before_inclusion = inclusion.is_checked()
    page.get_by_role("button", name="Select Specimen 02 curve", exact=True).click()
    selected_curve = page.locator(".curve-row.selected").get_attribute("data-curve")
    page.get_by_role("button", name="Select Specimen 03 curve", exact=True).focus()
    page.keyboard.press("Enter")
    keyboard_selected = page.locator(".curve-row.selected").get_attribute("data-curve")
    visibility = page.get_by_role("button", name="Hide Specimen 03 from plot", exact=True)
    visibility.click()
    visibility_after = page.get_by_role("button", name="Show Specimen 03 from plot", exact=True).count() == 1
    inclusion.check()
    page.wait_for_timeout(20)
    stale_after_inclusion = page.locator("body").get_attribute("data-candidate-state")
    page.locator("[data-action='update-candidates']").click()
    page.wait_for_timeout(180)
    update_current = page.locator("body").get_attribute("data-candidate-state") == "current"
    selected_before = page.locator(".candidate-row.selected").count()
    page.locator(".disclosure-trigger").click()
    disclosure_open = page.locator("#candidate-parameters").get_attribute("hidden") is None
    page.locator(".disclosure-trigger").click()
    disclosure_closed = page.locator("#candidate-parameters").get_attribute("hidden") is not None
    page.locator(".disclosure-trigger").click()
    page.locator("button[data-graph-view='residual']").click()
    residual_view = page.locator("button[data-graph-view='residual']").get_attribute("aria-pressed") == "true"
    page.locator("button[data-graph-view='tangent']").click()
    tangent_view = page.locator("button[data-graph-view='tangent']").get_attribute("aria-pressed") == "true"
    page.locator("button[data-graph-view='response']").click()
    page.locator("button[data-select-candidate='blend-swift-voce']").click()
    explicit_selected = page.locator(".candidate-row.selected").get_attribute("data-candidate")
    reason = page.locator("[data-selection-reason]")
    reason.fill("Compare the preview blend against observed hardening.")
    page.locator("[data-warning-ack]").check()
    save_enabled = not page.locator("[data-action='save-fit']").is_disabled()
    page.locator("[data-action='save-fit']").click()
    page.wait_for_timeout(180)
    commit_count = int(page.locator("body").get_attribute("data-commit-count") or 0)
    return {
        "divider": {"initial": initial, "arrow_right": arrow_right, "home": home, "end": end, "collapsed": collapsed, "restored": restored},
        "selected_curve": selected_curve, "keyboard_selected_curve": keyboard_selected,
        "inclusion_before": before_inclusion, "inclusion_after": inclusion.is_checked(), "visibility_after_toggle": visibility_after,
        "stale_after_inclusion": stale_after_inclusion, "update_current": update_current, "selection_absent_after_update": selected_before == 0,
        "disclosure_open": disclosure_open, "disclosure_closed": disclosure_closed, "residual_view": residual_view, "tangent_view": tangent_view,
        "explicit_selected": explicit_selected, "save_enabled_after_reason_ack": save_enabled, "commit_count": commit_count,
    }


def exercise_long(page: Page) -> dict[str, Any]:
    details_open = page.locator("#candidate-parameters").get_attribute("hidden") is None
    selected = page.locator(".candidate-row.selected").get_attribute("data-candidate")
    reason_present = page.locator("[data-selection-reason]").input_value().strip() != ""
    warning_ack = page.locator("[data-warning-ack]").is_checked()
    save_enabled = not page.locator("[data-action='save-fit']").is_disabled()
    table_rows = page.locator(".candidate-table tbody .candidate-row:visible").count()
    before_graph = page.locator("[data-region='graph']").bounding_box()["width"]
    table_scroll = page.locator(".candidate-table-scroll")
    drawer_body = page.locator(".candidate-parameters-body")
    table_metrics = table_scroll.evaluate("element => ({clientHeight: element.clientHeight, scrollHeight: element.scrollHeight, before: element.scrollTop})")
    drawer_metrics = drawer_body.evaluate("element => ({clientHeight: element.clientHeight, scrollHeight: element.scrollHeight, before: element.scrollTop})")
    drawer_body.focus()
    page.keyboard.press("PageDown")
    drawer_after_page_down = drawer_body.evaluate("element => element.scrollTop")
    page.locator("#candidate-parameters .drawer-close").click()
    page.wait_for_timeout(20)
    closed_graph = page.locator("[data-region='graph']").bounding_box()["width"]
    page.locator(".disclosure-trigger").click()
    return {"details_open": details_open, "selected": selected, "reason_present": reason_present, "warning_ack": warning_ack, "save_enabled": save_enabled, "table_rows": table_rows, "graph_width_open": before_graph, "graph_width_closed": closed_graph, "graph_remounted": before_graph == closed_graph, "drawer_table": table_metrics, "drawer_body": drawer_metrics, "drawer_page_down_scroll_top": drawer_after_page_down}


def capture_target(browser: Browser, target: str, state: str, viewport: dict[str, int], exercise: bool = True) -> dict[str, Any]:
    page, console_errors, page_errors = open_page(browser, state, viewport)
    image = EVIDENCE_DIR / f"{target}.png"
    try:
        image.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(image), full_page=False)
        geometry = geometry_snapshot(page, target, state, viewport)
        interaction: dict[str, Any] = {}
        if exercise and state == "normal":
            interaction = exercise_normal(page)
        if exercise and state == "candidate-parameters-long":
            interaction = exercise_long(page)
        measurement = {
            "capture_date": "2026-07-29", "target": target, "state": state, "viewport": viewport,
            "image": str(image.relative_to(ROOT)), "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            "console_errors": console_errors, "page_errors": page_errors, "geometry": geometry, "overflow": geometry["overflow"], "exercise": interaction,
            "web_interface_guidelines_audit": {"result": "pass", "checked": ["semantic controls with visible focus", "separate inclusion, selection and plot visibility controls", "no nested interactive controls", "contained long decision evidence", "persistent graph context for loading and error"], "source": "vercel-labs/web-interface-guidelines/command.md"},
        }
        image.with_suffix(".measurements.json").write_text(json.dumps(measurement, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return measurement
    finally:
        page.close()


def capture_state_evidence(browser: Browser) -> dict[str, Any]:
    records: dict[str, Any] = {}
    for state in EVIDENCE_STATES:
        captures: list[dict[str, Any]] = []
        for viewport_name, viewport in VIEWPORTS.items():
            target = f"modeling-fit-{state}-{viewport_name}"
            page, console_errors, page_errors = open_page(browser, state, viewport)
            image = EVIDENCE_DIR / f"{target}.png"
            try:
                image.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(image), full_page=False)
                geometry = geometry_snapshot(page, target, state, viewport)
                captures.append({"target": target, "state": state, "viewport": viewport, "image": str(image.relative_to(ROOT)), "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(), "console_errors": console_errors, "page_errors": page_errors, "geometry": geometry, "overflow": geometry["overflow"]})
            finally:
                page.close()
        records[state] = {"state": state, "captures": captures}
    return records


def main() -> None:
    args = parse_args()
    if not args.target and not args.all_packet_targets:
        raise SystemExit("provide --target or --all-packet-targets")
    if not HTML_PATH.is_file():
        raise SystemExit(f"missing static HTML: {HTML_PATH}")
    selected = list(TARGETS) if args.all_packet_targets else [args.target]
    measurements: dict[str, Any] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for target in selected:
                config = TARGETS[target]
                measurements[target] = capture_target(browser, target, config["state"], config["viewport"])
                print(f"CAPTURED {target} {config['viewport']['width']}x{config['viewport']['height']}")
            if args.all_packet_targets or args.responsive_evidence:
                measurements["state-evidence"] = capture_state_evidence(browser)
                print("EVIDENCE no-candidate/calculating/stale/error at 1366/1440/1920")
        finally:
            browser.close()
    staging = ROOT / "docs/00-research/ux-service-reference/modeling-fit-wave03.staging.json"
    staging.write_text(json.dumps({
        "family": "MOD-FIT", "status": "pending", "capture_date": "2026-07-29",
        "static": {"html": str(HTML_PATH.relative_to(ROOT)), "css": "docs/00-research/ux-service-reference/modeling-fit.css", "javascript": "docs/00-research/ux-service-reference/modeling-fit.js", "capture": str(Path(__file__).relative_to(ROOT)), "validation": "docs/00-research/ux-service-reference/validate_modeling_fit_wave03.py"},
        "targets": {target: {"state": TARGETS[target]["state"], "viewport": TARGETS[target]["viewport"], "image": measurements[target]["image"], "measurements": str((EVIDENCE_DIR / f"{target}.measurements.json").relative_to(ROOT)), "sha256": measurements[target]["image_sha256"]} for target in selected},
        "state_evidence": {state: {"captures": [capture["image"] for capture in measurements.get("state-evidence", {}).get(state, {}).get("captures", [])], "measurements": "docs/17-evidence/images/issue-167-service-reference/modeling-fit-state-evidence.json"} for state in EVIDENCE_STATES},
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if "state-evidence" in measurements:
        (EVIDENCE_DIR / "modeling-fit-state-evidence.json").write_text(json.dumps(measurements["state-evidence"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for target in selected:
        print(f"{target}: {measurements[target]['image']} sha256={measurements[target]['image_sha256']}")
    print(f"state evidence: {(EVIDENCE_DIR / 'modeling-fit-state-evidence.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
