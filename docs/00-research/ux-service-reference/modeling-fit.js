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
const saveButton = document.querySelector("[data-action='save-fit']");
const updateButton = document.querySelector("[data-action='update-candidates']");
const disclosure = document.querySelector("#candidate-parameters");
const blockedReason = document.querySelector("[data-blocked-reason]");
const graphCanvas = document.querySelector("[data-graph-canvas]");

const stateMessages = {
  calculating: "Calculating candidates… the exact source, fit inputs and previous graph remain in place.",
  "fit-error-with-rail-ribbon-and-graph-preserved": "Candidate calculation failed for Hockett–Sherby. The prior graph and fit inputs are preserved; Retry / Update candidates is available.",
};

const candidateParameters = {
  voce: [
    ["sigma_0_initial_yield_stress", "312 MPa", "lower 280 · upper 360"],
    ["sigma_sat_saturation_stress", "1,148 MPa", "lower 900 · upper 1,400"],
    ["delta_recovery_rate", "8.60", "lower 0.1 · upper 25"],
    ["fit_domain_start_end", "0.0001 → 0.1000", "plastic strain"],
  ],
  swift: [
    ["swift_strength_coefficient_K", "1,035 MPa", "lower 700 · upper 1,400"],
    ["swift_exponent_n", "0.235", "lower 0.08 · upper 0.45"],
    ["swift_prestrain_epsilon_0", "0.00608", "lower 0 · upper 0.02"],
    ["fit_domain_start_end", "0.0001 → 0.1000", "plastic strain"],
  ],
  "hockett-sherby": [
    ["initial_yield_stress_sigma_0", "312 MPa", "lower 280 · upper 360"],
    ["saturation_stress_sigma_sat", "1,260 MPa", "lower 900 · upper 1,450"],
    ["exponential_rate_beta", "5.80", "lower 0.2 · upper 20"],
    ["hardening_exponent_n", "0.750", "lower 0.2 · upper 1.2"],
  ],
  ghosh: [
    ["ghosh_coefficient_K", "420 MPa", "Altair 2025 formula contract"],
    ["ghosh_domain_epsilon_0", "0.800", "must exceed every evaluated plastic strain"],
    ["ghosh_delta_p_minus_n", "0.240", "only identifiable exponent combination"],
    ["ghosh_public_n_and_p", "not separate fit evidence", "structurally non-identifiable"],
  ],
  "blend-swift-voce": [
    ["Swift coefficient K", "1,035 MPa", "lower 700 · upper 1,400"],
    ["Swift exponent n", "0.235", "lower 0.08 · upper 0.45"],
    ["Voce saturation stress", "1,148 MPa", "lower 900 · upper 1,400"],
    ["Voce recovery rate", "8.60", "lower 0.1 · upper 25"],
    ["blend_primary_contribution", "50 %", "lower 0 · upper 100"],
    ["fit_domain_start_end", "0.0001 → 0.1000", "plastic strain"],
    ["extrapolation_target_strain", "1.00", "output points 101"],
  ],
};

// Deterministic, non-production public-law fixtures. This is a hardening response,
// not a total stress–total strain curve. Ghosh follows the Altair Material Modeler
// 2025 equation contract and is evaluated only while plastic strain < epsilon_0.
const INITIAL_YIELD_STRESS_MPA = 312;
const FULL_STRAIN_SAMPLES = [0, 0.005, 0.015, 0.03, 0.05, 0.075, 0.1, 0.14, 0.18, 0.24, 0.3, 0.36, 0.42];
const OBSERVED_STRAIN_SAMPLES = [0, 0.005, 0.015, 0.03, 0.05, 0.075, 0.1, 0.14, 0.18];
const voceStress = (strain) => INITIAL_YIELD_STRESS_MPA
  + (1148 - INITIAL_YIELD_STRESS_MPA) * (1 - Math.exp(-8.6 * strain));
const swiftPrestrain = Math.pow(INITIAL_YIELD_STRESS_MPA / 1035, 1 / 0.235);
const swiftStress = (strain) => 1035 * Math.pow(swiftPrestrain + strain, 0.235);
const hockettStress = (strain) => 1260
  - (1260 - INITIAL_YIELD_STRESS_MPA) * Math.exp(-5.8 * Math.pow(strain, 0.75));
const ghoshDomainEpsilon0 = 0.8;
const ghoshDeltaPMinusN = 0.24;
const ghoshStress = (strain) => 420
  * Math.pow(ghoshDomainEpsilon0 - strain, -ghoshDeltaPMinusN);
const blendStress = (strain) => (swiftStress(strain) + voceStress(strain)) / 2;
const observedOffsetsMpa = [0, 2, -3, 4, -2, 3, -4, 2, -1];
const sampleSeries = (strains, evaluator) => strains.map((strain) => [strain, Number(evaluator(strain).toFixed(3))]);
const PLOT_SERIES = {
  observed: OBSERVED_STRAIN_SAMPLES.map((strain, index) => [
    strain,
    Number((blendStress(strain) + observedOffsetsMpa[index]).toFixed(3)),
  ]),
  voce: sampleSeries(FULL_STRAIN_SAMPLES, voceStress),
  swift: sampleSeries(FULL_STRAIN_SAMPLES, swiftStress),
  "hockett-sherby": sampleSeries(FULL_STRAIN_SAMPLES, hockettStress),
  ghosh: sampleSeries(FULL_STRAIN_SAMPLES, ghoshStress),
  blend: sampleSeries(FULL_STRAIN_SAMPLES, blendStress),
};

let requestSequence = 0;
let selectedCandidate = null;
let currentState = "normal";

const setInteractionStatus = (message) => {
  if (interactionStatus) interactionStatus.textContent = message;
};

const setText = (selector, value) => {
  const element = document.querySelector(selector);
  if (element) element.textContent = value;
};

const setDisabled = (button, disabled, idleLabel = "") => {
  if (!button) return;
  if (disabled && idleLabel && !button.dataset.idleLabel) button.dataset.idleLabel = idleLabel;
  button.disabled = disabled;
  button.setAttribute("aria-disabled", String(disabled));
};

const isVisible = (element) => !!element && (element.checkVisibility
  ? element.checkVisibility({checkOpacity: false, checkVisibilityCSS: true})
  : !!(element.offsetWidth || element.offsetHeight));

