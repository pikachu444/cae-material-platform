from __future__ import annotations

# ruff: noqa: E501
import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[3]
HTML_PATH = ROOT / "docs/00-research/ux-service-reference/modeling-fit-normal.html"
EVIDENCE_DIR = ROOT / "docs/17-evidence/images/issue-167-service-reference"
STAGING_PATH = ROOT / "docs/00-research/ux-service-reference/modeling-fit-wave03.staging.json"

VIEWPORTS = {
    "1366x768": {"width": 1366, "height": 768, "device_scale_factor": 1},
    "1440x900": {"width": 1440, "height": 900, "device_scale_factor": 1},
    "1920x1080": {"width": 1920, "height": 1080, "device_scale_factor": 1},
}
TARGETS = {
    "modeling-fit-normal-1366x768": ("normal", "1366x768"),
    "modeling-fit-normal-1440x900": ("normal", "1440x900"),
    "modeling-fit-normal-1920x1080": ("normal", "1920x1080"),
    "modeling-fit-candidate-parameters-long-1440x900": ("candidate-parameters-long", "1440x900"),
}
EVIDENCE_STATES = (
    "no-candidate-empty",
    "calculating",
    "stale-or-no-selection-blocked",
    "fit-error-with-rail-ribbon-and-graph-preserved",
)
LEGACY_SELECTORS = ("page-stack", "page-heading", "content-card", "module-material-card", "hero-actions", "eyebrow", "status-badge", "count-chip")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate MOD-FIT WAVE-03 static service reference evidence.")
    parser.add_argument("--target", choices=sorted(TARGETS), help="Validate one approval target.")
    parser.add_argument("--all-packet-targets", action="store_true", help="Validate all approval targets and state evidence.")
    parser.add_argument("--expect-main-agent-status", default="pending", choices=("pending", "accepted", "rejected"), help="Expected staging lifecycle status.")
    return parser.parse_args()


