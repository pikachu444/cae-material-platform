const root = document.documentElement;
const body = document.body;
const interactionStatus = document.querySelector("#interaction-status");
const navigatorPane = document.querySelector("[data-region='navigator']");
const navigatorDivider = document.querySelector("[data-region='navigator-divider']");
const navigatorResizer = navigatorDivider?.querySelector(".modeling-divider-resizer");
const dividerButton = navigatorDivider?.querySelector("button");
const curveRows = [...document.querySelectorAll(".curve-row")];
const operationRows = [...document.querySelectorAll(".operation-row")];
const graphControls = [...document.querySelectorAll(".graph-control")];
const previewButtons = [...document.querySelectorAll("[data-action='preview-top']")];
const saveButton = document.querySelector("[data-action='save']");
const blockedReason = document.querySelector("[data-blocked-reason]");
const graphCanvas = document.querySelector(".graph-canvas");
const graphPlot = document.querySelector(".source-plot");
const graphLegend = document.querySelector(".plot-legend");
const SVG_NS = "http://www.w3.org/2000/svg";
const PLOT_MARGIN = {left: 78, right: 24, top: 24, bottom: 54};
const PLOT_NICE_FACTORS = [1, 2, 2.5, 5, 10];
const PROCESS_STRAIN = [0, 0.005, 0.01, 0.02, 0.04, 0.07, 0.1, 0.14, 0.17, 0.188];
const PROCESS_SERIES = [
  {className: "observed-one", values: [0, 155, 288, 432, 560, 660, 725, 780, 820, 842]},
  {className: "observed-two", values: [0, 148, 278, 420, 550, 651, 717, 773, 814, 836]},
  {className: "observed-three", values: [0, 141, 268, 407, 536, 638, 705, 762, 803, 829]},
];
const PROCESSED_SERIES = {className: "processed-preview", values: [0, 152, 282, 430, 558, 658, 728, 785, 817, 840]};
const ELASTIC_FIT = {startStrain: 0.0002, endStrain: 0.002, slopeMpa: 209600};
const stateMessages = {
  "preview-loading": "Calculating preview… Test Data and current settings stay available.",
  "commit-loading": "Saving processing result… Current preview and draft settings stay available.",
  "preview-error": "Preview failed. Test Data and draft settings stay available; retry Preview changes.",
  "commit-error": "Save failed. No processing result was saved. Current preview and save reason stay available; retry Save processed curves.",
};

let requestSequence = 0;
let commitCount = 0;
let lastPlotSize = null;

function svgElement(name, attributes = {}) {
  const element = document.createElementNS(SVG_NS, name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
  return element;
}

function niceAxis(observedMaximum, targetIntervals, headroomRatio) {
  const desired = Math.max(observedMaximum, 1e-9) * (1 + headroomRatio);
  const rawStep = desired / targetIntervals;
  const exponent = 10 ** Math.floor(Math.log10(rawStep));
  const normalized = rawStep / exponent;
  const factor = PLOT_NICE_FACTORS.find((candidate) => candidate >= normalized) || 10;
  const step = factor * exponent;
  return {
    maximum: Math.max(step, Math.ceil((desired - Number.EPSILON) / step) * step),
    step,
    desired,
  };
}

function axisTicks(minimum, maximum, step) {
  const count = Math.max(1, Math.round((maximum - minimum) / step));
  return Array.from({length: count + 1}, (_, index) => minimum + step * index);
}

function formatStrain(value) {
  if (Math.abs(value) < 1e-9) return "0";
  return value.toFixed(value < 0.1 ? 2 : 2).replace(/0+$/, "").replace(/\.$/, "");
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
    const controlOne = {x: current.x + (next.x - previous.x) / 6, y: current.y + (next.y - previous.y) / 6};
    const controlTwo = {x: next.x - (afterNext.x - current.x) / 6, y: next.y - (afterNext.y - current.y) / 6};
    path += ` C ${controlOne.x.toFixed(2)} ${controlOne.y.toFixed(2)}, ${controlTwo.x.toFixed(2)} ${controlTwo.y.toFixed(2)}, ${next.x.toFixed(2)} ${next.y.toFixed(2)}`;
  }
  return path;
}

function intersects(left, right, padding = 0) {
  return left.left - padding < right.right
    && left.right + padding > right.left
    && left.top - padding < right.bottom
    && left.bottom + padding > right.top;
}