function setCandidateDrawer(open) {
  if (!disclosure) return;
  disclosure.hidden = !open;
  document.querySelectorAll("[data-action='toggle-candidates']").forEach((control) => {
    control.setAttribute("aria-expanded", String(open));
    if (control.matches(".disclosure-trigger")) {
      const indicator = control.querySelector("span[aria-hidden='true']");
      if (indicator) indicator.textContent = open ? "▾" : "▸";
    }
  });
  setText("[data-candidate-disclosure-state]", open ? "Open · bounded parameter drawer" : "Closed · graph stays dominant");
  body.dataset.openDisclosure = open ? "Candidate parameters" : "closed";
}

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
  setText("[data-included-count]", `${count} / 3 included`);
  body.dataset.includedCurves = String(count);
}

function selectCurve(row) {
  curveRows.forEach((candidate) => {
    const selected = candidate === row;
    candidate.classList.toggle("selected", selected);
    candidate.querySelector(".curve-selection-button")?.setAttribute("aria-pressed", String(selected));
  });
  body.dataset.selectedCurve = row.dataset.curve || "curve";
  setInteractionStatus(`${row.dataset.curve} selected; exact Processing Output revision retained`);
}

function selectOperation(row) {
  operationRows.forEach((candidate) => {
    const selected = candidate === row;
    candidate.classList.toggle("selected", selected);
    candidate.setAttribute("aria-pressed", String(selected));
  });
  body.dataset.selectedStep = row.dataset.step || "4";
  setInteractionStatus(`${row.textContent.replace(/\s+/g, " ").trim()} selected; Fit graph remains mounted`);
}

function updateContribution() {
  const slider = document.querySelector("#primary-contribution");
  setText("[data-contribution]", `${slider?.value || 50}%`);
}

function candidateRow(id) {
  return document.querySelector(`.candidate-row[data-candidate='${id}']`);
}

function candidateLawLabel(id) {
  return candidateRow(id)?.querySelector("th strong")?.textContent.trim() || id;
}

function clearSelection() {
  selectedCandidate = null;
  body.dataset.selectedCandidate = "";
  document.querySelectorAll(".candidate-row").forEach((row) => {
    row.classList.remove("selected");
    row.removeAttribute("aria-selected");
    const button = row.querySelector(".candidate-select");
    if (button) {
      button.textContent = "Select";
      button.setAttribute("aria-label", `Select ${row.querySelector("th strong")?.textContent.trim() || "candidate"}`);
    }
  });
  const evidence = document.querySelector("[data-selection-evidence]");
  if (evidence) evidence.hidden = true;
  const reason = document.querySelector("[data-selection-reason]");
  const ack = document.querySelector("[data-warning-ack]");
  if (reason) reason.value = "";
  if (ack) ack.checked = false;
  if (!['stale', 'blocked', 'loading', 'error', 'empty'].includes(body.dataset.candidateState || '')) {
    setText('[data-status-selection]', 'No Fit candidate selected');
    setText('[data-status-job]', 'No active job');
  }
  refreshSaveGate();
}

function renderParameters(id) {
  const target = document.querySelector("[data-parameter-values]");
  if (!target) return;
  target.innerHTML = "";
  (candidateParameters[id] || []).forEach(([name, value, bounds]) => {
    const entry = document.createElement("div");
    entry.className = "parameter-entry";
    entry.innerHTML = `<span>${name}</span><strong>${value}</strong><small>${bounds}</small>`;
    target.append(entry);
  });
}

function selectCandidate(id, {seedDecision = false} = {}) {
  const row = candidateRow(id);
  if (!row || body.classList.contains("state-empty")) return;
  selectedCandidate = id;
  body.dataset.selectedCandidate = id;
  document.querySelectorAll(".candidate-row").forEach((candidate) => {
    const active = candidate === row;
    candidate.classList.toggle("selected", active);
    candidate.toggleAttribute("aria-selected", active);
    const button = candidate.querySelector(".candidate-select");
    if (button) {
      button.textContent = active ? "Selected" : "Select";
      button.setAttribute("aria-label", `${active ? "Selected" : "Select"} ${candidate.querySelector("th strong")?.textContent.trim() || "candidate"}`);
    }
  });
  const evidence = document.querySelector("[data-selection-evidence]");
  if (evidence) evidence.hidden = false;
  setText("[data-selection-title]", `Selected · ${candidateLawLabel(id)}`);
  setText("[data-selection-summary]", "Explicit engineer selection · recommendation remains separate evidence.");
  setText("[data-selection-state]", "Selected · draft");
  const warning = id === "blend-swift-voce" || id === "hockett-sherby" || id === "ghosh";
  const ack = document.querySelector("[data-warning-ack]");
  if (ack) {
    ack.checked = seedDecision && warning;
    ack.disabled = !warning;
  }
  setText("[data-warning-copy]", warning ? `Acknowledge: ${candidateRow(id)?.querySelector("td:nth-child(7)")?.textContent.trim() || "candidate warning"}` : "No additional warning acknowledgement required");
  setText("[data-selection-help]", warning ? "Save remains disabled until the reason and applicable warning acknowledgement are complete." : "Save remains disabled until a non-empty selection reason is recorded.");
  setText("[data-downstream-status]", `${candidateLawLabel(id)} explicitly selected for this draft; recommendation remains evidence and Export stays stale until Save fit & continue.`);
  setText("[data-status-selection]", `Fit · ${candidateLawLabel(id)} selected`);
  setText("[data-status-job]", "Fit candidate selected · decision draft");
  renderParameters(id);
  refreshSaveGate();
  setInteractionStatus(`${candidateLawLabel(id)} explicitly selected; recommendation is not auto-selected`);
}

