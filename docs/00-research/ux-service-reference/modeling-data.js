const root = document.documentElement;
const body = document.body;
const interactionStatus = document.querySelector("#interaction-status");
const navigatorPane = document.querySelector("[data-region='navigator']");
const navigatorDivider = document.querySelector("[data-region='navigator-divider']");
const dividerButton = navigatorDivider?.querySelector("button");
const sourceTabs = [...document.querySelectorAll(".source-tab")];
const sourcePanels = [...document.querySelectorAll(".source-panel")];
const savedDatasets = [...document.querySelectorAll(".saved-dataset")];
const curveRows = [...document.querySelectorAll(".curve-row")];
const graphControls = [...document.querySelectorAll(".graph-control")];
const graphCanvas = document.querySelector(".graph-canvas");
const graphPlot = document.querySelector(".source-plot");
const graphLegend = document.querySelector(".plot-legend");
const SVG_NS = "http://www.w3.org/2000/svg";
const PLOT_MARGIN = {left: 80, right: 24, top: 24, bottom: 52};
const PLOT_NICE_FACTORS = [1, 2, 2.5, 5, 10];
const SOURCE_STRAIN = [0, 0.005, 0.01, 0.02, 0.04, 0.07, 0.1, 0.14, 0.17, 0.2];
const SOURCE_SERIES = [
  {className: "curve-one", values: [0, 155, 288, 432, 560, 660, 725, 780, 820, 850]},
  {className: "curve-two", values: [0, 148, 278, 420, 550, 651, 717, 773, 814, 843]},
  {className: "curve-three", values: [0, 141, 268, 407, 536, 638, 705, 762, 803, 835]},
];

