const root = document.documentElement;
const body = document.body;
const status = document.querySelector("#interaction-status");
const treeSearch = document.querySelector("#tree-search-form");
const treeQuery = document.querySelector("#tree-query");
const materialTree = document.querySelector("#material-tree");
const treeRows = [...document.querySelectorAll("#material-tree [role='treeitem']")];
const navigatorPane = document.querySelector("[data-region='navigator']");
const navigatorDivider = document.querySelector("[data-region='navigator-divider']");
const tabList = document.querySelector("[role='tablist']");
const tabButtons = [...document.querySelectorAll("[role='tab']")];
const downloadButton = document.querySelector("#download-card");
const acknowledgement = document.querySelector("#approximation-ack");
const previewScroll = document.querySelector("#preview-scroll");
const nativeText = document.querySelector("#native-text");
const previewLoading = document.querySelector("#preview-loading");
const previewError = document.querySelector("#preview-error");
const previewUnavailable = document.querySelector("#preview-unavailable");
const approximationRow = document.querySelector("#approximation-row");
const unsupportedRow = document.querySelector("#unsupported-row");
const compactMappingRows = [...document.querySelectorAll("#mapping-list .mapping-row")].filter((row) => row !== approximationRow && row !== unsupportedRow).slice(1);

const setStatus = (message) => {
  if (status) status.textContent = message;
};

const focusTreeRow = (row) => {
  if (!row) return;
  treeRows.forEach((candidate) => { candidate.tabIndex = candidate === row ? 0 : -1; });
  row.focus();
};

const selectTreeRow = (row) => {
  if (!row) return;
  treeRows.forEach((candidate) => {
    const selected = candidate === row;
    candidate.classList.toggle("selected", selected);
    candidate.setAttribute("aria-selected", String(selected));
  });
  body.dataset.selectedTreeId = row.id;
  setStatus(`${row.dataset.kind ?? "Record"} ${row.querySelector(".tree-label")?.textContent.trim() ?? "selected"} selected`);
};

document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLocaleLowerCase() === "k") {
    event.preventDefault();
    treeQuery?.focus();
    treeQuery?.select();
    body.dataset.navigatorSearchFocused = "true";
    setStatus("Navigator search focused");
  }
});

treeSearch?.addEventListener("submit", (event) => {
  event.preventDefault();
  const query = treeQuery?.value.trim() ?? "";
  body.dataset.treeSearchConsequence = query.toLocaleLowerCase() === "dp780" ? "DP780-REF" : query;
  setStatus(`Tree search applied: ${query || "all records"}; ancestors retained`);
});

materialTree?.addEventListener("keydown", (event) => {
  const currentIndex = treeRows.indexOf(document.activeElement);
  if (currentIndex < 0) return;
  let nextRow = null;
  if (event.key === "ArrowDown") nextRow = treeRows[Math.min(treeRows.length - 1, currentIndex + 1)];
  if (event.key === "ArrowUp") nextRow = treeRows[Math.max(0, currentIndex - 1)];
  if (event.key === "Home") nextRow = treeRows[0];
  if (event.key === "End") nextRow = treeRows.at(-1);
  if (event.key === "Enter") {
    event.preventDefault();
    selectTreeRow(treeRows[currentIndex]);
    return;
  }
  if (nextRow) {
    event.preventDefault();
    focusTreeRow(nextRow);
  }
});

treeRows.forEach((row) => row.addEventListener("click", () => { focusTreeRow(row); selectTreeRow(row); }));

const syncNavigatorAria = () => {
  if (!navigatorPane || !navigatorDivider) return;
  navigatorDivider.setAttribute("aria-valuenow", String(Math.round(navigatorPane.getBoundingClientRect().width)));
};

const setNavigatorBounds = () => {
  const width = window.innerWidth;
  const max = width === 1366 ? 345 : 360;
  navigatorDivider?.setAttribute("aria-valuemin", "200");
  navigatorDivider?.setAttribute("aria-valuemax", String(max));
  if (width === 1366) root.style.setProperty("--navigator-width", "244px");
  else if (width >= 1700) root.style.setProperty("--navigator-width", "280px");
  else root.style.setProperty("--navigator-width", "264px");
  syncNavigatorAria();
};