function refreshSaveGate() {
  const reason = document.querySelector("[data-selection-reason]")?.value.trim() || "";
  const ack = document.querySelector("[data-warning-ack]");
  const warningRequired = !!selectedCandidate && ["blend-swift-voce", "hockett-sherby", "ghosh"].includes(selectedCandidate);
  const ready = currentState === "normal" || currentState === "candidate-parameters-long"
    ? !!selectedCandidate && body.dataset.candidateState !== "stale" && body.dataset.candidateState !== "loading" && body.dataset.candidateState !== "error" && reason.length > 0 && (!warningRequired || !!ack?.checked)
    : false;
  setDisabled(saveButton, !ready);
  if (ready) {
    setText("[data-save-reason]", "Reason and applicable warning acknowledgement complete · ready to save one immutable fit decision.");
  } else if (body.dataset.candidateState === "stale") {
    setText("[data-save-reason]", "Fit inputs changed; Update candidates, then explicitly select a candidate again.");
  } else if (!selectedCandidate) {
    setText("[data-save-reason]", "Choose one candidate, then record a reason before Save fit & continue.");
  } else if (!reason) {
    setText("[data-save-reason]", "Add a non-empty selection reason before Save fit & continue.");
  } else if (warningRequired && !ack?.checked) {
    setText("[data-save-reason]", "Acknowledge the selected candidate warning before Save fit & continue.");
  }
  setText("[data-selection-help]", ready
    ? "Reason and warning acknowledgement complete · ready to save one immutable fit decision."
    : warningRequired
      ? "Save remains disabled until the reason and applicable warning acknowledgement are complete."
      : "Save remains disabled until a non-empty selection reason is recorded.");
}

function markStale(message = "Fit input changed; Update candidates required") {
  if (body.classList.contains("state-empty")) return;
  selectedCandidate = null;
  body.dataset.candidateState = "stale";
  body.dataset.selectionInvalidated = "true";
  clearSelection();
  setText('[data-status-selection]', 'No Fit candidate selected');
  setText('[data-status-job]', 'Fit candidate stale · update required');
  setText("[data-ribbon-state]", "Preview stale · selection cleared");
  setText("[data-stage-status]", "Fit draft · candidates stale");
  setText("[data-candidate-status]", "Candidate computation stale · recommendation cleared");
  setText("[data-downstream-status]", "Fit options changed; current candidate and downstream pointers are stale until Update candidates succeeds.");
  setInteractionStatus(message);
  refreshSaveGate();
}

function finishCurrentCandidates() {
  body.dataset.candidateState = "current";
  body.dataset.selectionInvalidated = "false";
  setText("[data-ribbon-state]", "Preview · not saved");
  setText("[data-stage-status]", "Processing Output · exact revision saved · fit preview not saved");
  setText("[data-candidate-status]", "Recomputed candidates · recommendation is evidence only");
  setText("[data-downstream-status]", "Candidates current; Save fit & continue records an explicit engineer decision and immutable snapshot.");
  refreshSaveGate();
}

function setStateMessage(message, error = false) {
  const target = document.querySelector("p[data-state-message]");
  if (!target) return;
  target.hidden = !message;
  target.textContent = message;
  target.setAttribute("role", error ? "alert" : "status");
  body.dataset.stateMessageValue = message || "";
}

function setOverlay(message, state = "") {
  if (!graphCanvas) return;
  const overlay = graphCanvas.querySelector("[data-graph-state-overlay]");
  if (!overlay) return;
  overlay.hidden = !message;
  overlay.dataset.state = state;
  overlay.textContent = message;
}

function runUpdate({error = false, retainState = false} = {}) {
  if (!updateButton || updateButton.disabled || body.dataset.candidateBusy === "true") return;
  const request = ++requestSequence;
  body.dataset.candidateBusy = "true";
  body.dataset.candidateState = "loading";
  setDisabled(updateButton, true);
  updateButton.dataset.idleLabel = "Update candidates";
  updateButton.textContent = "Calculating…";
  setDisabled(saveButton, true);
  setText("[data-ribbon-state]", "Calculating… · graph retained");
  setText("[data-stage-status]", "Calculating… · source and graph retained");
  setText("[data-candidate-status]", "Calculating candidates from exact Processing Output…");
  setText("[data-downstream-status]", "Candidate computation in progress; prior graph and inputs remain mounted.");
  setOverlay("Calculating candidates… · prior graph and inputs retained", "loading");
  setStateMessage("Calculating candidates… local progress only; prior graph and inputs remain available.");
  setInteractionStatus("Calculating fit candidates…");
  window.setTimeout(() => {
    if (request !== requestSequence) return;
    body.dataset.candidateBusy = "false";
    setDisabled(updateButton, false);
    updateButton.textContent = "Update candidates";
    if (error) {
      body.dataset.candidateState = "error";
      body.classList.add("state-error");
      setText("[data-ribbon-state]", "Error · prior candidates retained");
      setText("[data-stage-status]", "Error · graph and inputs retained");
      setText("[data-candidate-status]", "Hockett–Sherby calculation failed · prior evidence retained");
      setText("[data-downstream-status]", "Retry / Update candidates after checking fit domain and selected equations.");
      setOverlay("Error · Hockett–Sherby failed · prior graph and inputs retained", "error");
      setStateMessage(stateMessages["fit-error-with-rail-ribbon-and-graph-preserved"], true);
      setInteractionStatus("Fit candidate calculation failed; retry is available");
      refreshSaveGate();
      return;
    }
    body.classList.remove("state-error", "state-loading");
    setOverlay("", "");
    setStateMessage("");
    finishCurrentCandidates();
    if (!retainState) body.dataset.referenceState = "normal";
    setInteractionStatus("Candidates updated; no candidate was auto-selected");
  }, 120);
}

function runSave() {
  if (!saveButton || saveButton.disabled || body.dataset.commitBusy === "true") return;
  const request = ++requestSequence;
  body.dataset.commitBusy = "true";
  body.dataset.commitCount = String(Number(body.dataset.commitCount || 0) + 1);
  setDisabled(saveButton, true);
  saveButton.dataset.idleLabel = "Save fit & continue";
  saveButton.textContent = "Saving…";
  setDisabled(updateButton, true);
  setText("[data-ribbon-state]", "Saving… · selection retained");
  setText("[data-stage-status]", "Saving… · fit decision not yet committed");
  setOverlay("Saving fit decision… · graph and selected evidence retained", "loading");
  setInteractionStatus("Saving explicit fit decision…");
  window.setTimeout(() => {
    if (request !== requestSequence) return;
    body.dataset.commitBusy = "false";
    setDisabled(updateButton, false);
    body.dataset.candidateState = "saved";
    saveButton.textContent = "Saved fit decision";
    setText("[data-ribbon-state]", "Saved · immutable fit decision");
    setText("[data-stage-status]", "Fit Decision · exact revision saved");
    setText("[data-downstream-status]", "Fit decision saved as an immutable revision; Export may now select this exact decision.");
    setText("[data-status-revision]", "Fit Decision · exact revision");
    setText("[data-status-job]", "No active job");
    setOverlay("", "");
    setInteractionStatus("Fit decision saved as one immutable revision");
  }, 120);
}