function placePlotLegend(plotGeometry) {
  if (!graphLegend || !graphCanvas || !graphPlot || body.classList.contains("state-blocked")) return;
  graphLegend.style.display = "flex";
  graphLegend.style.left = "12px";
  graphLegend.style.top = "12px";
  graphLegend.style.right = "auto";
  graphLegend.style.bottom = "auto";
  const canvasRect = graphCanvas.getBoundingClientRect();
  const legendRect = graphLegend.getBoundingClientRect();
  const width = legendRect.width;
  const height = legendRect.height;
  const plot = {
    left: plotGeometry.left,
    right: plotGeometry.right,
    top: plotGeometry.top,
    bottom: plotGeometry.bottom,
  };
  const curveRects = plotGeometry.curveRects || [...graphPlot.querySelectorAll(".curve")].map((path) => {
    const rect = path.getBoundingClientRect();
    return {left: rect.left - canvasRect.left, right: rect.right - canvasRect.left, top: rect.top - canvasRect.top, bottom: rect.bottom - canvasRect.top};
  });
  const candidates = [
    {name: "lower-right", left: plot.right - width - 12, top: plot.bottom - height - 12},
    {name: "upper-left", left: plot.left + 12, top: plot.top + 12},
    {name: "upper-right", left: plot.right - width - 12, top: plot.top + 12},
    {name: "lower-left", left: plot.left + 12, top: plot.bottom - height - 12},
    {name: "docked-right", left: Math.max(8, canvasRect.width - width - 12), top: Math.max(8, (canvasRect.height - height) / 2)},
  ];
  const safe = candidates.find((candidate) => {
    const box = {left: candidate.left, right: candidate.left + width, top: candidate.top, bottom: candidate.top + height};
    const inside = box.left >= plot.left + 4 && box.right <= plot.right - 4 && box.top >= plot.top + 4 && box.bottom <= plot.bottom - 4;
    return inside && !curveRects.some((curve) => intersects(box, curve, 3));
  }) || candidates[candidates.length - 1];
  graphLegend.style.left = `${Math.round(safe.left * 100) / 100}px`;
  graphLegend.style.top = `${Math.round(safe.top * 100) / 100}px`;
  graphLegend.dataset.placement = safe.name;
  graphLegend.dataset.curveCollision = String(curveRects.some((curve) => intersects({left: safe.left, right: safe.left + width, top: safe.top, bottom: safe.top + height}, curve, 3)));
  graphLegend.dataset.plotContained = String(safe.left >= plot.left + 4 && safe.left + width <= plot.right - 4 && safe.top >= plot.top + 4 && safe.top + height <= plot.bottom - 4);
}