function svgElement(name, attributes = {}) {
  const element = document.createElementNS(SVG_NS, name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
  return element;
}

function niceUpperBound(observedMaximum, targetIntervals, headroomRatio) {
  const desired = Math.max(observedMaximum, 1e-9) * (1 + headroomRatio);
  const rawStep = desired / targetIntervals;
  const exponent = 10 ** Math.floor(Math.log10(rawStep));
  const normalized = rawStep / exponent;
  const factor = PLOT_NICE_FACTORS.find((candidate) => candidate >= normalized) || 10;
  const step = factor * exponent;
  return Math.max(step, Math.ceil((desired - Number.EPSILON) / step) * step);
}

function axisTicks(minimum, maximum, count) {
  const interval = (maximum - minimum) / count;
  return Array.from({length: count + 1}, (_, index) => minimum + interval * index);
}

function formatStrain(value) {
  if (Math.abs(value) < 1e-9) return "0";
  return value.toFixed(2);
}

function formatStress(value) {
  return Math.round(value).toLocaleString("en-US");
}

function smoothPath(points) {
  if (!points.length) return "";
  if (points.length === 1) return `M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`;
  let path = `M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`;
  for (let index = 0; index < points.length - 1; index += 1) {
    const previous = points[index - 1] || points[index];
    const current = points[index];
    const next = points[index + 1];
    const afterNext = points[index + 2] || next;
    const controlOne = {
      x: current.x + (next.x - previous.x) / 6,
      y: current.y + (next.y - previous.y) / 6,
    };
    const controlTwo = {
      x: next.x - (afterNext.x - current.x) / 6,
      y: next.y - (afterNext.y - current.y) / 6,
    };
    path += ` C ${controlOne.x.toFixed(2)} ${controlOne.y.toFixed(2)}, ${controlTwo.x.toFixed(2)} ${controlTwo.y.toFixed(2)}, ${next.x.toFixed(2)} ${next.y.toFixed(2)}`;
  }
  return path;
}

function chooseAxisTitleX(width, plotLeft, plotRight, titleWidth, canvasRect) {
  const candidates = [0.5, 0.38, 0.26];
  const legendRect = graphLegend?.getBoundingClientRect();
  const titleY = canvasRect.bottom - 18;
  const titleTop = titleY - 13;
  const titleBottom = titleY + 3;
  for (const fraction of candidates) {
    const x = plotLeft + (plotRight - plotLeft) * fraction;
    const left = canvasRect.left + x - titleWidth / 2;
    const right = canvasRect.left + x + titleWidth / 2;
    const collides = legendRect
      && titleBottom >= legendRect.top
      && titleTop <= legendRect.bottom
      && right >= legendRect.left
      && left <= legendRect.right;
    if (!collides) return x;
  }
  return plotLeft + (plotRight - plotLeft) * 0.5;
}

let lastPlotSize = null;
function renderResponsivePlot(force = false) {
  if (!graphCanvas || !graphPlot) return;
  const rectangle = graphCanvas.getBoundingClientRect();
  const width = Math.max(1, rectangle.width);
  const height = Math.max(1, rectangle.height);
  if (!force && lastPlotSize && Math.abs(lastPlotSize.width - width) < 0.25 && Math.abs(lastPlotSize.height - height) < 0.25) return;
  lastPlotSize = {width, height};
  graphPlot.setAttribute("viewBox", `0 0 ${width.toFixed(2)} ${height.toFixed(2)}`);
  graphPlot.setAttribute("width", width.toFixed(2));
  graphPlot.setAttribute("height", height.toFixed(2));
  graphPlot.dataset.renderWidth = width.toFixed(2);
  graphPlot.dataset.renderHeight = height.toFixed(2);

  const plotLeft = PLOT_MARGIN.left;
  const plotRight = Math.max(plotLeft + 1, width - PLOT_MARGIN.right);
  const plotTop = PLOT_MARGIN.top;
  const plotBottom = Math.max(plotTop + 1, height - PLOT_MARGIN.bottom);
  const plotWidth = plotRight - plotLeft;
  const plotHeight = plotBottom - plotTop;
  const headroomRatio = Number(graphPlot.dataset.axisHeadroomRatio || 0.1);
  const observedMaxStrain = Math.max(...SOURCE_STRAIN);
  const observedMaxStress = Math.max(...SOURCE_SERIES.flatMap((series) => series.values));
  const observedMinStrain = Math.min(...SOURCE_STRAIN);
  const observedMinStress = Math.min(...SOURCE_SERIES.flatMap((series) => series.values));
  const xMin = observedMinStrain >= 0 ? 0 : observedMinStrain;
  const yMin = observedMinStress >= 0 ? 0 : observedMinStress;
  const xMax = niceUpperBound(observedMaxStrain, Number(graphPlot.dataset.axisTargetIntervalsStrain || 5), headroomRatio);
  const yMax = niceUpperBound(observedMaxStress, Number(graphPlot.dataset.axisTargetIntervalsStress || 4), headroomRatio);
  const xTicks = axisTicks(xMin, xMax, Number(graphPlot.dataset.axisTargetIntervalsStrain || 5));
  const yTicks = axisTicks(yMin, yMax, Number(graphPlot.dataset.axisTargetIntervalsStress || 4));
  const toX = (value) => plotLeft + ((value - xMin) / (xMax - xMin || 1)) * plotWidth;
  const toY = (value) => plotBottom - ((value - yMin) / (yMax - yMin || 1)) * plotHeight;
  graphPlot.dataset.seriesMinStrain = String(observedMinStrain);
  graphPlot.dataset.seriesMaxStrain = String(observedMaxStrain);
  graphPlot.dataset.seriesMinStressMpa = String(observedMinStress);
  graphPlot.dataset.seriesMaxStressMpa = String(observedMaxStress);
  graphPlot.dataset.axisMinStrain = String(xMin);
  graphPlot.dataset.axisMaxStrain = String(xMax);
  graphPlot.dataset.axisMinStressMpa = String(yMin);
  graphPlot.dataset.axisMaxStressMpa = String(yMax);
  graphPlot.dataset.plotLeft = String(plotLeft);
  graphPlot.dataset.plotRight = String(plotRight);
  graphPlot.dataset.plotTop = String(plotTop);
  graphPlot.dataset.plotBottom = String(plotBottom);

  const background = graphPlot.querySelector(".plot-background");
  background?.setAttribute("x", String(plotLeft));
  background?.setAttribute("y", String(plotTop));
  background?.setAttribute("width", String(plotWidth));
  background?.setAttribute("height", String(plotHeight));
  const grid = graphPlot.querySelector(".plot-grid");
  const axis = graphPlot.querySelector(".plot-axis");
  const labels = graphPlot.querySelector(".plot-labels");
  grid?.replaceChildren();
  axis?.replaceChildren();
  labels?.replaceChildren();

  xTicks.forEach((tick, index) => {
    const x = toX(tick);
    grid?.append(svgElement("line", {x1: x, y1: plotTop, x2: x, y2: plotBottom, "vector-effect": "non-scaling-stroke"}));
    const label = svgElement("text", {x, y: plotBottom + 18, "text-anchor": index === 0 ? "start" : index === xTicks.length - 1 ? "end" : "middle"});
    label.textContent = formatStrain(tick);
    labels?.append(label);
  });
  yTicks.forEach((tick) => {
    const y = toY(tick);
    grid?.append(svgElement("line", {x1: plotLeft, y1: y, x2: plotRight, y2: y, "vector-effect": "non-scaling-stroke"}));
    const label = svgElement("text", {x: plotLeft - 10, y: y + 4, "text-anchor": "end"});
    label.textContent = formatStress(tick);
    labels?.append(label);
  });
  axis?.append(svgElement("line", {x1: plotLeft, y1: plotBottom, x2: plotRight, y2: plotBottom, "vector-effect": "non-scaling-stroke"}));
  axis?.append(svgElement("line", {x1: plotLeft, y1: plotTop, x2: plotLeft, y2: plotBottom, "vector-effect": "non-scaling-stroke"}));

  SOURCE_SERIES.forEach((series) => {
    const path = graphPlot.querySelector(`.${series.className}`);
    if (!path) return;
    const points = SOURCE_STRAIN.map((strain, index) => ({x: toX(strain), y: toY(series.values[index])}));
    path.setAttribute("d", smoothPath(points));
    path.setAttribute("vector-effect", "non-scaling-stroke");
  });

  const xTitle = svgElement("text", {class: "axis-title", y: height - 10, "text-anchor": "middle"});
  xTitle.textContent = "Engineering strain [1]";
  labels?.append(xTitle);
  const estimatedTitleWidth = Math.max(108, xTitle.textContent.length * 6.2);
  xTitle.setAttribute("x", chooseAxisTitleX(width, plotLeft, plotRight, estimatedTitleWidth, rectangle));
  const yTitle = svgElement("text", {class: "axis-title", transform: `translate(18 ${(plotTop + plotBottom) / 2}) rotate(-90)`, "text-anchor": "middle"});
  yTitle.textContent = "Engineering stress (MPa)";
  labels?.append(yTitle);
}

function startResponsivePlot() {
  renderResponsivePlot(true);
  if (graphCanvas && typeof ResizeObserver !== "undefined") {
    const observer = new ResizeObserver(() => renderResponsivePlot());
    observer.observe(graphCanvas);
  }
  window.addEventListener("resize", () => renderResponsivePlot());
  window.renderModelingDataPlot = () => renderResponsivePlot(true);
}

const setInteractionStatus = (message) => {
  if (interactionStatus) interactionStatus.textContent = message;
};

const setText = (selector, value) => {
  const element = document.querySelector(selector);
  if (element) element.textContent = value;
};

const queryState = new URLSearchParams(window.location.search).get("state");
const pathState = window.location.pathname.includes("empty-new-session")
  ? "empty"
  : window.location.pathname.includes("long-invalid-mapping-blocked")
    ? "invalid"
    : null;
const requestedState = queryState || pathState || body.dataset.referenceState || "normal";

const stateMessages = {
  "loading-detecting": "Inspecting the local source… parser evidence and the current graph remain in place.",
  "loading-saving": "Saving Test Data… the exact source, mapping and preview are retained while the governed import completes.",
  "error-parse": "Source parse failed. The file and parser choices are preserved; choose another file or retry inspection.",
  "error-import": "Governed import failed. Source bytes, mapping rows and the last preview remain available for retry.",
  "error-save": "Save failed. No Test Data revision was registered; correct the source or retry with this mapping.",
};

function setSource(source, {announce = true} = {}) {
  sourceTabs.forEach((tab) => {
    const selected = tab.dataset.source === source;
    tab.classList.toggle("active", selected);
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
  });
  sourcePanels.forEach((panel) => {
    const visible = panel.id === `${source}-panel`;
    panel.hidden = !visible;
    panel.setAttribute("aria-hidden", String(!visible));
  });
  body.dataset.activeSource = source;
  if (announce) {
    setInteractionStatus(`${source === "library" ? "Library" : source === "local" ? "Local file" : "Test Data JSON"} source selected`);
  }
}

function selectDataset(row) {
  savedDatasets.forEach((candidate) => {
    const selected = candidate === row;
    candidate.classList.toggle("selected", selected);
    candidate.setAttribute("aria-selected", String(selected));
    const marker = candidate.querySelector(".selection-marker");
    if (marker) marker.textContent = selected ? "●" : "○";
    const state = candidate.querySelector(".dataset-state");
    if (state) state.textContent = selected ? "Selected" : "Available";
  });
  const label = row.dataset.dataset || "saved Test Data";
  setText("[data-graph-context]", `${label} · preview only`);
  setText("[data-status-selection]", label);
  setText("[data-stage-status]", "Data source · not saved");
  body.dataset.selectedDataset = label;
  setInteractionStatus(`${label} selected; graph preview context updated`);
}

function selectCurve(row) {
  curveRows.forEach((candidate) => {
    const selected = candidate === row;
    candidate.classList.toggle("selected", selected);
    candidate.setAttribute("aria-pressed", String(selected));
    candidate.tabIndex = selected ? 0 : -1;
  });
  const label = row.dataset.curve || "curve";
  body.dataset.selectedCurve = label;
  setInteractionStatus(`${label} selected; source record context retained`);
}

function updateIncludedCount() {
  const count = curveRows.filter((row) => row.querySelector("input[type='checkbox']")?.checked).length;
  setText("[data-included-count]", `${count} included`);
  body.dataset.includedCurves = String(count);
}

function setupEmptyState() {
  body.classList.add("state-empty");
  body.dataset.referenceState = "empty";
  setText("[data-included-count]", "0 included");
  setText("[data-saved-count]", "0");
  setText("[data-status-selection]", "No Test Data selected");
  setText("[data-status-revision]", "New session · no revision");
  setText(".context-material", "New session · no Material Model selected");
  setText("[data-graph-context]", "No Test Data selected · preview unavailable");
  setText("[data-status-warning]", "1 preparation task");
  setText("[data-stage-status]", "Data source · choose Local file");
  setText("[data-ribbon-state]", "New session · no saved preview");
  savedDatasets.forEach((row) => row.remove());
  document.querySelector(".source-plot")?.setAttribute("aria-hidden", "true");
  const note = document.createElement("div");
  note.className = "empty-library-note";
  note.innerHTML = "<strong>No saved datasets</strong><span>This new session has no Test Data, Mapping Profile, Recipe or downstream pointer.</span>";
  document.querySelector("#library-panel")?.append(note);
  const empty = document.querySelector(".graph-empty");
  if (empty) empty.hidden = false;
  setSource("library", {announce: false});
}

function showLocalEvidence() {
  const raw = document.querySelector(".raw-inspector");
  const mapping = document.querySelector(".mapping-block");
  if (raw) raw.hidden = false;
  if (mapping) mapping.hidden = false;
}

function setMappingReady() {
  const dependent = document.querySelector(".mapping-table tbody tr:nth-child(2) select[aria-label='Dependent source column']");
  if (dependent) dependent.value = "True stress MPa observed channel label";
  const rawUnit = document.querySelector(".mapping-table tbody tr:nth-child(2) select[aria-label='Dependent raw unit']");
  if (rawUnit) rawUnit.value = "MPa";
  const status = document.querySelector(".mapping-state");
  if (status) status.textContent = "Ready · preview available";
  const errorCell = document.querySelector(".mapping-error");
  if (errorCell) { errorCell.className = "mapping-ok"; errorCell.textContent = "Ready"; }
  const conflict = document.querySelector(".mapping-conflict");
  if (conflict) conflict.hidden = true;
  document.querySelectorAll("[data-action='update-preview'], [data-action='save-dataset']").forEach((button) => {
    button.disabled = true;
    button.setAttribute("aria-disabled", "true");
  });
}

function ensureStateMessage(message, isError = false) {
  const panel = document.querySelector("#local-panel");
  if (!panel) return;
  let element = panel.querySelector(".state-message");
  if (!element) {
    element = document.createElement("p");
    element.className = "state-message";
    panel.prepend(element);
  }
  element.textContent = message;
  element.setAttribute("role", isError ? "alert" : "status");
  body.dataset.stateMessage = message;
}

function setupExceptionalState(state) {
  if (state === "invalid") {
    body.classList.add("state-invalid");
    body.dataset.referenceState = "invalid";
    setSource("local", {announce: false});
    showLocalEvidence();
    setText("[data-status-selection]", "Local source · unsaved");
    setText("[data-status-revision]", "Raw source · immutable");
    setText("[data-status-job]", "Preview blocked");
    setText("[data-status-warning]", "1 mapping conflict");
    setText("[data-stage-status]", "Mapping invalid · preview blocked");
    setText("[data-ribbon-state]", "Blocked · not saved");
    setText("[data-graph-context]", "Last valid preview · stale · not updated");
    setText("[data-legend-note]", "Last valid preview · stale · not updated");
    const blocked = document.querySelector(".graph-blocked");
    if (blocked) blocked.hidden = false;
    return;
  }
  if (!stateMessages[state]) return;
  const isError = state.startsWith("error-");
  body.classList.add(isError ? "state-error" : "state-loading");
  body.dataset.referenceState = state;
  setSource("local", {announce: false});
  showLocalEvidence();
  if (state === "loading-detecting" || state === "error-parse") {
    const raw = document.querySelector(".raw-inspector");
    const mapping = document.querySelector(".mapping-block");
    if (raw) raw.hidden = true;
    if (mapping) mapping.hidden = true;
  } else {
    setMappingReady();
  }
  ensureStateMessage(stateMessages[state], isError);
  const canvas = document.querySelector(".graph-canvas");
  if (canvas) canvas.dataset.stateOverlay = isError ? "Error · context preserved" : "Loading · context preserved";
  setText("[data-status-selection]", "Local source · unsaved");
  setText("[data-status-revision]", "Preview · non-authoritative");
  setText("[data-status-job]", isError ? "Recovery available" : "Job in progress");
  setText("[data-status-warning]", isError ? "1 recoverable error" : "Source retained");
  setText("[data-stage-status]", isError ? "Error · source and graph retained" : "Loading · source and graph retained");
  setText("[data-ribbon-state]", isError ? "Error · not saved" : "Loading · not saved");
}

function syncNavigatorAria() {
  if (!navigatorPane || !navigatorDivider) return;
  const width = Math.round(navigatorPane.getBoundingClientRect().width);
  navigatorDivider.setAttribute("aria-valuenow", String(width));
  navigatorDivider.setAttribute("aria-expanded", String(width > 0));
  navigatorDividerButtonLabel(width > 0);
  body.dataset.navigatorWidth = String(width);
}

function navigatorDividerButtonLabel(open) {
  if (!dividerButton) return;
  dividerButton.setAttribute("aria-expanded", String(open));
  dividerButton.setAttribute("aria-label", `${open ? "Collapse" : "Expand"} curve and process navigator`);
  const span = dividerButton.querySelector("span");
  if (span) span.textContent = open ? "‹" : "›";
}

function setNavigatorWidth(width, {collapsed = false} = {}) {
  const minimum = Number(navigatorDivider?.getAttribute("aria-valuemin") || 180);
  const maximum = Number(navigatorDivider?.getAttribute("aria-valuemax") || 240);
  if (collapsed) {
    body.classList.add("navigator-collapsed");
    root.style.setProperty("--modeling-navigator-width", "0px");
    navigatorDivider?.setAttribute("aria-valuenow", "0");
    navigatorDivider?.setAttribute("aria-expanded", "false");
    navigatorDividerButtonLabel(false);
    body.dataset.navigatorCollapsed = "true";
    setInteractionStatus("Curve and process navigator collapsed");
    return;
  }
  const next = Math.max(minimum, Math.min(maximum, Math.round(width)));
  body.classList.remove("navigator-collapsed");
  root.style.setProperty("--modeling-navigator-width", `${next}px`);
  navigatorDivider?.setAttribute("aria-valuenow", String(next));
  navigatorDivider?.setAttribute("aria-expanded", "true");
  navigatorDividerButtonLabel(true);
  body.dataset.navigatorCollapsed = "false";
  body.dataset.navigatorWidth = String(next);
  setInteractionStatus(`Navigator width ${next}px; graph remains visible`);
}

sourceTabs.forEach((tab, index) => {
  tab.addEventListener("click", () => setSource(tab.dataset.source || "library"));
  tab.addEventListener("keydown", (event) => {
    let next = null;
    if (event.key === "ArrowRight") next = (index + 1) % sourceTabs.length;
    if (event.key === "ArrowLeft") next = (index - 1 + sourceTabs.length) % sourceTabs.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = sourceTabs.length - 1;
    if (next !== null) {
      event.preventDefault();
      sourceTabs[next].focus();
      setSource(sourceTabs[next].dataset.source || "library");
    }
  });
});

savedDatasets.forEach((row) => {
  row.addEventListener("click", () => selectDataset(row));
});

curveRows.forEach((row) => {
  row.addEventListener("click", (event) => {
    if (event.target instanceof HTMLInputElement || event.target.closest(".curve-visibility-button")) return;
    selectCurve(row);
  });
  row.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      selectCurve(row);
    }
  });
  row.querySelector("input[type='checkbox']")?.addEventListener("change", () => {
    updateIncludedCount();
    setInteractionStatus(`${row.dataset.curve} inclusion ${row.querySelector("input")?.checked ? "enabled" : "disabled"}`);
  });
  row.querySelector(".curve-visibility-button")?.addEventListener("click", (event) => {
    event.stopPropagation();
    const button = event.currentTarget;
    const visible = button.textContent.trim() !== "○";
    button.textContent = visible ? "○" : "◉";
    button.setAttribute("aria-label", `${visible ? "Show" : "Hide"} ${row.dataset.curve} on plot`);
    button.title = visible ? "Show on plot" : "Hide from plot";
    body.dataset.plotVisibility = `${row.dataset.curve}:${!visible}`;
    setInteractionStatus(`${row.dataset.curve} ${visible ? "hidden from" : "shown on"} plot`);
  });
});