function setBlockedState() {
  body.classList.add("state-blocked");
  body.dataset.candidateState = "blocked";
  body.dataset.referenceState = "stale-or-no-selection-blocked";
  const targetStrain = document.querySelector("input[name='target_strain']");
  if (targetStrain) {
    targetStrain.value = "1.20";
    targetStrain.setAttribute("value", "1.20");
  }
  setText("[data-stage-status]", "Fit blocked · candidate selection required");
  setText("[data-ribbon-state]", "Blocked · no current selection");
  setText("[data-candidate-status]", "Recommendation visible · engineer selection absent");
  setText("[data-downstream-status]", "Changed target strain to 1.20 invalidated the fit decision; Update candidates is the safe recovery.");
  setText("[data-save-reason]", "Save disabled · recompute candidates and explicitly select a row after the changed intent.");
  setText("[data-status-warning]", "1 stale decision");
  setText("[data-status-job]", "Recovery available");
  setText("[data-status-selection]", "No Fit candidate selected");
  if (blockedReason) {
    blockedReason.hidden = false;
    blockedReason.innerHTML = "<strong>Selection blocked.</strong> Changed intent <code>Target strain 1.20</code> cleared the current candidate pointer. No recommendation is silently promoted; Update candidates and reselect explicitly.";
  }
  setDisabled(saveButton, true);
  setOverlay("Stale candidate selection · graph and source retained", "");
  setStateMessage("Changed intent: target strain 1.20. Recommendation is not selected; Update candidates is the safe recovery.");
  clearSelection();
}

function setEmptyState() {
  body.classList.add("state-empty");
  body.dataset.candidateState = "empty";
  body.dataset.referenceState = "no-candidate-empty";
  setText("[data-stage-status]", "Fit ready · no candidates calculated");
  setText("[data-ribbon-state]", "No candidates · preview unavailable");
  setText("[data-candidate-status]", "No candidate calculation has run");
  setText("[data-downstream-status]", "Exact Processing Output and Fit inputs remain mounted; Update candidates creates a preview only.");
  setText("[data-save-reason]", "Save disabled · update candidates, then explicitly choose a candidate and record a reason.");
  setText("[data-status-warning]", "Candidate calculation required");
  setText("[data-status-job]", "Ready to calculate");
  setDisabled(saveButton, true);
  setCandidateDrawer(false);
  const empty = document.querySelector("[data-graph-empty]");
  if (empty) empty.hidden = false;
  setOverlay("No candidate preview · exact source and graph context retained", "");
  setStateMessage("No candidate calculation yet. Update candidates is the only calculation action; no selection is implied.");
  clearSelection();
}

function setCalculatingState() {
  body.dataset.candidateState = "loading";
  body.dataset.referenceState = "calculating";
  body.classList.add("state-loading");
  setDisabled(updateButton, true);
  setDisabled(saveButton, true);
  setText("[data-ribbon-state]", "Calculating… · graph retained");
  setText("[data-stage-status]", "Calculating… · source and graph retained");
  setText("[data-candidate-status]", "Calculating candidates from exact Processing Output…");
  setText("[data-downstream-status]", "Candidate computation in progress; prior graph and inputs remain mounted.");
  setOverlay("Calculating candidates… · prior graph and inputs retained", "loading");
  setStateMessage(stateMessages.calculating);
  body.setAttribute("aria-busy", "true");
}

function setErrorState() {
  body.dataset.candidateState = "error";
  body.dataset.referenceState = "fit-error-with-rail-ribbon-and-graph-preserved";
  body.classList.add("state-error");
  setText("[data-ribbon-state]", "Error · prior candidates retained");
  setText("[data-stage-status]", "Error · graph and inputs retained");
  setText("[data-candidate-status]", "Hockett–Sherby calculation failed · prior evidence retained");
  setText("[data-downstream-status]", "Retry / Update candidates after checking fit domain and selected equations.");
  setOverlay("Error · Hockett–Sherby failed · prior graph and inputs retained", "error");
  setStateMessage(stateMessages["fit-error-with-rail-ribbon-and-graph-preserved"], true);
  setText("[data-status-job]", "Recovery available");
  setText("[data-status-warning]", "1 recoverable error");
  setDisabled(saveButton, true);
}

function setupState(state) {
  currentState = state;
  body.classList.remove("state-empty", "state-blocked", "state-loading", "state-error", "state-long");
  body.removeAttribute("aria-busy");
  setStateMessage("");
  if (blockedReason) blockedReason.hidden = true;
  const empty = document.querySelector("[data-graph-empty]");
  if (empty) empty.hidden = true;
  setOverlay("", "");
  setDisabled(updateButton, false);
  updateButton.textContent = "Update candidates";
  setText("[data-status-warning]", "0 warnings");
  if (state === "candidate-parameters-long") {
    body.classList.add("state-long");
    setCandidateDrawer(true);
    selectCandidate("blend-swift-voce", {seedDecision: true});
    const reason = document.querySelector("[data-selection-reason]");
    if (reason) reason.value = "The 50/50 Swift and Voce preview follows observed hardening while remaining stable through the target strain.";
    const ack = document.querySelector("[data-warning-ack]");
    if (ack) ack.checked = true;
    body.dataset.candidateState = "current";
    refreshSaveGate();
    setText("[data-candidate-disclosure-state]", "Open · bounded parameter drawer");
    return;
  }
  if (state === "no-candidate-empty") {
    setEmptyState();
    return;
  }
  if (state === "stale-or-no-selection-blocked") {
    setBlockedState();
    return;
  }
  if (state === "calculating") {
    setCalculatingState();
    return;
  }
  if (state === "fit-error-with-rail-ribbon-and-graph-preserved") {
    setErrorState();
    return;
  }
  body.dataset.referenceState = "normal";
  body.dataset.candidateState = "current";
  clearSelection();
  setCandidateDrawer(false);
  finishCurrentCandidates();
}