function renderResponsivePlot(force = false) {
  if (!graphCanvas || !graphPlot) return;
  const rectangle = graphCanvas.getBoundingClientRect();
  const width = Math.max(1, Math.round(rectangle.width * 100) / 100);
  const height = Math.max(1, Math.round(rectangle.height * 100) / 100);
  if (!force && lastPlotSize && Math.abs(lastPlotSize.width - width) < 0.25 && Math.abs(lastPlotSize.height - height) < 0.25) return;
  lastPlotSize = {width, height};
  graphPlot.setAttribute("viewBox", `0 0 ${width.toFixed(2)} ${height.toFixed(2)}`);
  graphPlot.setAttribute("width", width.toFixed(2));
  graphPlot.setAttribute("height", height.toFixed(2));
  graphPlot.dataset.renderWidth = width.toFixed(2);
  graphPlot.dataset.renderHeight = height.toFixed(2);

  const observedValues = PROCESS_SERIES.flatMap((series) => series.values);
  const allValues = [...observedValues, ...PROCESSED_SERIES.values, 0, ELASTIC_FIT.startStrain * ELASTIC_FIT.slopeMpa, ELASTIC_FIT.endStrain * ELASTIC_FIT.slopeMpa];
  const observedMinStrain = Math.min(...PROCESS_STRAIN);
  const observedMaxStrain = Math.max(...PROCESS_STRAIN);
  const observedMinStress = Math.min(...observedValues);
  const observedMaxStress = Math.max(...observedValues);
  const xAxis = niceAxis(observedMaxStrain, Number(graphPlot.dataset.axisTargetIntervalsStrain || 5), Number(graphPlot.dataset.axisHeadroomRatio || 0.1));
  const yAxis = niceAxis(observedMaxStress, Number(graphPlot.dataset.axisTargetIntervalsStress || 4), Number(graphPlot.dataset.axisHeadroomRatio || 0.1));
  const xMin = observedMinStrain >= 0 ? 0 : observedMinStrain;
  const yMin = observedMinStress >= 0 ? 0 : observedMinStress;
  const xTicks = axisTicks(xMin, xAxis.maximum, xAxis.step);
  const yTicks = axisTicks(yMin, yAxis.maximum, yAxis.step);
  const plotLeft = PLOT_MARGIN.left;
  const plotRight = Math.max(plotLeft + 1, width - PLOT_MARGIN.right);
  const plotTop = PLOT_MARGIN.top;
  const plotBottom = Math.max(plotTop + 1, height - PLOT_MARGIN.bottom);
  const plotWidth = plotRight - plotLeft;
  const plotHeight = plotBottom - plotTop;
  const toX = (value) => plotLeft + ((value - xMin) / (xAxis.maximum - xMin || 1)) * plotWidth;
  const toY = (value) => plotBottom - ((value - yMin) / (yAxis.maximum - yMin || 1)) * plotHeight;
  const finite = [observedMinStrain, observedMaxStrain, observedMinStress, observedMaxStress, ...allValues].every(Number.isFinite);
  if (!finite) return;

  graphPlot.dataset.seriesMinStrain = String(observedMinStrain);
  graphPlot.dataset.seriesMaxStrain = String(observedMaxStrain);
  graphPlot.dataset.seriesMinStressMpa = String(observedMinStress);
  graphPlot.dataset.seriesMaxStressMpa = String(observedMaxStress);
  graphPlot.dataset.axisMinStrain = String(xMin);
  graphPlot.dataset.axisMaxStrain = String(xAxis.maximum);
  graphPlot.dataset.axisMinStressMpa = String(yMin);
  graphPlot.dataset.axisMaxStressMpa = String(yAxis.maximum);
  graphPlot.dataset.axisComputedMaxStrain = xAxis.maximum.toFixed(6);
  graphPlot.dataset.axisComputedMaxStressMpa = yAxis.maximum.toFixed(3);
  graphPlot.dataset.axisNiceStepStrain = String(xAxis.step);
  graphPlot.dataset.axisNiceStepStressMpa = String(yAxis.step);
  graphPlot.dataset.axisTicksStrain = JSON.stringify(xTicks);
  graphPlot.dataset.axisTicksStressMpa = JSON.stringify(yTicks);
  graphPlot.dataset.axisDerivation = "finite-plotted-span-plus-proportional-headroom";
  graphPlot.dataset.sourceStrain = JSON.stringify(PROCESS_STRAIN);
  graphPlot.dataset.observedSeries = JSON.stringify(PROCESS_SERIES.map((series) => series.values));
  graphPlot.dataset.processedSeries = JSON.stringify(PROCESSED_SERIES.values);
  graphPlot.dataset.elasticFit = JSON.stringify([ELASTIC_FIT.startStrain, ELASTIC_FIT.endStrain]);
  graphPlot.dataset.plotLeft = String(plotLeft);
  graphPlot.dataset.plotRight = String(plotRight);
  graphPlot.dataset.plotTop = String(plotTop);
  graphPlot.dataset.plotBottom = String(plotBottom);
  graphPlot.dataset.pointFrameClearances = JSON.stringify({
    left: toX(observedMinStrain) - plotLeft,
    right: plotRight - toX(observedMaxStrain),
    top: toY(observedMaxStress) - plotTop,
    bottom: plotBottom - toY(observedMinStress),
  });

  const background = graphPlot.querySelector(".plot-background");
  background?.setAttribute("x", String(plotLeft));
  background?.setAttribute("y", String(plotTop));
  background?.setAttribute("width", String(plotWidth));
  background?.setAttribute("height", String(plotHeight));
  const blockedBackdrop = graphPlot.querySelector(".plot-blocked-backdrop");
  blockedBackdrop?.setAttribute("x", String(plotLeft));
  blockedBackdrop?.setAttribute("y", String(plotTop));
  blockedBackdrop?.setAttribute("width", String(plotWidth));
  blockedBackdrop?.setAttribute("height", String(plotHeight));
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
  PROCESS_SERIES.forEach((series) => {
    const path = graphPlot.querySelector(`.${series.className}`);
    if (!path) return;
    const points = PROCESS_STRAIN.map((strain, index) => ({x: toX(strain), y: toY(series.values[index])}));
    path.setAttribute("d", smoothPath(points));
    path.setAttribute("vector-effect", "non-scaling-stroke");
  });
  const processedPath = graphPlot.querySelector(`.${PROCESSED_SERIES.className}`);
  if (processedPath) {
    processedPath.setAttribute("d", smoothPath(PROCESS_STRAIN.map((strain, index) => ({x: toX(strain), y: toY(PROCESSED_SERIES.values[index])}))));
    processedPath.setAttribute("vector-effect", "non-scaling-stroke");
  }
  const fitPath = graphPlot.querySelector(".elastic-fit");
  if (fitPath) {
    fitPath.setAttribute("d", `M ${toX(ELASTIC_FIT.startStrain).toFixed(2)} ${toY(ELASTIC_FIT.startStrain * ELASTIC_FIT.slopeMpa).toFixed(2)} L ${toX(ELASTIC_FIT.endStrain).toFixed(2)} ${toY(ELASTIC_FIT.endStrain * ELASTIC_FIT.slopeMpa).toFixed(2)}`);
    fitPath.setAttribute("vector-effect", "non-scaling-stroke");
  }
  const xTitle = svgElement("text", {class: "axis-title", x: (plotLeft + plotRight) / 2, y: height - 10, "text-anchor": "middle"});
  xTitle.textContent = "Engineering strain [1]";
  labels?.append(xTitle);
  const yTitle = svgElement("text", {class: "axis-title", transform: `translate(18 ${(plotTop + plotBottom) / 2}) rotate(-90)`, "text-anchor": "middle"});
  yTitle.textContent = "Engineering stress (MPa)";
  labels?.append(yTitle);
  body.dataset.axisDerivation = "data-relative";
  const curveRects = [];
  PROCESS_SERIES.forEach((series) => PROCESS_STRAIN.forEach((strain, index) => {
    const x = toX(strain); const y = toY(series.values[index]);
    curveRects.push({left: x - 5, right: x + 5, top: y - 5, bottom: y + 5});
  }));
  PROCESS_STRAIN.forEach((strain, index) => {
    const x = toX(strain); const y = toY(PROCESSED_SERIES.values[index]);
    curveRects.push({left: x - 5, right: x + 5, top: y - 5, bottom: y + 5});
  });
  for (let index = 0; index <= 8; index += 1) {
    const strain = ELASTIC_FIT.startStrain + (ELASTIC_FIT.endStrain - ELASTIC_FIT.startStrain) * index / 8;
    const x = toX(strain); const y = toY(strain * ELASTIC_FIT.slopeMpa);
    curveRects.push({left: x - 5, right: x + 5, top: y - 5, bottom: y + 5});
  }
  placePlotLegend({left: plotLeft, right: plotRight, top: plotTop, bottom: plotBottom, curveRects});
}