graphControls.forEach((control) => {
  control.addEventListener("click", () => {
    graphControls.forEach((candidate) => {
      const active = candidate === control;
      candidate.classList.toggle("active", active);
      candidate.setAttribute("aria-pressed", String(active));
    });
    const view = control.dataset.graphView || "response";
    body.dataset.graphView = view;
    setInteractionStatus(`Graph view ${view === "reset" ? "reset" : view} selected`);
  });
});

document.querySelector("[data-action='choose-local']")?.addEventListener("click", () => {
  setSource("local");
  document.querySelector("#local-panel input[type='file']")?.focus();
  body.dataset.primaryConsequence = "local-file";
  setInteractionStatus("Local file source selected; choose a CSV, TSV or XLSX file");
});

document.querySelector("#advanced-top")?.addEventListener("click", () => {
  const details = [...document.querySelectorAll(".advanced-settings")]
    .find((candidate) => candidate.checkVisibility({checkOpacity: false, checkVisibilityCSS: true}))
    || document.querySelector(".graph-advanced");
  if (details instanceof HTMLDetailsElement) {
    details.open = !details.open;
    details.dispatchEvent(new Event("toggle"));
    details.scrollIntoView({block: "nearest"});
  }
  body.dataset.advancedRequested = "true";
  setInteractionStatus("Advanced source settings toggled");
});