function syncNavigatorAria() {
  if (!navigatorPane || !navigatorResizer) return;
  const width = Math.round(navigatorPane.getBoundingClientRect().width);
  navigatorResizer.setAttribute("aria-valuenow", String(width));
  navigatorResizer.setAttribute("aria-expanded", String(width > 0));
  if (dividerButton) {
    dividerButton.setAttribute("aria-expanded", String(width > 0));
    dividerButton.setAttribute("aria-label", `${width > 0 ? "Collapse" : "Expand"} curve and fit navigator`);
    const span = dividerButton.querySelector("span");
    if (span) span.textContent = width > 0 ? "‹" : "›";
  }
  body.dataset.navigatorWidth = String(width);
}

function setNavigatorWidth(width, {collapsed = false} = {}) {
  const minimum = Number(navigatorResizer?.getAttribute("aria-valuemin") || 184);
  const maximum = Number(navigatorResizer?.getAttribute("aria-valuemax") || 260);
  if (collapsed) {
    body.classList.add("navigator-collapsed");
    root.style.setProperty("--modeling-navigator-width", "0px");
    navigatorResizer?.setAttribute("aria-valuenow", "0");
    navigatorResizer?.setAttribute("aria-expanded", "false");
    if (dividerButton) {
      dividerButton.setAttribute("aria-expanded", "false");
      dividerButton.setAttribute("aria-label", "Expand curve and fit navigator");
      dividerButton.querySelector("span")?.replaceChildren("›");
    }
    body.dataset.navigatorCollapsed = "true";
    setInteractionStatus("Curve and Fit navigator collapsed; graph retained");
    return;
  }
  const next = Math.max(minimum, Math.min(maximum, Math.round(width)));
  body.classList.remove("navigator-collapsed");
  root.style.setProperty("--modeling-navigator-width", `${next}px`);
  navigatorResizer?.setAttribute("aria-valuenow", String(next));
  navigatorResizer?.setAttribute("aria-expanded", "true");
  if (dividerButton) {
    dividerButton.setAttribute("aria-expanded", "true");
    dividerButton.setAttribute("aria-label", "Collapse curve and fit navigator");
    dividerButton.querySelector("span")?.replaceChildren("‹");
  }
  body.dataset.navigatorCollapsed = "false";
  body.dataset.navigatorWidth = String(next);
  setInteractionStatus(`Navigator width ${next}px; graph remains visible`);
}

dividerButton?.addEventListener("click", () => {
  const open = navigatorResizer?.getAttribute("aria-expanded") !== "false";
  if (open) {
    body.dataset.navigatorRestoredWidth = navigatorResizer?.getAttribute("aria-valuenow") || "192";
    setNavigatorWidth(0, {collapsed: true});
  } else {
    setNavigatorWidth(Number(body.dataset.navigatorRestoredWidth || 192));
  }
});

navigatorResizer?.addEventListener("keydown", (event) => {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  const minimum = Number(navigatorResizer.getAttribute("aria-valuemin") || 184);
  const maximum = Number(navigatorResizer.getAttribute("aria-valuemax") || 260);
  const current = Number(navigatorResizer.getAttribute("aria-valuenow") || 192);
  if (event.key === "Home") return setNavigatorWidth(minimum);
  if (event.key === "End") return setNavigatorWidth(maximum);
  setNavigatorWidth(current + (event.key === "ArrowRight" ? 8 : -8));
});

curveRows.forEach((row) => {
  row.querySelector(".curve-selection-button")?.addEventListener("click", () => selectCurve(row));
  row.querySelector("input[type='checkbox']")?.addEventListener("change", (event) => {
    updateIncludedCount();
    markStale(`${row.dataset.curve} inclusion ${event.currentTarget.checked ? "enabled" : "disabled"}; Update candidates required`);
  });
  row.querySelector(".curve-visibility-button")?.addEventListener("click", (event) => {
    const button = event.currentTarget;
    const visible = button.textContent.trim() !== "○";
    button.textContent = visible ? "○" : "◉";
    button.setAttribute("aria-label", `${visible ? "Show" : "Hide"} ${row.dataset.curve} from plot`);
    button.title = visible ? "Show on plot" : "Hide from plot";
    setInteractionStatus(`${row.dataset.curve} ${visible ? "hidden from" : "shown on"} plot; candidate state unchanged`);
  });
});

operationRows.forEach((row, index) => {
  row.addEventListener("click", () => selectOperation(row));
  row.addEventListener("keydown", (event) => {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === "Home" ? 0 : event.key === "End" ? operationRows.length - 1 : event.key === "ArrowDown" ? Math.min(operationRows.length - 1, index + 1) : Math.max(0, index - 1);
    operationRows[next].focus();
    selectOperation(operationRows[next]);
  });
});