function startResponsivePlot() {
  renderResponsivePlot(true);
  if (typeof ResizeObserver !== "undefined") {
    const observer = new ResizeObserver(() => renderResponsivePlot());
    if (graphCanvas) observer.observe(graphCanvas);
    if (navigatorPane) observer.observe(navigatorPane);
  }
  window.addEventListener("resize", () => renderResponsivePlot(true));
  window.renderModelingProcessPlot = () => renderResponsivePlot(true);
}

const setInteractionStatus = (message) => {
  if (interactionStatus) interactionStatus.textContent = message;
};
const setText = (selector, value) => {
  const element = document.querySelector(selector);
  if (element) element.textContent = value;
};
const isVisible = (element) => !!element && element.checkVisibility({checkOpacity: false, checkVisibilityCSS: true});

function setStage(stage) {
  document.querySelectorAll(".stage-button").forEach((candidate) => {
    const active = candidate.dataset.stage === stage;
    candidate.classList.toggle("active", active);
    candidate.toggleAttribute("aria-current", active);
  });
  body.dataset.activeStage = stage;
}

function updateIncludedCount() {
  const count = curveRows.filter((row) => row.querySelector("input[type='checkbox']")?.checked).length;
  setText("[data-included-count]", `3 curves · ${count} included`);
  body.dataset.includedCurves = String(count);
}

function selectCurve(row) {
  curveRows.forEach((candidate) => {
    const selected = candidate === row;
    candidate.classList.toggle("selected", selected);
    candidate.querySelector(".curve-selection-button")?.setAttribute("aria-pressed", String(selected));
  });
  body.dataset.selectedCurve = row.dataset.curve || "curve";
  setInteractionStatus(`${row.dataset.curve} selected; saved Test Data retained`);
}