setNavigatorBounds();
window.addEventListener("resize", setNavigatorBounds);

navigatorDivider?.addEventListener("keydown", (event) => {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  const minimum = Number(navigatorDivider.getAttribute("aria-valuemin"));
  const maximum = Number(navigatorDivider.getAttribute("aria-valuemax"));
  const current = Number(navigatorDivider.getAttribute("aria-valuenow"));
  let next = current;
  if (event.key === "Home") next = minimum;
  else if (event.key === "End") next = maximum;
  else next = Math.max(minimum, Math.min(maximum, current + (event.key === "ArrowRight" ? 8 : -8)));
  root.style.setProperty("--navigator-width", `${next}px`);
  navigatorDivider.setAttribute("aria-valuenow", String(next));
  body.dataset.splitterConsequence = String(next);
  setStatus(`Catalog navigator width ${next}px`);
});

const activateTab = (button, focus = true) => {
  if (!button) return;
  tabButtons.forEach((candidate) => {
    const selected = candidate === button;
    candidate.classList.toggle("active", selected);
    candidate.setAttribute("aria-selected", String(selected));
    candidate.tabIndex = selected ? 0 : -1;
  });
  body.dataset.activeTab = button.dataset.tab ?? "CAE Cards";
  if (focus) button.focus();
  setStatus(`${button.dataset.tab ?? "CAE Cards"} tab selected`);
};

tabButtons.forEach((button) => {
  button.addEventListener("click", () => activateTab(button));
  button.addEventListener("keydown", (event) => {
    const index = tabButtons.indexOf(button);
    let next = null;
    if (event.key === "ArrowRight") next = (index + 1) % tabButtons.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + tabButtons.length) % tabButtons.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = tabButtons.length - 1;
    if (next !== null) {
      event.preventDefault();
      activateTab(tabButtons[next]);
    }
  });
});

tabList?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") return;
  const focused = document.activeElement;
  if (focused?.getAttribute("role") !== "tab") return;
  event.preventDefault();
  activateTab(focused);
});

document.querySelector("#back-to-results")?.addEventListener("click", (event) => {
  event.preventDefault();
  body.dataset.restoredQuery = "steel";
  body.dataset.restoredSelection = "DP780-REF";
  setStatus("Returned to results · steel · DP780-REF selection restored");
});

const normalText = nativeText?.textContent ?? "";
const radText = `#RADIOSS STARTER
# CMP synthetic reference · DP780 approximation card
/UNIT/1
CMP_SI_KG_M_S
kg                 m                 s
/MAT/LAW36/DP780_R1
# DENSITY
 7.800000000E+03
# ELASTIC MODULUS                  POISSON RATIO
 2.100000000E+11                    3.000000000E-01
# INITIAL YIELD                    PLASTIC STRAIN
 4.500000000E+08                    0.000000000E+00
# ISOTROPIC HARDENING CURVE
 5.000000000E+08  1.000000000E-02
 5.600000000E+08  2.500000000E-02
 6.200000000E+08  5.000000000E-02
 6.500000000E+08  7.500000000E-02
 # APPROXIMATION: bounded post-necking extension
 6.800000000E+08  1.000000000E-01
# End of synthetic OpenRadioss card preview`;
const longText = `${normalText}\n${Array.from({ length: 90 }, (_, index) => {
  const point = String(index + 1).padStart(3, "0");
  return `** LONG EVIDENCE POINT ${point} · synthetic response continuation · ${((index + 1) * 0.005).toFixed(3)} strain`;
}).join("\n")}`;

const setField = (selector, value) => {
  const element = document.querySelector(selector);
  if (element) element.textContent = value;
};