document.querySelectorAll(".candidate-select").forEach((button) => button.addEventListener("click", () => selectCandidate(button.dataset.selectCandidate)));
document.querySelectorAll(".fit-controls input, .fit-controls select").forEach((control) => {
  control.addEventListener("input", () => { if (control.type === "range") updateContribution(); });
  control.addEventListener("change", () => markStale(`${control.getAttribute("aria-label") || control.name || "Fit option"} changed; Update candidates required`));
});
document.querySelector("[data-selection-reason]")?.addEventListener("input", refreshSaveGate);
document.querySelector("[data-warning-ack]")?.addEventListener("change", refreshSaveGate);
updateButton?.addEventListener("click", () => runUpdate());
saveButton?.addEventListener("click", runSave);
document.querySelectorAll("[data-action='toggle-candidates']").forEach((control) => control.addEventListener("click", () => {
  const open = disclosure?.hidden === true;
  setCandidateDrawer(open);
  setInteractionStatus(`Candidate parameters ${open ? "opened" : "closed"}; persistent graph remains mounted`);
}));
document.querySelector("[data-action='select-fit-range']")?.addEventListener("click", () => setInteractionStatus("Fit range selection armed; graph context preserved"));
document.querySelector("[data-action='pick-point']")?.addEventListener("click", () => setInteractionStatus("Graph point picker armed; candidate decision context preserved"));
document.querySelector("#advanced-top")?.addEventListener("click", () => {
  const details = document.querySelector("#evidence");
  if (details) details.open = !details.open;
  setInteractionStatus("Advanced / Evidence disclosure toggled");
});
document.querySelector(".candidate-parameters-body")?.addEventListener("keydown", (event) => {
  if (!['PageDown', 'PageUp', 'Home', 'End'].includes(event.key)) return;
  const drawerBody = event.currentTarget;
  event.preventDefault();
  if (event.key === 'Home') drawerBody.scrollTop = 0;
  else if (event.key === 'End') drawerBody.scrollTop = drawerBody.scrollHeight;
  else drawerBody.scrollBy({top: event.key === 'PageDown' ? drawerBody.clientHeight * .8 : -drawerBody.clientHeight * .8, behavior: 'instant'});
  setInteractionStatus(`Candidate parameter drawer ${event.key} scroll applied locally`);
});
document.querySelectorAll("details").forEach((details) => details.addEventListener("toggle", () => {
  body.dataset.openDisclosure = details.open ? (details.querySelector("summary")?.textContent.trim() || "open") : "closed";
}));
document.querySelectorAll(".stage-button").forEach((stage) => stage.addEventListener("click", () => {
  setStage(stage.dataset.stage || "Fit");
  setInteractionStatus(`${stage.dataset.stage} stage selected; Fit graph retained`);
}));
document.querySelector("#curve-filter")?.addEventListener("input", (event) => {
  const query = String(event.currentTarget.value || "").toLocaleLowerCase();
  curveRows.forEach((row) => { row.hidden = query.length > 0 && !row.textContent.toLocaleLowerCase().includes(query); });
});
graphControls.forEach((control) => control.addEventListener("click", () => {
  graphControls.forEach((candidate) => {
    const active = candidate === control;
    candidate.classList.toggle("active", active);
    candidate.setAttribute("aria-pressed", String(active));
  });
  body.dataset.graphView = control.dataset.graphView || "response";
  setInteractionStatus(`Graph view ${body.dataset.graphView} selected; candidate selection and context preserved`);
}));

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";
const createSvgNode = (name, attributes = {}, text = "") => {
  const node = document.createElementNS(SVG_NAMESPACE, name);
  Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
  if (text) node.textContent = text;
  return node;
};

const niceStep = (span, targetIntervals) => {
  const raw = span / Math.max(1, targetIntervals);
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const normalized = raw / magnitude;
  const factor = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 2.5 ? 2.5 : normalized <= 5 ? 5 : 10;
  return factor * magnitude;
};

const derivePlotDomain = (points, ratio) => {
  const minimumStrain = Math.min(...points.map(([strain]) => strain));
  const maximumStrain = Math.max(...points.map(([strain]) => strain));
  const minimumStress = Math.min(...points.map(([, stress]) => stress));
  const maximumStress = Math.max(...points.map(([, stress]) => stress));
  const strainSpan = maximumStrain - minimumStrain;
  const stressSpan = maximumStress - minimumStress;
  const computedMinimumStrain = Math.max(0, minimumStrain - strainSpan * ratio);
  const computedMaximumStrain = maximumStrain + strainSpan * ratio;
  const computedMinimumStress = Math.max(0, minimumStress - stressSpan * ratio);
  const computedMaximumStress = maximumStress + stressSpan * ratio;
  const strainStep = niceStep(computedMaximumStrain - computedMinimumStrain, 5);
  const stressStep = niceStep(computedMaximumStress - computedMinimumStress, 6);
  return {
    minimumStrain,
    maximumStrain,
    minimumStress,
    maximumStress,
    computedMinimumStrain,
    computedMaximumStrain,
    computedMinimumStress,
    computedMaximumStress,
    niceMinimumStrain: Math.max(0, Math.floor(computedMinimumStrain / strainStep) * strainStep),
    niceMaximumStrain: Math.ceil(computedMaximumStrain / strainStep) * strainStep,
    niceMinimumStress: Math.floor(computedMinimumStress / stressStep) * stressStep,
    niceMaximumStress: Math.ceil(computedMaximumStress / stressStep) * stressStep,
    strainStep,
    stressStep,
  };
};

const tickValues = (minimum, maximum, step) => {
  const count = Math.round((maximum - minimum) / step);
  return Array.from({ length: count + 1 }, (_, index) => Number((minimum + index * step).toPrecision(12)));
};

const seriesClass = {
  observed: "observed-curve",
  voce: "voce-curve",
  swift: "swift-curve",
  "hockett-sherby": "hockett-curve",
  ghosh: "ghosh-curve",
  blend: "preview-blend-curve",
};

const stressFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
let plotRenderFrame = 0;

const rectangleIntersects = (a, b) => (
  a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top
);

const segmentTouchesRectangle = (start, end, rectangle) => {
  const steps = Math.max(1, Math.ceil(Math.max(Math.abs(end.x - start.x), Math.abs(end.y - start.y)) / 6));
  for (let index = 0; index <= steps; index += 1) {
    const ratio = index / steps;
    const x = start.x + (end.x - start.x) * ratio;
    const y = start.y + (end.y - start.y) * ratio;
    if (x >= rectangle.left && x <= rectangle.right && y >= rectangle.top && y <= rectangle.bottom) return true;
  }
  return false;
};