function operationLabel(step) {
  const labels = {
    "1": "Resolve duplicate x values",
    "2": "Elastic modulus",
    "3": "Offset proof stress",
    "4": "Necking boundary",
    "5": "Engineering → true / plastic",
  };
  return labels[step] || "Processing operation";
}

function selectOperation(row, {stale = false} = {}) {
  operationRows.forEach((candidate) => {
    const selected = candidate === row;
    candidate.classList.toggle("selected", selected);
    candidate.setAttribute("aria-pressed", String(selected));
  });
  const step = row.dataset.step || "2";
  const label = operationLabel(step);
  setText("#process-settings-title", `Step ${step} · ${label}`);
  setText("[data-graph-context]", `Saved Test Data · Revision 1 · ${label} preview`);
  body.dataset.selectedStep = step;
  if (stale) markDraftStale(`${label} selected; Preview changes required`);
  else setInteractionStatus(`${label} selected; source and graph remain mounted`);
}

function markDraftStale(message = "Draft changed; Preview changes required") {
  body.dataset.previewState = "stale";
  body.dataset.downstreamPointers = "stale";
  setText("[data-ribbon-state]", "Preview stale · not saved");
  setText("[data-stage-status]", "Process draft · preview stale");
  setText("[data-downstream-status]", "Fit and Export remain unchanged until the processing result is saved.");
  setInteractionStatus(message);
}

function markPreviewCurrent() {
  body.dataset.previewState = "current";
  body.dataset.downstreamPointers = "stale";
  setText("[data-ribbon-state]", "Preview · not saved");
  setText("[data-stage-status]", "Saved Test Data · Revision 1 · preview not saved");
  setText("[data-downstream-status]", "Fit and Export remain unchanged until the processing result is saved.");
  setText("[data-legend-note]", "Preview · not saved · raw/source recoverable");
}

function setButtonBusy(button, busy, label) {
  if (!button) return;
  button.disabled = busy;
  button.setAttribute("aria-disabled", String(busy));
  if (busy) button.dataset.idleLabel = button.textContent;
  button.textContent = busy ? label : (button.dataset.idleLabel || button.textContent);
}

function ensureStateMessage(message, isError) {
  let element = document.querySelector(".state-message");
  if (!element) {
    element = document.createElement("p");
    element.className = "state-message";
    const ribbon = document.querySelector(".process-ribbon");
    ribbon?.insertBefore(element, ribbon.querySelector(".downstream-status"));
  }
  element.textContent = message;
  element.setAttribute("role", isError ? "alert" : "status");
  body.dataset.stateMessage = message;
}

function clearStateMessage() {
  document.querySelector(".state-message")?.remove();
  delete body.dataset.stateMessage;
}

function runPreview({error = false} = {}) {
  if (body.classList.contains("state-blocked") || body.dataset.previewBusy === "true") return;
  const request = ++requestSequence;
  body.dataset.previewBusy = "true";
  body.dataset.previewState = "loading";
  previewButtons.forEach((button) => setButtonBusy(button, true, "Calculating…"));
  setButtonBusy(saveButton, true, "Save processed curves");
  setText("[data-ribbon-state]", "");
  setText("[data-stage-status]", "Calculating preview…");
  const canvas = document.querySelector(".graph-canvas");
  if (canvas) canvas.dataset.stateOverlay = "";
  setInteractionStatus("Calculating preview…");
  window.setTimeout(() => {
    if (request !== requestSequence) return;
    body.dataset.previewBusy = "false";
    previewButtons.forEach((button) => setButtonBusy(button, false));
    if (error) {
      body.dataset.previewState = "error";
      body.classList.add("state-error");
      ensureStateMessage(stateMessages["preview-error"], true);
      if (canvas) canvas.dataset.stateOverlay = "";
      setText("[data-ribbon-state]", "");
      setText("[data-stage-status]", "Preview failed");
      setInteractionStatus("Preview failed; retry is available");
      setButtonBusy(saveButton, true, "Save processed curves");
    } else {
      body.classList.remove("state-error", "state-loading");
      clearStateMessage();
      if (canvas) canvas.dataset.stateOverlay = "";
      markPreviewCurrent();
      setButtonBusy(saveButton, false);
      setInteractionStatus("Preview current; Save processed curves is ready");
    }
  }, 90);
}

