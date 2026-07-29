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