function placePlotLegend({plot, plotStage, plotLeft, plotRight, plotTop, plotBottom, mapX, mapY, observedBoundaryX}) {
  const legend = plotStage.querySelector(".plot-legend");
  const layout = plotStage.closest(".plot-layout");
  if (!legend || !layout) return;
  if (layout.dataset.legendPlacement === "docked" && legend.parentElement === layout) {
    legend.dataset.placement = "docked";
    plot.dataset.legendPlacement = "docked";
    plot.dataset.legendCollisionCount = "0";
    plot.dataset.legendFallback = "true";
    return;
  }

  legend.dataset.placement = "pending";
  const width = legend.offsetWidth;
  const height = legend.offsetHeight;
  const inset = 10;
  const candidates = [
    ["lower-right", plotRight - width - inset, plotBottom - height - inset],
    ["lower-left", plotLeft + inset, plotBottom - height - inset],
    ["upper-right", plotRight - width - inset, plotTop + inset],
    ["upper-left", plotLeft + inset, plotTop + inset],
  ].filter(([, left, top]) => left >= plotLeft + 1 && top >= plotTop + 1);

  const stageBounds = plotStage.getBoundingClientRect();
  const overlays = [...plotStage.querySelectorAll(".graph-state-overlay,.graph-empty")]
    .filter((node) => !node.hidden && getComputedStyle(node).display !== "none")
    .map((node) => {
      const bounds = node.getBoundingClientRect();
      return {
        left: bounds.left - stageBounds.left,
        right: bounds.right - stageBounds.left,
        top: bounds.top - stageBounds.top,
        bottom: bounds.bottom - stageBounds.top,
      };
    });

  const scored = candidates.map(([placement, left, top]) => {
    const rectangle = {
      left: left - 7,
      right: left + width + 7,
      top: top - 7,
      bottom: top + height + 7,
    };
    let collisions = overlays.filter((overlay) => rectangleIntersects(rectangle, overlay)).length;
    if (observedBoundaryX >= rectangle.left && observedBoundaryX <= rectangle.right) collisions += 1;
    Object.values(PLOT_SERIES).forEach((values) => {
      const mapped = values.map(([strain, stress]) => ({x: mapX(strain), y: mapY(stress)}));
      if (mapped.some((point, index) => index > 0 && segmentTouchesRectangle(mapped[index - 1], point, rectangle))) collisions += 1;
    });
    return {placement, left, top, collisions};
  }).sort((first, second) => first.collisions - second.collisions);

  const selected = scored[0];
  if (!selected || selected.collisions > 0) {
    layout.dataset.legendPlacement = "docked";
    layout.append(legend);
    legend.dataset.placement = "docked";
    plot.dataset.legendPlacement = "docked";
    plot.dataset.legendCollisionCount = String(selected?.collisions || 0);
    plot.dataset.legendFallback = "true";
    return;
  }

  layout.dataset.legendPlacement = selected.placement;
  legend.style.left = `${Math.round(selected.left)}px`;
  legend.style.top = `${Math.round(selected.top)}px`;
  legend.dataset.placement = selected.placement;
  plot.dataset.legendPlacement = selected.placement;
  plot.dataset.legendCollisionCount = String(selected.collisions);
  plot.dataset.legendFallback = "false";
}