function runCommit({error = false} = {}) {
  if (body.classList.contains("state-blocked") || body.dataset.commitBusy === "true" || !saveButton || saveButton.disabled) return;
  const request = ++requestSequence;
  body.dataset.commitBusy = "true";
  body.dataset.commitCount = String(++commitCount);
  body.dataset.previewState = "saving";
  setButtonBusy(saveButton, true, "Saving…");
  previewButtons.forEach((button) => setButtonBusy(button, true, "Preview changes"));
  setText("[data-ribbon-state]", "");
  setText("[data-stage-status]", "Saving processing result…");
  const canvas = document.querySelector(".graph-canvas");
  if (canvas) canvas.dataset.stateOverlay = "";
  setInteractionStatus("Saving processed curves…");
  window.setTimeout(() => {
    if (request !== requestSequence) return;
    body.dataset.commitBusy = "false";
    previewButtons.forEach((button) => setButtonBusy(button, false));
    if (error) {
      body.classList.add("state-error");
      ensureStateMessage(stateMessages["commit-error"], true);
      setText("[data-ribbon-state]", "");
      setText("[data-stage-status]", "Save failed");
      if (canvas) canvas.dataset.stateOverlay = "";
      setButtonBusy(saveButton, false);
      setInteractionStatus("Save failed; retry is available and no output was registered");
      return;
    }
    body.classList.remove("state-error", "state-loading");
    clearStateMessage();
    body.dataset.previewState = "saved";
    setText("[data-ribbon-state]", "Processing result saved");
    setText("[data-stage-status]", "Processing result saved");
    setText("[data-downstream-status]", "Processing result saved; Fit and Export can now use it.");
    setText("[data-status-revision]", "Processing result saved");
    setText("[data-status-job]", "No active calculation");
    if (canvas) canvas.dataset.stateOverlay = "";
    setButtonBusy(saveButton, true, "Saved processed curves");
    saveButton.setAttribute("aria-disabled", "true");
    setInteractionStatus("Processing Output saved as one immutable revision");
  }, 100);
}

function setBlockedState() {
  body.classList.add("state-blocked");
  body.dataset.referenceState = "prerequisite-blocked";
  body.dataset.previewState = "blocked";
  setText("[data-included-count]", "0 compatible curves");
  setText("[data-curve-count]", "No compatible revision");
  setText("[data-status-selection]", "No compatible Test Data");
  setText("[data-status-revision]", "Saved Test Data required");
  setText("[data-status-job]", "Calculation blocked");
  setText("[data-status-warning]", "1 unmet prerequisite");
  setText("[data-stage-status]", "Process blocked · compatible source required");
  setText("[data-ribbon-state]", "Blocked · preview unavailable");
  setText("[data-source-revision]", "No compatible saved Test Data selected");
  setText("[data-preview-result]", "Unavailable · source required");
  setText("[data-downstream-status]", "Processing requires compatible saved Test Data.");
  setText("[data-graph-context]", "No compatible source · preview unavailable");
  setText("[data-legend-note]", "No current preview · source context retained");
  if (blockedReason) {
    blockedReason.hidden = false;
    blockedReason.dataset.exactTestData = "CMP-DEMO-DP780-TEST-JSON-03";
    blockedReason.dataset.noFallback = "true";
    blockedReason.innerHTML = "<strong>Processing blocked.</strong> Compatible saved Test Data is required.";
  }
  operationRows.forEach((row) => {
    row.disabled = true;
    row.setAttribute("aria-disabled", "true");
  });
  previewButtons.forEach((button) => setButtonBusy(button, true, "Preview changes"));
  setButtonBusy(saveButton, true, "Save processed curves");
  const graphBlocked = document.querySelector(".graph-blocked");
  if (graphBlocked) graphBlocked.hidden = false;
  const copy = document.querySelector("[data-blocked-graph-copy]");
  if (copy) copy.textContent = "Return to Data and choose compatible saved Test Data before processing.";
  setInteractionStatus("Processing blocked; compatible saved Test Data is required");
}