document.querySelectorAll("details").forEach((details) => {
  details.addEventListener("toggle", () => {
    body.dataset.openDisclosure = details.open ? (details.querySelector("summary")?.textContent.trim() || "open") : "closed";
  });
});

dividerButton?.addEventListener("click", () => {
  const open = navigatorDivider?.getAttribute("aria-expanded") !== "false";
  if (open) {
    const current = Number(navigatorDivider?.getAttribute("aria-valuenow") || 192);
    body.dataset.navigatorRestoredWidth = String(current);
    setNavigatorWidth(current, {collapsed: true});
  } else {
    const restored = Number(body.dataset.navigatorRestoredWidth || root.style.getPropertyValue("--modeling-navigator-width").replace("px", "") || 192);
    setNavigatorWidth(restored || 192);
  }
});

navigatorDivider?.addEventListener("keydown", (event) => {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  const minimum = Number(navigatorDivider.getAttribute("aria-valuemin") || 180);
  const maximum = Number(navigatorDivider.getAttribute("aria-valuemax") || 240);
  const current = Number(navigatorDivider.getAttribute("aria-valuenow") || root.style.getPropertyValue("--modeling-navigator-width").replace("px") || 192);
  if (event.key === "Home") return setNavigatorWidth(minimum);
  if (event.key === "End") return setNavigatorWidth(maximum);
  setNavigatorWidth(current + (event.key === "ArrowRight" ? 8 : -8));
});