const setActionMode = (mode) => {
  const openModeling = document.querySelector("#open-modeling");
  const backToCards = document.querySelector("#back-to-cards");
  if (!downloadButton) return;
  downloadButton.disabled = false;
  downloadButton.classList.add("primary-action");
  downloadButton.classList.remove("secondary-action");
  downloadButton.textContent = "Download .inp";
  if (openModeling) openModeling.hidden = true;
  if (backToCards) backToCards.hidden = true;
  if (mode === "approximation") {
    downloadButton.textContent = "Download .rad";
    downloadButton.disabled = !Boolean(acknowledgement?.checked);
    if (downloadButton.disabled) downloadButton.classList.add("primary-action");
  }
  if (mode === "unsupported") {
    downloadButton.textContent = "Download blocked";
    downloadButton.disabled = true;
    downloadButton.classList.remove("primary-action");
    downloadButton.classList.add("secondary-action");
    if (openModeling) openModeling.hidden = false;
    if (backToCards) backToCards.hidden = false;
  }
  if (mode === "loading") {
    downloadButton.textContent = "Loading exact evidence…";
    downloadButton.disabled = true;
  }
};

const applyState = (requestedState) => {
  const allowed = ["normal", "approximation", "unsupported", "long", "loading", "error"];
  const state = allowed.includes(requestedState) ? requestedState : "normal";
  const mode = state === "long" || state === "loading" || state === "error" ? "normal" : state;
  body.dataset.state = state;
  body.dataset.cardMode = mode;
  body.dataset.activeTab = "CAE Cards";
  activateTab(document.querySelector("#tab-cards"), false);
  if (acknowledgement) acknowledgement.checked = false;
  if (approximationRow) approximationRow.hidden = mode !== "approximation";
  if (unsupportedRow) unsupportedRow.hidden = mode !== "unsupported";
  compactMappingRows.forEach((row) => { row.hidden = mode === "approximation" || mode === "unsupported"; });
  if (previewError) previewError.hidden = state !== "error";
  if (previewLoading) previewLoading.hidden = state !== "loading";
  if (previewUnavailable) previewUnavailable.hidden = mode !== "unsupported";
  if (previewScroll) previewScroll.hidden = mode === "unsupported" || state === "loading";
  if (nativeText) nativeText.textContent = mode === "approximation" ? radText : state === "long" ? longText : normalText;
  const cardState = document.querySelector("#card-state-label");
  if (mode === "normal") {
    setField("#card-kicker", "Abaqus · Native ASCII");
    setField("#card-title", "DP780 Abaqus native material card");
    setField("#card-subtitle", "Verify the exact native solver text before downloading this card revision.");
    setField("#preview-target", "DP780_ABAQUS_R1.inp · Abaqus 2025 · kg-m-s");
    setField("#preview-scroll-note", state === "long" ? "Long text · scroll within preview" : "Read-only exact text");
    setField("#delivery-summary", state === "error" ? "Last valid exact artifact" : state === "loading" ? "Exact evidence loading" : "Exact native artifact");
    setField("#field-solver", "Abaqus · .inp");
    setField("#field-version", "Abaqus 2025");
    setField("#field-units", "kg · m · s");
    setField("#field-card-revision", "r1");
    setField("#field-lifecycle", "Draft");
    setField("#unsupported-field", "damage initiation · GISSMO");
    if (cardState) cardState.textContent = state === "loading" ? "Loading exact evidence" : state === "error" ? "Preview error · retry available" : "Exact · exportable";
    setActionMode(state === "loading" ? "loading" : "normal");
    const deliveryStatus = document.querySelector("#delivery-status");
    if (deliveryStatus) {
      deliveryStatus.dataset.tone = state === "error" ? "blocked" : "";
      deliveryStatus.textContent = state === "error" ? "Preview error · retry the exact evidence request; Record and mapping context are retained." : state === "loading" ? "Exact evidence is loading · download is temporarily disabled." : "Exact mapping · download is available without acknowledgement.";
    }
  }
  if (mode === "approximation") {
    setField("#card-kicker", "OpenRadioss · Native ASCII");
    setField("#card-title", "DP780 OpenRadioss native material card");
    setField("#card-subtitle", "Review the named approximation before downloading this exact card revision.");
    setField("#preview-target", "DP780_OPENRADIOSS_R1.rad · OpenRadioss 2025 · kg-m-s");
    setField("#preview-scroll-note", "Read-only preview · review required");
    setField("#delivery-summary", "Review required · download blocked");
    setField("#field-solver", "OpenRadioss · .rad");
    setField("#field-version", "OpenRadioss 2025");
    setField("#field-units", "kg · m · s");
    setField("#field-card-revision", "r1");
    setField("#field-lifecycle", "Draft");
    if (cardState) cardState.textContent = "Review required · download blocked";
    setActionMode("approximation");
    const deliveryStatus = document.querySelector("#delivery-status");
    if (deliveryStatus) {
      deliveryStatus.dataset.tone = "warning";
      deliveryStatus.textContent = acknowledgement?.checked ? "Acknowledgement recorded locally · download is enabled for this exact card." : "Review the post-necking extension and acknowledge it to enable Download .rad.";
    }
  }
  if (mode === "unsupported") {
    setField("#card-kicker", "OpenRadioss · Native ASCII");
    setField("#card-title", "DP780 OpenRadioss native material card");
    setField("#card-subtitle", "Preflight stopped before artifact creation; choose a safe recovery action.");
    setField("#preview-target", "DP780_OPENRADIOSS_R1.rad · OpenRadioss 2025 · kg-m-s");
    setField("#delivery-summary", "Unsupported mapping · blocked");
    setField("#field-solver", "OpenRadioss · .rad");
    setField("#field-version", "OpenRadioss 2025");
    setField("#field-units", "kg · m · s");
    setField("#field-card-revision", "r1");
    setField("#field-lifecycle", "Draft");
    if (cardState) cardState.textContent = "Unsupported · preflight blocked";
    setActionMode("unsupported");
    const deliveryStatus = document.querySelector("#delivery-status");
    if (deliveryStatus) {
      deliveryStatus.dataset.tone = "blocked";
      deliveryStatus.textContent = "No native artifact was created · inspect the unsupported field in Modeling.";
    }
  }
};