function setupState(state) {
  body.classList.remove("state-blocked", "state-loading", "state-error");
  clearStateMessage();
  const graphBlocked = document.querySelector(".graph-blocked");
  if (graphBlocked) graphBlocked.hidden = true;
  operationRows.forEach((row) => { row.disabled = false; row.removeAttribute("aria-disabled"); });
  previewButtons.forEach((button) => setButtonBusy(button, false));
  if (saveButton) { saveButton.disabled = false; saveButton.removeAttribute("aria-disabled"); saveButton.textContent = "Save processed curves"; }
  if (state === "prerequisite-blocked" || state === "blocked") {
    setBlockedState();
    return;
  }
  if (stateMessages[state]) {
    const isError = state.endsWith("error");
    body.classList.add(isError ? "state-error" : "state-loading");
    body.dataset.referenceState = state;
    ensureStateMessage(stateMessages[state], isError);
    const isPreview = state.startsWith("preview");
    setText("[data-status-job]", isError ? "Recovery available" : "Calculation in progress");
    setText("[data-status-warning]", isError ? (isPreview ? "Preview failed" : "Save failed") : "Test Data available");
    setText("[data-stage-status]", isError ? (isPreview ? "Preview failed" : "Save failed") : (isPreview ? "Calculating preview…" : "Saving processing result…"));
    setText("[data-ribbon-state]", "");
    const canvas = document.querySelector(".graph-canvas");
    if (canvas) canvas.dataset.stateOverlay = "";
    if (state === "preview-loading") {
      previewButtons.forEach((button) => setButtonBusy(button, true, "Preview changes"));
      setButtonBusy(saveButton, true, "Save processed curves");
    }
    if (state === "commit-loading") {
      previewButtons.forEach((button) => setButtonBusy(button, true, "Preview changes"));
      setButtonBusy(saveButton, true, "Saving…");
    }
    if (state === "preview-error") setButtonBusy(saveButton, true, "Save processed curves");
    setInteractionStatus(stateMessages[state]);
    return;
  }
  body.dataset.referenceState = "normal";
  markPreviewCurrent();
}

function syncNavigatorAria() {
  if (!navigatorPane || !navigatorDivider) return;
  const width = Math.round(navigatorPane.getBoundingClientRect().width);
  navigatorResizer?.setAttribute("aria-valuenow", String(width));
  navigatorResizer?.setAttribute("aria-expanded", String(width > 0));
  updateDividerLabel(width > 0);
  body.dataset.navigatorWidth = String(width);
}
function updateDividerLabel(open) {
  if (!dividerButton) return;
  dividerButton.setAttribute("aria-expanded", String(open));
  dividerButton.setAttribute("aria-label", `${open ? "Collapse" : "Expand"} curve and process navigator`);
  const span = dividerButton.querySelector("span");
  if (span) span.textContent = open ? "‹" : "›";
}
function setNavigatorWidth(width, {collapsed = false} = {}) {
  const minimum = Number(navigatorResizer?.getAttribute("aria-valuemin") || 180);
  const maximum = Number(navigatorResizer?.getAttribute("aria-valuemax") || 240);
  if (collapsed) {
    body.classList.add("navigator-collapsed");
    root.style.setProperty("--modeling-navigator-width", "0px");
    navigatorResizer?.setAttribute("aria-valuenow", "0");
    navigatorResizer?.setAttribute("aria-expanded", "false");
    updateDividerLabel(false);
    body.dataset.navigatorCollapsed = "true";
    renderResponsivePlot(true);
    setInteractionStatus("Curve and process navigator collapsed; graph retained");
    return;
  }
  const next = Math.max(minimum, Math.min(maximum, Math.round(width)));
  body.classList.remove("navigator-collapsed");
  root.style.setProperty("--modeling-navigator-width", `${next}px`);
  navigatorResizer?.setAttribute("aria-valuenow", String(next));
  navigatorResizer?.setAttribute("aria-expanded", "true");
  updateDividerLabel(true);
  body.dataset.navigatorCollapsed = "false";
  body.dataset.navigatorWidth = String(next);
  renderResponsivePlot(true);
  setInteractionStatus(`Navigator width ${next}px; graph remains visible`);
}
dividerButton?.addEventListener("click", () => {
  const open = navigatorResizer?.getAttribute("aria-expanded") !== "false";
  if (open) {
    const current = Number(navigatorResizer?.getAttribute("aria-valuenow") || 192);
    body.dataset.navigatorRestoredWidth = String(current);
    setNavigatorWidth(current, {collapsed: true});
  } else {
    const restored = Number(body.dataset.navigatorRestoredWidth || 192);
    setNavigatorWidth(restored);
  }
});
navigatorResizer?.addEventListener("keydown", (event) => {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  const minimum = Number(navigatorResizer.getAttribute("aria-valuemin") || 180);
  const maximum = Number(navigatorResizer.getAttribute("aria-valuemax") || 240);
  const current = Number(navigatorResizer.getAttribute("aria-valuenow") || 192);
  if (event.key === "Home") return setNavigatorWidth(minimum);
  if (event.key === "End") return setNavigatorWidth(maximum);
  setNavigatorWidth(current + (event.key === "ArrowRight" ? 8 : -8));
});