function renderEngineeringPlot() {
  const plot = document.querySelector(".engineering-plot");
  const plotRoot = plot?.querySelector("[data-plot-root]");
  const plotStage = plot?.closest(".plot-stage");
  if (!plot || !plotRoot || !plotStage) return;
  const stageBounds = plotStage.getBoundingClientRect();
  const width = Math.round(stageBounds.width);
  const height = Math.round(stageBounds.height);
  if (width < 320 || height < 160) return;

  const points = Object.values(PLOT_SERIES).flat();
  const ratio = Number(plot.dataset.axisHeadroomRatio || 0.1);
  const finite = [...points.flat(), ratio, width, height].every(Number.isFinite);
  if (!finite) return;
  const domain = derivePlotDomain(points, ratio);
  if (domain.maximumStrain <= domain.minimumStrain || domain.maximumStress <= domain.minimumStress) return;

  const alteredPoints = [
    ...points,
    [domain.maximumStrain * 1.15, domain.maximumStress * 1.15],
  ];
  const alteredDomain = derivePlotDomain(alteredPoints, ratio);
  const compact = height < 260;
  const margin = {
    left: 58,
    right: 12,
    top: compact ? 15 : 18,
    bottom: compact ? 34 : 38,
  };
  const plotLeft = margin.left;
  const plotRight = width - margin.right;
  const plotTop = margin.top;
  const plotBottom = height - margin.bottom;
  const plotWidth = plotRight - plotLeft;
  const plotHeight = plotBottom - plotTop;
  const xSpan = domain.niceMaximumStrain - domain.niceMinimumStrain;
  const ySpan = domain.niceMaximumStress - domain.niceMinimumStress;
  const mapX = (strain) => plotLeft + ((strain - domain.niceMinimumStrain) / xSpan) * plotWidth;
  const mapY = (stress) => plotBottom - ((stress - domain.niceMinimumStress) / ySpan) * plotHeight;
  const xTicks = tickValues(domain.niceMinimumStrain, domain.niceMaximumStrain, domain.strainStep);
  const yTicks = tickValues(domain.niceMinimumStress, domain.niceMaximumStress, domain.stressStep);
  const observedMaximumStrain = Math.max(...PLOT_SERIES.observed.map(([strain]) => strain));
  const observedBoundaryX = mapX(observedMaximumStrain);

  plot.setAttribute("viewBox", `0 0 ${width} ${height}`);
  plot.removeAttribute("preserveAspectRatio");
  plotRoot.replaceChildren();
  plotRoot.append(
    createSvgNode("rect", {
      class: "plot-background",
      x: plotLeft,
      y: plotTop,
      width: plotWidth,
      height: plotHeight,
      "data-plot-box": "true",
    }),
    createSvgNode("rect", {
      class: "extrapolation-zone",
      x: observedBoundaryX,
      y: plotTop,
      width: Math.max(0, plotRight - observedBoundaryX),
      height: plotHeight,
    }),
  );

  const grid = createSvgNode("g", { class: "plot-grid", "aria-hidden": "true" });
  xTicks.forEach((tick) => grid.append(createSvgNode("line", {
    x1: mapX(tick),
    y1: plotTop,
    x2: mapX(tick),
    y2: plotBottom,
  })));
  yTicks.forEach((tick) => grid.append(createSvgNode("line", {
    x1: plotLeft,
    y1: mapY(tick),
    x2: plotRight,
    y2: mapY(tick),
  })));
  plotRoot.append(
    grid,
    createSvgNode("path", {
      class: "plot-axis",
      d: `M${plotLeft} ${plotTop}V${plotBottom}H${plotRight}`,
    }),
    createSvgNode("path", {
      class: "observed-boundary",
      d: `M${observedBoundaryX} ${plotTop}V${plotBottom}`,
    }),
    createSvgNode("text", {
      class: "extrapolation-label",
      x: observedBoundaryX + (plotRight - observedBoundaryX) / 2,
      y: plotTop + 15,
      "text-anchor": "middle",
      "data-plot-label": "extrapolated",
    }, "EXTRAPOLATED · UNOBSERVED"),
  );

  Object.entries(PLOT_SERIES).forEach(([key, values]) => {
    plotRoot.append(createSvgNode("polyline", {
      class: `curve ${seriesClass[key]}`,
      "data-series-key": key,
      "data-start-strain": values[0][0],
      "data-start-stress-mpa": values[0][1],
      points: values.map(([strain, stress]) => `${mapX(strain).toFixed(2)},${mapY(stress).toFixed(2)}`).join(" "),
    }));
  });

  const labels = createSvgNode("g", { class: "plot-labels" });
  xTicks.forEach((tick, index) => labels.append(createSvgNode("text", {
    x: mapX(tick),
    y: plotBottom + 15,
    "text-anchor": index === 0 ? "start" : index === xTicks.length - 1 ? "end" : "middle",
    "data-plot-label": `x-${index}`,
  }, tick === 0 ? "0" : tick.toFixed(2))));
  yTicks.forEach((tick, index) => labels.append(createSvgNode("text", {
    x: plotLeft - 7,
    y: mapY(tick) + 4,
    "text-anchor": "end",
    "data-plot-label": `y-${index}`,
  }, stressFormatter.format(tick))));
  labels.append(
    createSvgNode("text", {
      class: "axis-title",
      transform: `translate(13 ${(plotTop + plotBottom) / 2}) rotate(-90)`,
      "text-anchor": "middle",
      "data-plot-label": "axis-title",
    }, "True yield stress (MPa)"),
    createSvgNode("text", {
      class: "axis-title",
      x: (plotLeft + plotRight) / 2,
      y: height - 4,
      "text-anchor": "middle",
      "data-plot-label": "x-axis-title",
      "data-plot-x-axis-title": "true",
    }, "True plastic strain [1]"),
  );
  plotRoot.append(labels);
  placePlotLegend({
    plot,
    plotStage,
    plotLeft,
    plotRight,
    plotTop,
    plotBottom,
    mapX,
    mapY,
    observedBoundaryX,
  });

  plot.dataset.seriesMinStrain = domain.minimumStrain.toFixed(6);
  plot.dataset.seriesMaxStrain = domain.maximumStrain.toFixed(6);
  plot.dataset.seriesMinStressMpa = domain.minimumStress.toFixed(3);
  plot.dataset.seriesMaxStressMpa = domain.maximumStress.toFixed(3);
  plot.dataset.axisComputedMinStrain = domain.computedMinimumStrain.toFixed(6);
  plot.dataset.axisComputedMaxStrain = domain.computedMaximumStrain.toFixed(6);
  plot.dataset.axisComputedMinStressMpa = domain.computedMinimumStress.toFixed(3);
  plot.dataset.axisComputedMaxStressMpa = domain.computedMaximumStress.toFixed(3);
  plot.dataset.axisNiceMinStrain = domain.niceMinimumStrain.toFixed(2);
  plot.dataset.axisNiceMaxStrain = domain.niceMaximumStrain.toFixed(2);
  plot.dataset.axisNiceMinStressMpa = domain.niceMinimumStress.toFixed(0);
  plot.dataset.axisNiceMaxStressMpa = domain.niceMaximumStress.toFixed(0);
  plot.dataset.axisAlteredMaxStrain = alteredDomain.computedMaximumStrain.toFixed(6);
  plot.dataset.axisAlteredMaxStressMpa = alteredDomain.computedMaximumStress.toFixed(3);
  plot.dataset.axisAlteredProof = String(
    alteredDomain.niceMaximumStrain > domain.niceMaximumStrain
    && alteredDomain.niceMaximumStress > domain.niceMaximumStress,
  );
  plot.dataset.axisDerivation = "finite-plotted-span-plus-proportional-padding";
  plot.dataset.initialYieldStressMpa = INITIAL_YIELD_STRESS_MPA.toFixed(3);
  plot.dataset.zeroPlasticStressPositive = String(
    Object.values(PLOT_SERIES).every((values) => values[0][0] === 0 && values[0][1] > 0),
  );
  plot.dataset.xQuantity = "true_plastic_strain";
  plot.dataset.xUnit = "1";
  plot.dataset.yQuantity = "true_yield_stress";
  plot.dataset.yUnit = "MPa";
  plot.dataset.renderedWidth = String(width);
  plot.dataset.renderedHeight = String(height);
  plot.dataset.plotLeft = plotLeft.toFixed(2);
  plot.dataset.plotRight = plotRight.toFixed(2);
  plot.dataset.plotTop = plotTop.toFixed(2);
  plot.dataset.plotBottom = plotBottom.toFixed(2);
  plot.dataset.nonUniformScale = "false";
  body.dataset.axisDerivation = "data-relative";
  body.dataset.axisAlteredExtremaProof = plot.dataset.axisAlteredProof === "true" ? "pass" : "fail";
  body.dataset.plotDataFinite = "true";
  body.dataset.plotNiceDomain = `${domain.niceMinimumStrain.toFixed(2)}:${domain.niceMaximumStrain.toFixed(2)}x${domain.niceMinimumStress.toFixed(0)}:${domain.niceMaximumStress.toFixed(0)}`;
}

const schedulePlotRender = () => {
  cancelAnimationFrame(plotRenderFrame);
  plotRenderFrame = requestAnimationFrame(renderEngineeringPlot);
};

syncNavigatorAria();
updateIncludedCount();
updateContribution();
const queryState = new URLSearchParams(window.location.search).get("state");
const pathState = window.location.pathname.includes("candidate-parameters-long") ? "candidate-parameters-long" : null;
setupState(queryState || pathState || body.dataset.referenceState || "normal");
schedulePlotRender();

const plotStage = document.querySelector(".plot-stage");
if (plotStage && "ResizeObserver" in window) {
  new ResizeObserver(schedulePlotRender).observe(plotStage);
}
window.addEventListener("resize", schedulePlotRender);

window.setModelingFitReferenceState = (state) => {
  setupState(state);
  syncNavigatorAria();
  schedulePlotRender();
};

window.deriveModelingFitAxisBounds = renderEngineeringPlot;
