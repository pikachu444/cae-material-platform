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
const stateMessages = {
  "preview-loading": "Calculating preview… the exact source, operation settings and previous graph remain in place.",
  "commit-loading": "Saving processed curves… the current preview and draft settings remain in place until the immutable output succeeds.",
  "preview-error": "Preview failed. The source, curve membership and draft settings are preserved; retry Preview changes.",
  "commit-error": "Save failed. No Processing Output revision was registered; the current preview and save reason remain available for retry.",
};

let requestSequence = 0;
let commitCount = 0;

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
  setInteractionStatus(`${row.dataset.curve} selected; exact source revision retained`);
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
  setText("[data-graph-context]", `CMP-DEMO-DP780-TEST-JSON-03 · r1 · ${label} preview`);
  body.dataset.selectedStep = step;
  if (stale) markDraftStale(`${label} selected; Preview changes required`);
  else setInteractionStatus(`${label} selected; source and graph remain mounted`);
}

function markDraftStale(message = "Draft changed; Preview changes required") {
  body.dataset.previewState = "stale";
  body.dataset.downstreamPointers = "stale";
  setText("[data-ribbon-state]", "Preview stale · not saved");
  setText("[data-stage-status]", "Process draft · preview stale");
  setText("[data-downstream-status]", "Fit / Export current pointers are stale until this preview is refreshed and saved; immutable prior revisions remain available.");
  setInteractionStatus(message);
}