document.querySelectorAll(".stage-button").forEach((stage) => {
  stage.addEventListener("click", () => {
    document.querySelectorAll(".stage-button").forEach((candidate) => {
      const active = candidate === stage;
      candidate.classList.toggle("active", active);
      candidate.toggleAttribute("aria-current", active);
    });
    const label = stage.dataset.stage || "Data";
    body.dataset.activeStage = label;
    setInteractionStatus(`${label} stage selected; persistent graph retained`);
  });
});

document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLocaleLowerCase() === "k") {
    event.preventDefault();
    document.querySelector("#curve-filter")?.focus();
    setInteractionStatus("Curve filter focused");
  }
});

updateIncludedCount();
syncNavigatorAria();
if (requestedState === "empty") setupEmptyState();
else setupExceptionalState(requestedState);
startResponsivePlot();

// The static reference intentionally leaves loading/error commands read-only; these hooks let
// the deterministic capture exercise recovery states without mutating a saved revision.
window.setModelingDataReferenceState = (state) => {
  body.classList.remove("state-empty", "state-invalid", "state-loading", "state-error");
  document.querySelector(".empty-library-note")?.remove();
  document.querySelector(".state-message")?.remove();
  const empty = document.querySelector(".graph-empty");
  const blocked = document.querySelector(".graph-blocked");
  if (empty) empty.hidden = true;
  if (blocked) blocked.hidden = true;
  if (state === "empty") setupEmptyState();
  else setupExceptionalState(state);
  syncNavigatorAria();
};