def fail(message: str) -> None:
    raise AssertionError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    require(header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR", f"not a PNG image: {path.relative_to(ROOT)}")
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def image_record(path: Path, expected_sha: str = "", expected_size: tuple[int, int] | None = None) -> dict[str, Any]:
    require(path.is_file(), f"missing image: {path.relative_to(ROOT)}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    require(not expected_sha or digest == expected_sha, f"sha256 mismatch: {path.relative_to(ROOT)}")
    size = png_size(path)
    if expected_size:
        require(size == expected_size, f"dimensions {size} != {expected_size}: {path.relative_to(ROOT)}")
    return {"path": str(path.relative_to(ROOT)), "sha256": digest, "width": size[0], "height": size[1]}


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


def dom_snapshot(page: Page) -> dict[str, Any]:
    return page.evaluate(
        """() => {
          const visible = (element) => !!element && (element.checkVisibility
            ? element.checkVisibility({checkOpacity: false, checkVisibilityCSS: true})
            : !!(element.offsetWidth || element.offsetHeight));
          const rect = (selector) => { const element = document.querySelector(selector); if (!element) return null; const r = element.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom}; };
          const contains = (outer, inner) => !!outer && !!inner && inner.left >= outer.left - .6 && inner.right <= outer.right + .6 && inner.top >= outer.top - .6 && inner.bottom <= outer.bottom + .6;
          const simpleRect = (selector) => { const element = document.querySelector(selector); if (!element) return null; const r = element.getBoundingClientRect(); return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height}; };
          const intersects = (a, b) => !!a && !!b && a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
          const workspace = simpleRect('[data-region="workspace-grid"]'); const graph = simpleRect('[data-region="graph"]');
          const table = document.querySelector('.candidate-table'); const tableRect = simpleRect('.candidate-table');
          const cells = [...document.querySelectorAll('.candidate-table th,.candidate-table td')].filter((cell) => { const r = cell.getBoundingClientRect(); return visible(cell) && r.width > 0 && r.height > 0; }).map((cell) => { const r = cell.getBoundingClientRect(); return {inside:!!tableRect && r.left >= tableRect.left - .6 && r.right <= tableRect.right + .6, contained:cell.scrollWidth <= cell.clientWidth + 1}; });
          const nested = [];
          const interactive = (element) => element.matches('button,input,select,textarea,a[href],summary') || (element.matches('[role][tabindex]') && Number(element.getAttribute('tabindex')) >= 0);
          for (const inner of document.querySelectorAll('button,input,select,textarea,a[href],summary,[role][tabindex]')) { let ancestor = inner.parentElement; while (ancestor) { if (interactive(ancestor)) { nested.push(`${ancestor.tagName}:${inner.tagName}`); break; } ancestor = ancestor.parentElement; } }
          const plot = document.querySelector('.engineering-plot');
          const plotRect = simpleRect('.engineering-plot');
          const plotArea = plot ? {left:Number(plot.dataset.plotLeft),right:Number(plot.dataset.plotRight),top:Number(plot.dataset.plotTop),bottom:Number(plot.dataset.plotBottom)} : null;
          const actualPlot = simpleRect('.plot-background');
          const viewBox = plot?.viewBox?.baseVal;
          const svgScale = plotRect && viewBox && viewBox.width > 0 && viewBox.height > 0 ? {x:plotRect.width/viewBox.width,y:plotRect.height/viewBox.height,delta:Math.abs((plotRect.width/viewBox.width)-(plotRect.height/viewBox.height))} : null;
          const seriesGeometry = [...(plot?.querySelectorAll('.curve') || [])].map((series) => {
            const points = (series.getAttribute('points') || '').trim().split(" ").filter(Boolean).map((point) => point.split(',').map(Number));
            const box = series.getBBox(); const first = points[0] || []; const last = points[points.length - 1] || [];
            return {key:series.dataset.seriesKey || '',startStrain:Number(series.dataset.startStrain),startStressMpa:Number(series.dataset.startStressMpa),bbox:{x:box.x,y:box.y,width:box.width,height:box.height,right:box.x+box.width,bottom:box.y+box.height},firstPoint:{x:first[0],y:first[1]},lastPoint:{x:last[0],y:last[1]},pointCount:points.length};
          });
          const canvasRect = simpleRect('.graph-canvas');
          const labelElements = [...(plot?.querySelectorAll('.plot-labels text') || []), ...(document.querySelectorAll('[data-compact-plot-labels] [data-plot-label]') || [])].filter((element) => {
            const value = element.getBoundingClientRect();
            return visible(element) && value.width > 0 && value.height > 0;
          });
          const labels = labelElements.map((label) => {
            const r = label.getBoundingClientRect(); const style = getComputedStyle(label);
            return {text:label.textContent.trim(),height:r.height,fontSize:Number.parseFloat(style.fontSize),visible:visible(label),insideSvg:!!plotRect && r.left >= plotRect.left - .6 && r.right <= plotRect.right + .6 && r.top >= plotRect.top - .6 && r.bottom <= plotRect.bottom + .6,insideCanvas:!!canvasRect && r.left >= canvasRect.left - .6 && r.right <= canvasRect.right + .6 && r.top >= canvasRect.top - .6 && r.bottom <= canvasRect.bottom + .6};
          });
          const disclosureRect = simpleRect('#candidate-parameters');
          const tableViewportRect = simpleRect('.candidate-table-scroll');
          const rowContainment = [...document.querySelectorAll('.candidate-table tbody .candidate-row')].map((row) => {
            const r = row.getBoundingClientRect();
            return {candidate:row.dataset.candidate || '',visible:visible(row),insideViewport:!!tableViewportRect && r.left >= tableViewportRect.left - .6 && r.right <= tableViewportRect.right + .6 && r.top >= tableViewportRect.top - .6 && r.bottom <= tableViewportRect.bottom + .6};
          });
          const selectionRect = simpleRect('[data-selection-evidence]');
          const parameterEntries = [...document.querySelectorAll('.parameter-entry')].filter(visible).map((entry) => {
            const r = entry.getBoundingClientRect(); const name = entry.querySelector('span');
            return {name:name?.textContent.trim() || '',insideEvidence:!!selectionRect && r.left >= selectionRect.left - .6 && r.right <= selectionRect.right + .6 && r.top >= selectionRect.top - .6 && r.bottom <= selectionRect.bottom + .6,nameClipped:!!name && name.scrollWidth > name.clientWidth + 1};
          });
          const requiredElements = ['[data-selection-reason]','[data-warning-ack]','[data-selection-help]'].map((selector) => {
            const element = document.querySelector(selector); const r = element?.getBoundingClientRect();
            return {selector,insideEvidence:!!selectionRect && !!r && r.left >= selectionRect.left - .6 && r.right <= selectionRect.right + .6 && r.top >= selectionRect.top - .6 && r.bottom <= selectionRect.bottom + .6};
          });
          return {
            overflow:{documentHorizontal:Math.max(0,document.documentElement.scrollWidth-document.documentElement.clientWidth),documentVertical:Math.max(0,document.documentElement.scrollHeight-document.documentElement.clientHeight),bodyHorizontal:Math.max(0,document.body.scrollWidth-document.body.clientWidth),bodyVertical:Math.max(0,document.body.scrollHeight-document.body.clientHeight)},
            regions:{workspace:rect('[data-region="workspace-grid"]'),navigator:rect('[data-region="navigator"]'),main:rect('.modeling-main-surface'),ribbon:rect('.fit-ribbon'),disclosure:rect('#candidate-parameters'),graph:rect('[data-region="graph"]'),plot:rect('.engineering-plot')},
            rail:{width:Math.round(document.querySelector('[data-region="navigator"]')?.getBoundingClientRect().width || 0), ariaNow:Number(document.querySelector('.modeling-divider-resizer')?.getAttribute('aria-valuenow')), ariaExpanded:document.querySelector('.modeling-divider-resizer')?.getAttribute('aria-expanded') === 'true'},
            graph:{share:workspace&&graph?graph.width/workspace.width:0, width:plot?plot.getBoundingClientRect().width:0, series:plot?{minStrain:Number(plot.dataset.seriesMinStrain),maxStrain:Number(plot.dataset.seriesMaxStrain),minStress:Number(plot.dataset.seriesMinStressMpa),maxStress:Number(plot.dataset.seriesMaxStressMpa),computedMinStrain:Number(plot.dataset.axisComputedMinStrain),computedStrain:Number(plot.dataset.axisComputedMaxStrain),computedMinStress:Number(plot.dataset.axisComputedMinStressMpa),computedStress:Number(plot.dataset.axisComputedMaxStressMpa),niceMinStrain:Number(plot.dataset.axisNiceMinStrain),niceMaxStrain:Number(plot.dataset.axisNiceMaxStrain),niceMinStress:Number(plot.dataset.axisNiceMinStressMpa),niceMaxStress:Number(plot.dataset.axisNiceMaxStressMpa),ratio:Number(plot.dataset.axisHeadroomRatio),derivation:plot.dataset.axisDerivation,alteredProof:plot.dataset.axisAlteredProof === 'true',initialYieldStressMpa:Number(plot.dataset.initialYieldStressMpa),zeroPlasticStressPositive:plot.dataset.zeroPlasticStressPositive === 'true',xQuantity:plot.dataset.xQuantity||'',xUnit:plot.dataset.xUnit||'',yQuantity:plot.dataset.yQuantity||'',yUnit:plot.dataset.yUnit||'',preserveAspectRatio:plot.getAttribute('preserveAspectRatio'),renderedWidth:Number(plot.dataset.renderedWidth),renderedHeight:Number(plot.dataset.renderedHeight),viewBox:viewBox?{x:viewBox.x,y:viewBox.y,width:viewBox.width,height:viewBox.height}:null,svgScale,nonUniformScale:plot.dataset.nonUniformScale === 'true',plotArea,seriesGeometry,labels,labelsContained:labels.length >= 10 && labels.every((label)=>label.visible&&label.height >= 10&&label.insideCanvas),labelsReadable:labels.every((label)=>label.height >= 10&&label.fontSize >= 10.5)}:null},
            disclosure:{open:document.querySelector('#candidate-parameters')?.hidden===false, rows:document.querySelectorAll('.candidate-table tbody .candidate-row').length, visibleRows:[...document.querySelectorAll('.candidate-table tbody .candidate-row')].filter(visible).length, tableOverflow:table?table.scrollWidth-table.clientWidth:0, allInside:cells.every((cell)=>cell.inside), allContained:cells.every((cell)=>cell.contained), bodyHeight:rect('.candidate-parameters-body')?.height || 0, height:disclosureRect?.height || 0, bodyClientHeight:document.querySelector('.candidate-parameters-body')?.clientHeight || 0, bodyScrollHeight:document.querySelector('.candidate-parameters-body')?.scrollHeight || 0, triggerExpanded:document.querySelector('.disclosure-trigger')?.getAttribute('aria-expanded') || '', requiredContainment:{candidateRows:rowContainment,allCandidateRowsInside:rowContainment.every((row)=>row.visible),selectionEvidenceInside:!!selectionRect,parameterEntries,allParameterEntriesInside:parameterEntries.every((entry)=>entry.insideEvidence),requiredElements,allRequiredElementsInside:requiredElements.every((entry)=>entry.insideEvidence),parameterNamesClipped:parameterEntries.some((entry)=>entry.nameClipped)}},
            content:{stageLabels:[...document.querySelectorAll('.stage-button')].map((element)=>element.textContent.trim()),activeStage:document.querySelector('.stage-button.active')?.textContent.trim()||'',curveRows:[...document.querySelectorAll('.curve-row')].filter(visible).length,included:[...document.querySelectorAll('.curve-row')].filter(visible).filter((row)=>row.querySelector('input[type="checkbox"]:checked')).length,selectedCandidate:document.querySelector('.candidate-row.selected')?.dataset.candidate||'',recommended:[...document.querySelectorAll('.candidate-row')].filter((row)=>row.textContent.includes('Recommended')).map((row)=>row.dataset.candidate),saveDisabled:document.querySelector('[data-action="save-fit"]')?.disabled===true,saveReason:document.querySelector('[data-save-reason]')?.textContent.trim()||'',downstreamStatus:document.querySelector('[data-downstream-status]')?.textContent.trim()||'',blockedReason:document.querySelector('[data-blocked-reason]')?.textContent.trim()||'',targetStrain:document.querySelector("input[name='target_strain']")?.value||'',selectionHelp:document.querySelector('[data-selection-help]')?.textContent.trim()||'',updateDisabled:document.querySelector('[data-action="update-candidates"]')?.disabled===true,graphCurves:[...document.querySelectorAll('.engineering-plot .curve')].filter(visible).length,graphEmpty:visible(document.querySelector('[data-graph-empty]')),graphOverlay:document.querySelector('[data-graph-state-overlay]')?.textContent.trim()||'',selectedReason:document.querySelector('[data-selection-reason]')?.value.trim()||'',warningAck:document.querySelector('[data-warning-ack]')?.checked===true,selectionEvidence:visible(document.querySelector('[data-selection-evidence]')),candidateState:document.body.dataset.candidateState||'',statusSelection:document.querySelector('[data-status-selection]')?.textContent.trim()||'',statusJob:document.querySelector('[data-status-job]')?.textContent.trim()||'',legacy:['page-stack','page-heading','content-card','module-material-card','hero-actions','eyebrow','status-badge','count-chip'].filter((name)=>document.querySelector(`.${name}`)),nested},
            typography:{body:Number.parseFloat(getComputedStyle(document.body).fontSize),metadata:Number.parseFloat(getComputedStyle(document.querySelector('.context-material')||document.body).fontSize),rail:Number.parseFloat(getComputedStyle(document.querySelector('.curve-label strong')||document.body).fontSize),ribbon:Number.parseFloat(getComputedStyle(document.querySelector('.control-group legend')||document.body).fontSize),decisionTable:Number.parseFloat(getComputedStyle(document.querySelector('.candidate-table td')||document.body).fontSize),decision:Number.parseFloat(getComputedStyle(document.querySelector('.selection-help')||document.body).fontSize),graphFooter:Number.parseFloat(getComputedStyle(document.querySelector('.plot-legend')||document.body).fontSize),status:Number.parseFloat(getComputedStyle(document.querySelector('[data-region="status-bar"]')||document.body).fontSize),clipped:[...document.querySelectorAll('.fit-command-copy small,.blocked-reason,.selection-help')].some((element)=>element.scrollWidth>element.clientWidth+1||element.scrollHeight>element.clientHeight+1)},
            footer:(()=>{const axis=simpleRect('[data-plot-x-axis-title]');const legend=simpleRect('.plot-legend');const canvas=simpleRect('.graph-canvas');const stage=simpleRect('.plot-stage');const layout=simpleRect('.plot-layout');const touches=[...(plot?.querySelectorAll('.curve')||[])].some((series)=>{const points=(series.getAttribute('points')||'').trim().split(' ').filter(Boolean).map((point)=>{const [x,y]=point.split(',').map(Number);const svgPoint=plot.createSVGPoint();svgPoint.x=x;svgPoint.y=y;const mapped=svgPoint.matrixTransform(plot.getScreenCTM());return {x:mapped.x,y:mapped.y};});return points.some((point,index)=>{if(!index)return false;const start=points[index-1];const steps=Math.max(1,Math.ceil(Math.max(Math.abs(point.x-start.x),Math.abs(point.y-start.y))/4));return Array.from({length:steps+1},(_,step)=>step/steps).some((ratio)=>{const x=start.x+(point.x-start.x)*ratio;const y=start.y+(point.y-start.y)*ratio;return !!legend&&x>=legend.left-5&&x<=legend.right+5&&y>=legend.top-5&&y<=legend.bottom+5;});});});return {axis,legend,canvas,stage,axisLegendIntersect:intersects(axis,legend),legendContained:!!stage&&!!legend&&legend.left>=stage.left-.5&&legend.right<=stage.right+.5&&legend.top>=stage.top-.5&&legend.bottom<=stage.bottom+.5,legendInsidePlot:!!stage&&!!legend&&legend.left>stage.left&&legend.right<stage.right&&legend.top>stage.top&&legend.bottom<stage.bottom,legendPlacement:plot?.dataset.legendPlacement||'',legendCollisionCount:Number(plot?.dataset.legendCollisionCount||-1),legendFallback:plot?.dataset.legendFallback==='true',curveTouchesLegend:touches,externalWidthTax:layout&&stage?Math.max(0,layout.width-stage.width):0};})(),
            topology:{workspaceHeight:workspace?.height||0,fitWorkspaceHeight:Math.max(0,(workspace?.height||0)-(simpleRect('.fit-ribbon')?.height||0)),graphHeight:graph?.height||0,actualPlotHeight:actualPlot?.height||0,actualPlotShare:actualPlot&&workspace?actualPlot.height/workspace.height:0,actualPlotFitShare:actualPlot&&workspace?actualPlot.height/Math.max(1,workspace.height-(simpleRect('.fit-ribbon')?.height||0)):0,drawerShare:disclosureRect&&workspace?disclosureRect.height/workspace.height:0,curveRows:[...document.querySelectorAll('.curve-row')].filter(visible).map((row)=>row.getBoundingClientRect().height),operations:[...document.querySelectorAll('.operation-row')].filter(visible).map((row)=>row.getBoundingClientRect().height),rail:{clientHeight:document.querySelector('.curve-scroll')?.clientHeight||0,scrollHeight:document.querySelector('.curve-scroll')?.scrollHeight||0,overflowY:getComputedStyle(document.querySelector('.curve-scroll')).overflowY},navigatorVisual:(()=>{const parent=document.querySelector('.curve-parent .truncate');const label=document.querySelector('.curve-label strong');const revision=document.querySelector('.curve-label small');const swatch=document.querySelector('.curve-swatch');const selected=document.querySelector('.curve-row.selected');const group=document.querySelector('.group-heading');const filter=document.querySelector('.navigator-filter input');const operation=document.querySelector('.operation-row:not(.selected) span:last-child');const parentBox=parent?.getBoundingClientRect();const labelBox=label?.getBoundingClientRect();const labelStyle=label?getComputedStyle(label):null;const operationStyle=operation?getComputedStyle(operation):null;const swatchBox=swatch?.getBoundingClientRect();return {paneCount:document.querySelector('[data-included-count]')?.textContent.trim()||'',sectionTextTransform:group?getComputedStyle(group).textTransform:'',sectionFontSize:group?Number.parseFloat(getComputedStyle(group).fontSize):0,filterFontSize:filter?Number.parseFloat(getComputedStyle(filter).fontSize):0,identityFontSize:labelStyle?Number.parseFloat(labelStyle.fontSize):0,identityFontWeight:labelStyle?Number.parseInt(labelStyle.fontWeight,10):0,operationFontSize:operationStyle?Number.parseFloat(operationStyle.fontSize):0,operationFontWeight:operationStyle?Number.parseInt(operationStyle.fontWeight,10):0,hierarchyIndentPx:parentBox&&labelBox?labelBox.left-parentBox.left:0,clippedIdentities:[...document.querySelectorAll('.curve-label strong')].filter((item)=>item.scrollWidth>item.clientWidth+1).length,clippedRevisions:[...document.querySelectorAll('.curve-label small')].filter((item)=>item.scrollWidth>item.clientWidth+1).length,clippedOperations:[...document.querySelectorAll('.operation-row span:last-child')].filter((item)=>item.scrollWidth>item.clientWidth+1).length,swatchWidth:swatchBox?.width||0,swatchHeight:swatchBox?.height||0,swatchBorderRadius:swatch?getComputedStyle(swatch).borderRadius:'',selectedBorderWidth:selected?Number.parseFloat(getComputedStyle(selected).borderLeftWidth):0,selectedBackground:selected?getComputedStyle(selected).backgroundColor:'',railBackground:getComputedStyle(document.querySelector('.curve-scroll')).backgroundColor,scrollbarGutter:getComputedStyle(document.querySelector('.curve-scroll')).scrollbarGutter,parentText:parent?.textContent.trim()||'',revisionText:revision?.textContent.trim()||''};})(),axis:(()=>{const overlay=[...document.querySelectorAll('[data-compact-plot-labels] [data-plot-label]')].filter(visible);const svg=[...(plot?.querySelectorAll('.plot-labels text')||[])].filter(visible);const labels=overlay.length?overlay:svg;const yElement=labels.find((node)=>node.dataset.plotLabel==='axis-title'||node.classList.contains('axis-title'));const xElement=document.querySelector('[data-plot-x-axis-title]');const y=yElement?.getBoundingClientRect();const x=xElement?.getBoundingClientRect();const plotElement=plot?.getBoundingClientRect();const tickElements=labels.filter((node)=>node!==yElement&&node!==xElement&&node.dataset.plotLabel!=='extrapolated'&&!node.classList.contains('extrapolation-label'));const xTickElements=tickElements.filter((node)=>node.dataset.plotLabel?.startsWith('x-')||node.getBoundingClientRect().top>=(actualPlot?.bottom||0));const yTickElements=tickElements.filter((node)=>!xTickElements.includes(node));const xTickBottom=Math.max(...xTickElements.map((node)=>node.getBoundingClientRect().bottom));const yTickLeft=Math.min(...yTickElements.map((node)=>node.getBoundingClientRect().left));const yTickRight=Math.max(...yTickElements.map((node)=>node.getBoundingClientRect().right));const ticks=tickElements.map((node)=>node.textContent.trim());const intersects=(a,b)=>!!a&&!!b&&a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top;return {visibleSource:overlay.length?'overlay':'svg',ticks,xTitle:xElement?.textContent.trim()||'',yTitle:yElement?.textContent.trim()||'',xTitleVisible:visible(xElement),xTitleFontSize:xElement?Number.parseFloat(getComputedStyle(xElement).fontSize):0,yTitleVisible:visible(yElement),xCentered:!!x&&!!actualPlot&&Math.abs((x.left+x.width/2)-(actualPlot.left+actualPlot.width/2))<=2,xTitleGapToTicksPx:x&&Number.isFinite(xTickBottom)?x.top-xTickBottom:null,yTitleGapToTicksPx:y&&Number.isFinite(yTickLeft)?yTickLeft-y.right:null,yTickGapToAxisPx:actualPlot&&Number.isFinite(yTickRight)?actualPlot.left-yTickRight:null,yTickCollision:tickElements.some((tick)=>intersects(y,tick.getBoundingClientRect())),yLegendCollision:intersects(y,simpleRect('.plot-legend')),yPlotCollision:intersects(y,actualPlot),yContained:!!y&&!!simpleRect('.graph-canvas')&&y.left>=simpleRect('.graph-canvas').left-.6&&y.right<=simpleRect('.graph-canvas').right+.6&&y.top>=simpleRect('.graph-canvas').top-.6&&y.bottom<=simpleRect('.graph-canvas').bottom+.6,plotInsets:actualPlot&&plotElement?{leftRatio:(actualPlot.left-plotElement.left)/plotElement.width,rightRatio:(plotElement.right-actualPlot.right)/plotElement.width,bottomRatio:(plotElement.bottom-actualPlot.bottom)/plotElement.height}:null};})(),},
          };
        }"""
    )


def validate_target(browser: Browser, target: str, state: str, viewport_name: str, expected_sha: str) -> dict[str, Any]:
    viewport = VIEWPORTS[viewport_name]
    image = EVIDENCE_DIR / f"{target}.png"
    image_info = image_record(image, expected_sha, (viewport["width"], viewport["height"]))
    page, console_errors, page_errors = open_page(browser, state, viewport)
    try:
        snapshot = dom_snapshot(page)
        require(not console_errors and not page_errors, f"browser errors for {target}: {console_errors + page_errors}")
        require(all(value == 0 for value in snapshot["overflow"].values()), f"overflow for {target}: {snapshot['overflow']}")
        expected_rail = {"1366x768": 184, "1440x900": 192, "1920x1080": 208}[viewport_name]
        require(abs(snapshot["rail"]["width"] - expected_rail) <= 1, f"rail {snapshot['rail']['width']} != {expected_rail} for {target}")
        require(snapshot["rail"]["ariaNow"] == snapshot["rail"]["width"], f"splitter ARIA width mismatch for {target}")
        require(snapshot["content"]["activeStage"] == "Fit", f"Fit stage inactive for {target}")
        require(snapshot["content"]["stageLabels"] == ["Data", "Process", "Fit", "Export"], f"stage contract changed for {target}")
        require(snapshot["content"]["curveRows"] == 3 and snapshot["content"]["included"] == 2, f"curve scope mismatch for {target}")
        require(snapshot["graph"]["share"] >= .72, f"graph share {snapshot['graph']['share']:.3f} < .72 for {target}")
        series = snapshot["graph"]["series"]
        require(series["derivation"] == "finite-plotted-span-plus-proportional-padding", f"axis derivation missing for {target}")
        require(snapshot["graph"]["series"]["alteredProof"], f"altered-extrema proof missing for {target}")
        require(series["xQuantity"] == "true_plastic_strain" and series["xUnit"] == "1" and series["yQuantity"] == "true_yield_stress" and series["yUnit"] == "MPa", f"hardening quantity contract changed for {target}: {series}")
        require(series["minStrain"] == 0 and series["minStress"] > 0 and series["initialYieldStressMpa"] > 0 and series["zeroPlasticStressPositive"], f"hardening response incorrectly includes an elastic origin for {target}: {series}")
        require(series["preserveAspectRatio"] is None and not series["nonUniformScale"], f"non-uniform SVG scaling is present for {target}: {series}")
        require(series["viewBox"] and abs(series["viewBox"]["width"] - series["renderedWidth"]) <= 1 and abs(series["viewBox"]["height"] - series["renderedHeight"]) <= 1 and series["svgScale"] and series["svgScale"]["delta"] <= .002, f"SVG viewport does not track rendered pixels for {target}: {series}")
        plot_area = series["plotArea"]
        series_geometry = series["seriesGeometry"]
        require(len(series_geometry) >= 6 and all(series["pointCount"] >= 6 for series in series_geometry), f"finite plotted point data missing for {target}")
        require(all(series_geometry_item["startStrain"] == 0 and series_geometry_item["startStressMpa"] > 0 and abs(series_geometry_item["startStressMpa"] - snapshot["graph"]["series"]["initialYieldStressMpa"]) <= .01 for series_geometry_item in series_geometry), f"candidate response does not start at positive initial yield stress for {target}: {series_geometry}")
        require(all(abs(series_geometry_item["firstPoint"]["x"] - plot_area["left"]) <= .6 and plot_area["top"] < series_geometry_item["firstPoint"]["y"] < plot_area["bottom"] for series_geometry_item in series_geometry), f"initial-yield anchor is outside the plot for {target}")
        require(all(plot_area["left"] < series["lastPoint"]["x"] < plot_area["right"] and plot_area["top"] < series["lastPoint"]["y"] < plot_area["bottom"] for series in series_geometry), f"series endpoint has no proportional headroom for {target}")
        require(snapshot["graph"]["series"]["labelsContained"], f"plot label escapes compact SVG/canvas for {target}: {snapshot['graph']['series']['labels']}")
        require(snapshot["graph"]["series"]["labelsReadable"], f"plot label is visually squashed below the compact engineering minimum for {target}: {snapshot['graph']['series']['labels']}")
        require(snapshot["graph"]["series"]["niceMaxStrain"] > snapshot["graph"]["series"]["maxStrain"] and snapshot["graph"]["series"]["niceMaxStress"] > snapshot["graph"]["series"]["maxStress"] and 0 < snapshot["graph"]["series"]["niceMinStress"] < snapshot["graph"]["series"]["minStress"], f"nice axis domain missing data-relative padding for {target}")
        require(snapshot["content"]["legacy"] == [], f"legacy selectors present for {target}: {snapshot['content']['legacy']}")
        require(snapshot["content"]["nested"] == [], f"nested interactive controls for {target}: {snapshot['content']['nested']}")
        require(snapshot["content"]["graphCurves"] >= 6, f"candidate graph series incomplete for {target}")
        topology = snapshot["topology"]
        require(all(26 <= height <= 28 for height in topology["curveRows"]), f"curve rail rows are not compact 26-28px: {topology['curveRows']}")
        require(all(24 <= height <= 26 for height in topology["operations"]), f"operation rows are not compact 24-26px: {topology['operations']}")
        navigator_visual = topology["navigatorVisual"]
        require(navigator_visual["paneCount"] == "2 / 3 included", f"curve summary is not compact or current: {navigator_visual}")
        require(navigator_visual["sectionTextTransform"] == "none" and 11 <= navigator_visual["sectionFontSize"] <= 12, f"section chrome is not sentence-case compact metadata: {navigator_visual}")
        require(navigator_visual["filterFontSize"] >= 12 and 12.5 <= navigator_visual["identityFontSize"] <= 13, f"navigator typography is not readable and compact: {navigator_visual}")
        require(400 <= navigator_visual["identityFontWeight"] <= 500 and 12 <= navigator_visual["operationFontSize"] <= 13 and 400 <= navigator_visual["operationFontWeight"] <= 500, f"navigator identities are too heavy or inconsistent: {navigator_visual}")
        require(8 <= navigator_visual["hierarchyIndentPx"] <= 24 and navigator_visual["clippedIdentities"] == 0 and navigator_visual["clippedRevisions"] == 0 and navigator_visual["clippedOperations"] == 0, f"navigator hierarchy or identity containment failed: {navigator_visual}")
        require(navigator_visual["swatchWidth"] <= 4 and navigator_visual["swatchHeight"] >= 14 and navigator_visual["swatchBorderRadius"] == "0px", f"curve sample must be a narrow engineering line, not a badge: {navigator_visual}")
        require(navigator_visual["selectedBorderWidth"] >= 3 and navigator_visual["selectedBackground"] != navigator_visual["railBackground"], f"selected curve lacks restrained fill/accent separation: {navigator_visual}")
        require("stable" in navigator_visual["scrollbarGutter"], f"curve rail does not reserve conditional local scroll space: {navigator_visual}")
        axis = topology["axis"]
        require(len(axis["ticks"]) >= 10 and all(tick.replace(",", "").replace(".", "", 1).isdigit() for tick in axis["ticks"]), f"axis ticks must be numeric only: {axis['ticks']}")
        require(axis["xTitle"] == "True plastic strain [1]" and axis["yTitle"] == "True yield stress (MPa)", f"axis titles changed: {axis}")
        require(axis["xTitleVisible"] and axis["xTitleFontSize"] >= 11 and axis["yTitleVisible"] and axis["yContained"] and axis["xCentered"] and not axis["yTickCollision"] and not axis["yLegendCollision"] and not axis["yPlotCollision"], f"visible axis title centering/collision failure: {axis}")
        require(0 <= axis["xTitleGapToTicksPx"] <= 12 and 2 <= axis["yTitleGapToTicksPx"] <= 20 and 2 <= axis["yTickGapToAxisPx"] <= 10, f"axis title/tick spacing is too loose or crowded: {axis}")
        require(axis["plotInsets"]["leftRatio"] <= .065 and axis["plotInsets"]["rightRatio"] <= .065 and axis["plotInsets"]["bottomRatio"] <= .115, f"plot insets waste graph area: {axis['plotInsets']}")
        footer = snapshot["footer"]
        require(footer["legendPlacement"] == "lower-right" and footer["legendCollisionCount"] == 0 and not footer["legendFallback"], f"current response legend is not in the verified lower-right region: {footer}")
        require(footer["legendContained"] and footer["legendInsidePlot"] and not footer["axisLegendIntersect"] and not footer["curveTouchesLegend"] and footer["externalWidthTax"] <= 1, f"plot-internal legend containment/collision/width gate failed: {footer}")
        typography = snapshot["typography"]
        require(typography["body"] >= 13 and typography["metadata"] >= 12, f"body/metadata typography below packet minimum for {target}: {typography}")
        require(typography["rail"] >= 12.5 and typography["ribbon"] >= 11.5 and typography["decision"] >= 12 and typography["graphFooter"] >= 10.5 and typography["status"] >= 12, f"compact engineering typography outside contract for {target}: {typography}")
        require(typography["decisionTable"] >= 13, f"candidate table data below 13px for {target}: {typography}")
        require(not snapshot["typography"]["clipped"], f"decision text clipped for {target}")
        if state == "normal":
            require(not snapshot["disclosure"]["open"], "normal Candidate parameters must be closed")
            require(snapshot["disclosure"]["triggerExpanded"] == "false", "closed drawer aria-expanded must be false")
            require(topology["actualPlotFitShare"] >= .45, f"normal actual plot Fit-workspace share {topology['actualPlotFitShare']:.3f} < .45")
            require(snapshot["content"]["selectedCandidate"] == "", "normal recommendation must not become selection")
            require(snapshot["content"]["statusSelection"] == "No Fit candidate selected", f"normal status bar must state no selection: {snapshot['content']}")
            require("blend-swift-voce" in snapshot["content"]["recommended"], "blend recommendation missing")
            require(snapshot["content"]["saveDisabled"] and snapshot["content"]["saveReason"], "normal Save gate missing adjacent reason")
            require(float(page.locator(".candidate-table td").first.evaluate("e => getComputedStyle(e).fontSize").replace("px", "")) >= 13, "normal candidate table data below 13px")
            require("Preview Swift / Voce 50/50 blend" in page.locator(".plot-legend").inner_text(), "preview blend identity missing")
        else:
            require(snapshot["disclosure"]["open"], "long Candidate parameters drawer must be open")
            require(snapshot["disclosure"]["triggerExpanded"] == "true", "open drawer aria-expanded must be true")
            require(snapshot["disclosure"]["rows"] == 5 and snapshot["disclosure"]["visibleRows"] >= 5, "long candidate table must contain five rows")
            require(snapshot["disclosure"]["allInside"] and snapshot["disclosure"]["allContained"], "long candidate table escapes drawer")
            require(snapshot["content"]["selectedCandidate"] == "blend-swift-voce", "long state must explicitly select calculated blend")
            require(snapshot["content"]["statusSelection"] == "Fit · Swift / Voce 50/50 blend selected" and snapshot["content"]["statusJob"] == "Fit candidate selected · decision draft", f"long status bar does not identify selected Fit candidate: {snapshot['content']}")
            require(snapshot["content"]["selectionEvidence"] and snapshot["content"]["selectedReason"] and snapshot["content"]["warningAck"], "long selection evidence/reason/ack missing")
            require("ready to save one immutable fit decision" in snapshot["content"]["selectionHelp"].lower(), f"long selection help does not describe ready decision: {snapshot['content']['selectionHelp']}")
            require(not snapshot["content"]["saveDisabled"], "long selected candidate should satisfy Save gate")
            require(topology["actualPlotHeight"] >= 230 and topology["actualPlotShare"] >= .30, f"long actual plot is not useful: {topology}")
            require(topology["drawerShare"] <= .35, f"long drawer exceeds 35% of workspace: {topology}")
            require(snapshot["disclosure"]["bodyScrollHeight"] > snapshot["disclosure"]["bodyClientHeight"], f"long drawer body must independently scroll: {snapshot['disclosure']}")
            drawer_body = page.locator(".candidate-parameters-body")
            drawer_metrics = drawer_body.evaluate("element => ({client: element.clientHeight, scroll: element.scrollHeight, top: element.scrollTop})")
            drawer_body.focus()
            page.keyboard.press("PageDown")
            require(drawer_body.evaluate("element => element.scrollTop") > drawer_metrics["top"], "long drawer body PageDown had no local consequence")
            require(float(page.locator(".candidate-table td").first.evaluate("e => getComputedStyle(e).fontSize").replace("px", "")) >= 13, "long candidate table data below 13px")
        return {"target": target, "state": state, "viewport": viewport, "image": image_info, "snapshot": snapshot, "console_errors": console_errors, "page_errors": page_errors}
    finally:
        page.close()


def validate_interactions(browser: Browser) -> dict[str, Any]:
    page, console_errors, page_errors = open_page(browser, "normal", VIEWPORTS["1440x900"])
    try:
        resizer = page.locator(".modeling-divider-resizer")
        initial_width = page.locator("[data-region='navigator']").bounding_box()["width"]
        resizer.focus()
        page.keyboard.press("ArrowRight")
        arrow_width = page.locator("[data-region='navigator']").bounding_box()["width"]
        page.keyboard.press("Home")
        home_width = page.locator("[data-region='navigator']").bounding_box()["width"]
        page.keyboard.press("End")
        end_width = page.locator("[data-region='navigator']").bounding_box()["width"]
        page.locator("[data-region='navigator-divider'] button").click()
        collapsed_width = page.locator("[data-region='navigator']").bounding_box()["width"]
        page.locator("[data-region='navigator-divider'] button").click()
        restored_width = page.locator("[data-region='navigator']").bounding_box()["width"]
        require(arrow_width > initial_width and home_width < initial_width and end_width > initial_width and collapsed_width == 0 and restored_width == end_width, "splitter geometry/restore contract failed")
        page.locator("input[name='include_specimen_03']").check()
        require(page.locator("body").get_attribute("data-candidate-state") == "stale", "inclusion change did not invalidate candidates")
        require(page.locator(".candidate-row.selected").count() == 0 and page.locator("[data-action='save-fit']").is_disabled(), "selection/save not cleared after stale change")
        page.locator("[data-action='update-candidates']").click()
        page.wait_for_timeout(180)
        require(page.locator("body").get_attribute("data-candidate-state") == "current" and page.locator(".candidate-row.selected").count() == 0, "update candidates auto-selected a row")
        page.locator(".disclosure-trigger").click()
        page.locator("button[data-select-candidate='blend-swift-voce']").click()
        page.locator("[data-selection-reason]").fill("Compare against observed hardening before save.")
        page.locator("[data-warning-ack]").check()
        require(not page.locator("[data-action='save-fit']").is_disabled(), "reason and warning acknowledgement did not unlock Save")
        page.locator("[data-graph-view='residual']").click()
        selected_after_residual = page.locator(".candidate-row.selected").get_attribute("data-candidate")
        page.locator("[data-graph-view='tangent']").click()
        selected_after_tangent = page.locator(".candidate-row.selected").get_attribute("data-candidate")
        require(selected_after_residual == "blend-swift-voce" and selected_after_tangent == "blend-swift-voce", "graph view changed decision context")
        page.locator(".drawer-close").click()
        require(page.locator("#candidate-parameters").get_attribute("hidden") is not None, "drawer close did not restore graph")
        page.locator("input[name='target_strain']").fill("1.10")
        page.locator("input[name='target_strain']").dispatch_event("change")
        require(page.locator("[data-status-selection]").inner_text() == "No Fit candidate selected", "Fit status bar did not reset after upstream invalidation")
        before_graph = page.locator("[data-region='graph']").bounding_box()["width"]
        page.evaluate("""() => { const rail=document.querySelector('.curve-scroll'); if (rail) { rail.dataset.validationLong='true'; rail.insertAdjacentHTML('beforeend', '<div class="validation-rail-tail">'+Array.from({length:32},(_,i)=>`<div>Evidence trace ${i+1} · source retained</div>`).join('')+'</div>'); rail.scrollTop=rail.scrollHeight; } }""")
        after_graph = page.locator("[data-region='graph']").bounding_box()["width"]
        require(abs(before_graph - after_graph) < .5, "long rail scroll changed graph width")
        return {"initial_width": initial_width, "arrow_width": arrow_width, "home_width": home_width, "end_width": end_width, "collapsed_width": collapsed_width, "restored_width": restored_width, "inclusion_invalidates": True, "update_no_auto_select": True, "reason_ack_unlocks_save": True, "graph_views_preserve_selection": True, "disclosure_restores_graph": True, "footer_resets_on_invalidation": True, "long_rail_preserves_graph_width": True, "console_errors": console_errors, "page_errors": page_errors}
    finally:
        page.close()


def validate_state_evidence() -> dict[str, Any]:
    evidence_path = EVIDENCE_DIR / "modeling-fit-state-evidence.json"
    require(evidence_path.is_file(), "missing modeling-fit-state-evidence.json")
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    result: dict[str, Any] = {}
    for state in EVIDENCE_STATES:
        captures = payload.get(state, {}).get("captures", [])
        require(len(captures) == 3, f"state {state} must have three viewport captures")
        result[state] = []
        for capture in captures:
            viewport = capture["viewport"]
            path = ROOT / capture["image"]
            result[state].append(image_record(path, capture.get("image_sha256", ""), (viewport["width"], viewport["height"])))
            require(capture.get("console_errors", []) == [] and capture.get("page_errors", []) == [], f"browser errors recorded for {state}/{capture['target']}")
            require(all(value == 0 for value in capture.get("overflow", {}).values()), f"overflow recorded for {state}/{capture['target']}: {capture.get('overflow')}")
            if state == "no-candidate-empty":
                geometry = capture.get("geometry", {})
                disclosure = geometry.get("disclosure", {})
                topology = geometry.get("topology", {})
                require(disclosure.get("open") is False and disclosure.get("triggerExpanded") == "false", f"empty-state drawer must remain closed: {capture['target']} {disclosure}")
                require(topology.get("actualPlotHeight", 0) >= 180, f"empty-state graph is not useful: {capture['target']} {topology}")
            if state == "stale-or-no-selection-blocked":
                content = capture.get("geometry", {}).get("visibleContent", {})
                require(content.get("targetStrain") == "1.20", f"stale state target strain input is not 1.20 for {capture['target']}: {content}")
                require("1.20" in content.get("downstreamStatus", "") and "1.20" in content.get("blockedReason", ""), f"stale state changed-intent copy is inconsistent for {capture['target']}: {content}")
                require(content.get("selectedCandidate", "") == "" and content.get("saveDisabled") is True, f"stale state selection/save gate not cleared for {capture['target']}: {content}")
                require(content.get("statusSelection", "") == "No Fit candidate selected", f"stale state footer did not reset selected candidate: {content}")
    return result


def main() -> None:
    args = parse_args()
    require(HTML_PATH.is_file(), f"missing HTML: {HTML_PATH}")
    require(STAGING_PATH.is_file(), f"missing staging: {STAGING_PATH}")
    staging = json.loads(STAGING_PATH.read_text(encoding="utf-8"))
    require(staging.get("family") == "MOD-FIT", "staging family must be MOD-FIT")
    require(staging.get("status") == args.expect_main_agent_status, f"staging status {staging.get('status')} != {args.expect_main_agent_status}")
    selected = list(TARGETS) if args.all_packet_targets else [args.target]
    require(all(target in TARGETS for target in selected), "no target selected")
    target_results: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for target in selected:
                state, viewport_name = TARGETS[target]
                expected_sha = staging.get("targets", {}).get(target, {}).get("sha256", "")
                target_results.append(validate_target(browser, target, state, viewport_name, expected_sha))
            interactions = validate_interactions(browser) if args.all_packet_targets else {}
        finally:
            browser.close()
    state_results = validate_state_evidence() if args.all_packet_targets else {}
    print(f"VALIDATED {len(target_results)} MOD-FIT approval target(s)")
    target_summary = [{"target": result["target"], "sha256": result["image"]["sha256"], "viewport": f"{result['image']['width']}x{result['image']['height']}"} for result in target_results]
    print(f"TARGETS {json.dumps(target_summary, ensure_ascii=False)}")
    if args.all_packet_targets:
        print(f"STATE_EVIDENCE {json.dumps({state: len(records) for state, records in state_results.items()})}")
        print(f"INTERACTIONS {json.dumps(interactions, ensure_ascii=False)}")
    print("PASS zero overflow, browser errors, legacy selectors, nested interactive controls, stale-selection and axis derivation gates")


if __name__ == "__main__":
    main()