function markPreviewCurrent() {
  body.dataset.previewState = "current";
  body.dataset.downstreamPointers = "stale";
  setText("[data-ribbon-state]", "Preview · not saved");
  setText("[data-stage-status]", "Test Data · exact revision saved · preview not saved");
  setText("[data-downstream-status]", "Preview current; Save processed curves creates one immutable Processing Output. Fit / Export pointers remain stale until commit.");
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
  setText("[data-ribbon-state]", "Calculating… · preview retained");
  setText("[data-stage-status]", "Calculating… · source and graph retained");
  const canvas = document.querySelector(".graph-canvas");
  if (canvas) canvas.dataset.stateOverlay = "Calculating… · context preserved";
  setInteractionStatus("Calculating preview…");
  window.setTimeout(() => {
    if (request !== requestSequence) return;
    body.dataset.previewBusy = "false";
    previewButtons.forEach((button) => setButtonBusy(button, false));
    if (error) {
      body.dataset.previewState = "error";
      body.classList.add("state-error");
      ensureStateMessage(stateMessages["preview-error"], true);
      if (canvas) canvas.dataset.stateOverlay = "Error · context preserved";
      setText("[data-ribbon-state]", "Error · preview retained");
      setText("[data-stage-status]", "Error · source and graph retained");
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
  setText("[data-ribbon-state]", "Saving… · preview retained");
  setText("[data-stage-status]", "Saving… · output not yet saved");
  const canvas = document.querySelector(".graph-canvas");
  if (canvas) canvas.dataset.stateOverlay = "Saving… · context preserved";
  setInteractionStatus("Saving processed curves…");
  window.setTimeout(() => {
    if (request !== requestSequence) return;
    body.dataset.commitBusy = "false";
    previewButtons.forEach((button) => setButtonBusy(button, false));
    if (error) {
      body.classList.add("state-error");
      ensureStateMessage(stateMessages["commit-error"], true);
      setText("[data-ribbon-state]", "Error · preview retained");
      setText("[data-stage-status]", "Error · preview retained");
      if (canvas) canvas.dataset.stateOverlay = "Error · context preserved";
      setButtonBusy(saveButton, false);
      setInteractionStatus("Save failed; retry is available and no output was registered");
      return;
    }
    body.classList.remove("state-error", "state-loading");
    clearStateMessage();
    body.dataset.previewState = "saved";
    setText("[data-ribbon-state]", "Saved · immutable output");
    setText("[data-stage-status]", "Processing Output · exact revision saved");
    setText("[data-downstream-status]", "Processing Output saved as an immutable revision; later Fit / Export may now select this exact output.");
    setText("[data-status-revision]", "Processing Output · exact revision");
    setText("[data-status-job]", "No active job");
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
  setText("[data-status-revision]", "Mapping Profile · missing");
  setText("[data-status-job]", "Preview blocked");
  setText("[data-status-warning]", "1 unmet prerequisite");
  setText("[data-stage-status]", "Process blocked · compatible source required");
  setText("[data-ribbon-state]", "Blocked · preview unavailable");
  setText("[data-source-revision]", "Expected exact revision · CMP-DEMO-DP780-TEST-JSON-03 · r1 + Mapping Profile");
  setText("[data-preview-result]", "Unavailable · source required");
  setText("[data-downstream-status]", "No compatible saved curves; choose the exact Test Data and Mapping Profile in Data before processing.");
  setText("[data-graph-context]", "No compatible source · preview unavailable");
  setText("[data-legend-note]", "No current preview · source context retained");
  if (blockedReason) {
    blockedReason.hidden = false;
    blockedReason.innerHTML = "<strong>Prerequisite blocked.</strong> Missing exact saved Test Data revision <code>CMP-DEMO-DP780-TEST-JSON-03 · r1</code> and compatible Mapping Profile. No first/latest fallback is selected.";
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
  if (copy) copy.textContent = "The exact saved Test Data and compatible Mapping Profile are absent. Return to Data to choose them; no processed result is fabricated.";
  setInteractionStatus("Processing blocked; exact Test Data and Mapping Profile are required");
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
    setText("[data-status-job]", isError ? "Recovery available" : "Job in progress");
    setText("[data-status-warning]", isError ? "1 recoverable error" : "Source retained");
    setText("[data-stage-status]", isError ? "Error · source and graph retained" : "Loading… · source and graph retained");
    setText("[data-ribbon-state]", isError ? "Error · preview retained" : "Loading… · preview retained");
    const canvas = document.querySelector(".graph-canvas");
    if (canvas) canvas.dataset.stateOverlay = isError ? "Error · context preserved" : "Loading… · context preserved";
    if (state === "preview-loading" || state === "preview-error") setButtonBusy(saveButton, true, "Save processed curves");
    if (state === "commit-loading") setButtonBusy(saveButton, true, "Saving…");
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
function deriveAxisBounds() {
  const plot = document.querySelector(".source-plot");
  if (!plot) return;
  const minStrain = Number(plot.dataset.seriesMinStrain);
  const maxStrain = Number(plot.dataset.seriesMaxStrain);
  const minStress = Number(plot.dataset.seriesMinStressMpa);
  const maxStress = Number(plot.dataset.seriesMaxStressMpa);
  const ratio = Number(plot.dataset.axisHeadroomRatio || .1);
  const finite = [minStrain, maxStrain, minStress, maxStress, ratio].every(Number.isFinite);
  if (!finite || maxStrain <= minStrain || maxStress <= minStress) return;
  const strainSpan = maxStrain - minStrain;
  const stressSpan = maxStress - minStress;
  const derivedMaxStrain = maxStrain + Math.max(strainSpan * ratio, Math.abs(maxStrain) * .03);
  const derivedMaxStress = maxStress + Math.max(stressSpan * ratio, Math.abs(maxStress) * .03);
  plot.dataset.axisComputedMaxStrain = derivedMaxStrain.toFixed(6);
  plot.dataset.axisComputedMaxStressMpa = derivedMaxStress.toFixed(3);
  plot.dataset.axisDerivation = "finite-plotted-span-plus-proportional-headroom";
  body.dataset.axisDerivation = "data-relative";
}
deriveAxisBounds();
syncNavigatorAria();
const queryState = new URLSearchParams(window.location.search).get("state");
const pathState = window.location.pathname.includes("prerequisite-blocked") ? "prerequisite-blocked" : null;
setupState(queryState || pathState || body.dataset.referenceState || "normal");

window.setModelingProcessReferenceState = (state) => {
  body.classList.remove("state-blocked", "state-loading", "state-error");
  clearStateMessage();
  setupState(state);
  syncNavigatorAria();
};