curveRows.forEach((row) => {
  row.querySelector(".curve-selection-button")?.addEventListener("click", () => {
    selectCurve(row);
  });
  row.querySelector("input[type='checkbox']")?.addEventListener("change", () => {
    updateIncludedCount();
    markDraftStale(`${row.dataset.curve} inclusion ${row.querySelector("input")?.checked ? "enabled" : "disabled"}; Preview changes required`);
  });
  row.querySelector(".curve-visibility-button")?.addEventListener("click", (event) => {
    const button = event.currentTarget;
    const visible = button.textContent.trim() !== "○";
    button.textContent = visible ? "○" : "◉";
    button.setAttribute("aria-label", `${visible ? "Show" : "Hide"} ${row.dataset.curve} on plot`);
    button.title = visible ? "Show on plot" : "Hide from plot";
    body.dataset.plotVisibility = `${row.dataset.curve}:${!visible}`;
    setInteractionStatus(`${row.dataset.curve} ${visible ? "hidden from" : "shown on"} plot; processing state unchanged`);
  });
});
operationRows.forEach((row, index) => {
  row.addEventListener("click", () => selectOperation(row, {stale: row.dataset.step !== "2"}));
  row.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp" && event.key !== "Home" && event.key !== "End") return;
    event.preventDefault();
    const next = event.key === "Home" ? 0 : event.key === "End" ? operationRows.length - 1 : event.key === "ArrowDown" ? Math.min(operationRows.length - 1, index + 1) : Math.max(0, index - 1);
    operationRows[next].focus();
    selectOperation(operationRows[next], {stale: operationRows[next].dataset.step !== "2"});
  });
});
previewButtons.forEach((button) => button.addEventListener("click", () => runPreview()));
saveButton?.addEventListener("click", () => runCommit());
document.querySelector("[data-action='back-data']")?.addEventListener("click", () => {
  setStage("Data");
  body.dataset.recoveryAction = "back-to-data";
  setInteractionStatus("Back to Data selected; Material, family and session context preserved");
});
document.querySelector("#advanced-top")?.addEventListener("click", () => {
  const details = document.querySelector("#evidence");
  if (details) details.open = !details.open;
  body.dataset.advancedRequested = "true";
  setInteractionStatus("Advanced / Evidence disclosure toggled");
});
document.querySelectorAll("details").forEach((details) => {
  details.addEventListener("toggle", () => {
    body.dataset.openDisclosure = details.open ? (details.querySelector("summary")?.textContent.trim() || "open") : "closed";
  });
});
graphControls.forEach((control) => {
  control.addEventListener("click", () => {
    graphControls.forEach((candidate) => {
      const active = candidate === control;
      candidate.classList.toggle("active", active);
      candidate.setAttribute("aria-pressed", String(active));
    });
    body.dataset.graphView = control.dataset.graphView || "response";
    setInteractionStatus(`Graph view ${body.dataset.graphView} selected; processing state unchanged`);
  });
});
document.querySelectorAll(".stage-button").forEach((stage) => {
  stage.addEventListener("click", () => {
    setStage(stage.dataset.stage || "Process");
    setInteractionStatus(`${stage.dataset.stage} stage selected; persistent graph retained`);
  });
});
document.querySelector("#curve-filter")?.addEventListener("input", (event) => {
  const query = String(event.currentTarget.value || "").toLocaleLowerCase();
  curveRows.forEach((row) => {
    row.hidden = query.length > 0 && !row.textContent.toLocaleLowerCase().includes(query);
  });
});
document.querySelectorAll(".setting input, .setting select").forEach((control) => {
  control.addEventListener("change", () => markDraftStale(`${control.getAttribute("aria-label") || control.name} changed; Preview changes required`));
});
syncNavigatorAria();
const queryState = new URLSearchParams(window.location.search).get("state");
const pathState = window.location.pathname.includes("prerequisite-blocked") ? "prerequisite-blocked" : null;
setupState(queryState || pathState || body.dataset.referenceState || "normal");
startResponsivePlot();

window.setModelingProcessReferenceState = (state) => {
  body.classList.remove("state-blocked", "state-loading", "state-error");
  clearStateMessage();
  setupState(state);
  syncNavigatorAria();
  renderResponsivePlot(true);
};