acknowledgement?.addEventListener("change", () => {
  if (body.dataset.state !== "approximation") return;
  setActionMode("approximation");
  body.dataset.approximationAcknowledged = acknowledgement.checked ? "true" : "false";
  setStatus(acknowledgement.checked ? "Approximation acknowledged locally · Download .rad enabled" : "Approximation acknowledgement cleared · download blocked");
  const deliveryStatus = document.querySelector("#delivery-status");
  if (deliveryStatus) deliveryStatus.textContent = acknowledgement.checked ? "Acknowledgement recorded locally · download is enabled for this exact card." : "Review the post-necking extension and acknowledge it to enable Download .rad.";
});

downloadButton?.addEventListener("click", () => {
  if (downloadButton.disabled) return;
  const mode = body.dataset.cardMode ?? "normal";
  body.dataset.cardDownload = mode === "approximation" ? "OpenRadioss:.rad" : "Abaqus:.inp";
  setStatus(`Download prepared · ${mode === "approximation" ? "OpenRadioss .rad" : "Abaqus .inp"} exact reference card`);
});

document.querySelector("#open-modeling")?.addEventListener("click", () => {
  body.dataset.recoveryOpenModeling = "true";
  setStatus("Open Modeling selected · unsupported field retained for diagnosis");
});

document.querySelector("#back-to-cards")?.addEventListener("click", () => {
  body.dataset.recoveryBackToCards = "true";
  setStatus("Back to CAE Cards · DP780 Record and revision retained");
});

document.querySelector("#retry-preview")?.addEventListener("click", () => {
  body.dataset.previewRetry = "true";
  applyState("normal");
  setStatus("Preview retry succeeded · exact card context retained");
});

const initialState = new URLSearchParams(window.location.search).get("state") ?? "normal";
applyState(initialState);

window.applyMaterialsCardState = applyState;
