const body = document.body;
const interactionStatus = document.querySelector("#interaction-status");
const targetSelect = document.querySelector("[data-target-select]");
const unitSystemSelect = document.querySelector("[data-unit-system-select]");
const createButton = document.querySelector("[data-action='create-card']");
const retryButton = document.querySelector("[data-action='retry-preview']");
const runCheckButton = document.querySelector("[data-action='run-check']");
const acknowledgement = document.querySelector("[data-approximation-ack]");
const mappingList = document.querySelector("#mapping-list");
const mappingScroll = document.querySelector(".mapping-scroll");
const nativeText = document.querySelector("#native-text");
const nativeScroll = document.querySelector("#native-preview-scroll");
const previewLoading = document.querySelector("[data-preview-loading]");
const previewError = document.querySelector("[data-preview-error]");
const sourceGraphWrap = document.querySelector("[data-source-graph-wrap]");
const propertiesPane = document.querySelector("[data-region='properties']");
const divider = document.querySelector("[data-region='export-divider']");
const dividerResizer = document.querySelector(".export-divider-resizer");
const mappingScrollCue = document.querySelector(".mapping-scroll-cue");
const nativeScrollCue = document.querySelector(".native-scroll-cue");

const metalText = nativeText?.textContent ?? "";
const targetText = {
  abaqus: `*HEADING
** CMP synthetic reference · DP780 selected model
*MATERIAL, NAME=DP780_SYNTHETIC_R1
** Selected model: Swift / Voce blend (50/50)
** Unit convention: kg · m · s; stress in Pa
*DENSITY
  7.80000000E+03,
*ELASTIC
  2.10000000E+11, 3.00000000E-01
*PLASTIC
  4.50000000E+08, 0.00000000E+00
  5.00000000E+08, 1.00000000E-02
  5.60000000E+08, 2.50000000E-02
  6.20000000E+08, 5.00000000E-02
  6.80000000E+08, 1.00000000E-01
** Mapping: density exact · source/output kg/m³ agree
** Mapping: isotropic elasticity exact · source/output Pa agree
** Mapping: initial yield transformed · first *PLASTIC row
** Mapping: hardening response transformed · native formatting
** Mapping: post-necking extension · approximation acknowledged for this exact preview
** Preview only · Create solver card writes one immutable revision
** End of exact synthetic Abaqus card`,
  openradioss: `#RADIOSS STARTER
## CMP synthetic reference · DP780 selected model
/MAT/LAW36/DP780_SYNTHETIC_R1
## Selected model: Swift / Voce blend (50/50)
## Unit convention: kg · m · s; stress in Pa
#DENSITY
  7.80000000E+03
#ELASTIC
  E=2.10000000E+11  NU=3.00000000E-01
#PLASTIC
  4.50000000E+08  0.00000000E+00
  5.00000000E+08  1.00000000E-02
  5.60000000E+08  2.50000000E-02
  6.20000000E+08  5.00000000E-02
  6.80000000E+08  1.00000000E-01
## Mapping: density exact · isotropic elasticity exact
## Mapping: post-necking extension approximated for this tuple
## Preview only · exact acknowledgement required before create
## End of synthetic OpenRadioss card`,
};

const familyDefinitions = {
  metal: {
    label: "Metal hardening response",
    context: "DP780 Dual-Phase Steel · Tensile · room temperature",
    source: "Swift / Voce blend (50/50)",
    digest: "metal-abaqus-2025-kg_m_s-v1",
    graph: "metal",
    fitResult: "Swift / Voce blend (50/50)",
    rows: [
      ["exact", "Density", "7,800 kg/m³ → 7.8000E+03"],
      ["exact", "Isotropic elasticity", "210 GPa, ν 0.30 → *ELASTIC"],
      ["transformed", "Initial yield", "450 MPa at εp = 0 → first *PLASTIC row"],
      ["transformed", "Hardening response", "5 points → native *PLASTIC rows"],
      ["transformed", "Unit convention", "kg · m · s → stress in Pa"],
      ["approximated", "Post-necking extension", "Bounded extension → target behavior"],
    ],
    counts: { exact: 2, transformed: 3, approximated: 1, not_applicable: 2, unsupported: 0 },
    advanced: ["Temperature applicability", "Strain-rate applicability"],
  },
  "linear-viscoelastic": {
    label: "Linear viscoelastic response",
    context: "Reference polymer · linear viscoelastic · 23 °C context",
    source: "Generalized Maxwell",
    digest: "linear-viscoelastic-abaqus-2025-kg_m_s-v1",
    graph: "linear-viscoelastic",
    fitResult: "Generalized Maxwell",
    rows: [
      ["exact", "Density", "1,120 kg/m³ → 1.1200E+03"],
      ["exact", "Instantaneous elasticity", "2.40 MPa, ν 0.49 → *ELASTIC"],
      ["exact", "Shear Prony terms", "2 terms → *VISCOELASTIC"],
      ["exact", "Bulk Prony terms", "2 terms → native Prony fields"],
      ["not_applicable", "Temperature applicability", "23 °C context → no shift law"],
      ["transformed", "Unit convention", "kg · m · s → stress in Pa"],
    ],
    counts: { exact: 4, transformed: 1, approximated: 0, not_applicable: 1, unsupported: 0 },
    advanced: ["Reference temperature shift"],
  },
  hyperelastic: {
    label: "Ogden-Prony hyperelastic response",
    context: "Reference elastomer · Ogden-Prony · uniaxial mode",
    source: "Ogden N=1 + shear Prony",
    digest: "hyperelastic-abaqus-2025-kg_m_s-v1",
    graph: "hyperelastic",
    fitResult: "Ogden N=1 + shear Prony",
    rows: [
      ["exact", "Density", "980 kg/m³ → 9.8000E+02"],
      ["exact", "Ogden strain-energy term", "μ, α → *HYPERELASTIC, OGDEN"],
      ["exact", "Volumetric response", "Incompressible → D1 = 0"],
      ["exact", "Shear Prony terms", "Ordered terms → *VISCOELASTIC"],
      ["not_applicable", "Available test modes", "Fit controls only → no solver field"],
      ["transformed", "Unit convention", "kg · m · s → stress in Pa"],
    ],
    counts: { exact: 4, transformed: 1, approximated: 0, not_applicable: 1, unsupported: 0 },
    advanced: ["Reference temperature applicability"],
  },
};

const graphDefinitions = {
  metal: {
    title: "True stress versus true plastic strain",
    description: "True stress in MPa against true plastic strain. Data-derived padding keeps the positive initial yield and maximum response clear of the frame.",
    xTitle: "True plastic strain [1]",
    yTitle: "True stress (MPa)",
    xTicks: [0, 0.05, 0.1],
    yTicks: [450, 550, 650],
    xFormat: (value) => value.toFixed(2),
    yFormat: (value) => String(value),
    xLowerBound: 0,
    legendZone: "lower-right",
    curves: [
      { name: "Saved blend", className: "blend", points: [[0, 450], [0.01, 500], [0.025, 560], [0.05, 620], [0.1, 680]] },
      { name: "Observed", className: "observed", points: [[0, 445], [0.01, 497], [0.025, 556], [0.05, 616], [0.1, 672]] },
    ],
  },
  "linear-viscoelastic": {
    title: "Normalized shear response versus log time",
    description: "Normalized shear modulus against log time. The range is padded from the visible data span.",
    xTitle: "log time (s)",
    yTitle: "Normalized shear modulus [1]",
    xTicks: [-3, 0, 3],
    yTicks: [0.2, 0.6, 1],
    xFormat: (value) => String(value).replace("-", "−"),
    yFormat: (value) => value.toFixed(1),
    legendZone: "upper-right",
    curves: [
      { name: "Fit response", className: "visco-fit", points: [[-3, 0.98], [-2, 0.84], [-1, 0.69], [0, 0.52], [1, 0.37], [2, 0.24], [3, 0.14]] },
      { name: "Observed", className: "visco-observed", points: [[-3, 1], [-2, 0.86], [-1, 0.67], [0, 0.54], [1, 0.35], [2, 0.26], [3, 0.12]] },
    ],
  },
  hyperelastic: {
    title: "Hyperelastic response by test mode",
    description: "Nominal stress in kPa against stretch ratio. The range is padded from the visible data span.",
    xTitle: "Stretch ratio [1]",
    yTitle: "Nominal stress (kPa)",
    xTicks: [1, 1.5, 2],
    yTicks: [0, 450, 900],
    xFormat: (value) => value.toFixed(1),
    yFormat: (value) => String(value),
    legendZone: "lower-right",
    curves: [
      { name: "Ogden fit", className: "hyper-fit", points: [[1, 0], [1.15, 190], [1.35, 390], [1.6, 610], [1.8, 770], [2, 900]] },
      { name: "Observed", className: "hyper-observed", points: [[1, 12], [1.15, 182], [1.35, 402], [1.6, 594], [1.8, 786], [2, 884]] },
    ],
  },
};

const svgNamespace = "http://www.w3.org/2000/svg";
const makeSvg = (tag, attributes = {}, text = "") => {
  const node = document.createElementNS(svgNamespace, tag);
  Object.entries(attributes).forEach(([name, value]) => node.setAttribute(name, String(value)));
  if (text) node.textContent = text;
  return node;
};

const paddedDomain = (values, ratio = 0.1, lowerBound) => {
  const dataMin = Math.min(...values);
  const dataMax = Math.max(...values);
  const span = Math.max(dataMax - dataMin, Math.abs(dataMax) || 1);
  const lower = lowerBound !== undefined && dataMin >= lowerBound ? lowerBound : dataMin - span * ratio;
  return { dataMin, dataMax, min: lower, max: dataMax + span * ratio, ratio };
};

const renderGraph = (graph, definition) => {
  const width = 320;
  const height = 210;
  const plot = { x: 40, y: 20, width: 272, height: 154 };
  const xValues = definition.curves.flatMap((curve) => curve.points.map(([x]) => x));
  const yValues = definition.curves.flatMap((curve) => curve.points.map(([, y]) => y));
  const xDomain = paddedDomain(xValues, 0.1, definition.xLowerBound);
  const yDomain = paddedDomain(yValues, 0.1);
  const xScale = (value) => plot.x + ((value - xDomain.min) / (xDomain.max - xDomain.min)) * plot.width;
  const yScale = (value) => plot.y + plot.height - ((value - yDomain.min) / (yDomain.max - yDomain.min)) * plot.height;

  graph.replaceChildren();
  graph.setAttribute("viewBox", `0 0 ${width} ${height}`);
  graph.dataset.paddingRatio = String(xDomain.ratio);
  graph.dataset.xDataMin = String(xDomain.dataMin);
  graph.dataset.xDataMax = String(xDomain.dataMax);
  graph.dataset.xDomainMin = String(xDomain.min);
  graph.dataset.xDomainMax = String(xDomain.max);
  graph.dataset.yDataMin = String(yDomain.dataMin);
  graph.dataset.yDataMax = String(yDomain.dataMax);
  graph.dataset.yDomainMin = String(yDomain.min);
  graph.dataset.yDomainMax = String(yDomain.max);
  graph.dataset.positiveYield = definition === graphDefinitions.metal ? "true" : "not-applicable";

  graph.append(makeSvg("title", {}, definition.title), makeSvg("desc", {}, definition.description));
  graph.append(makeSvg("rect", { class: "plot-frame", x: plot.x, y: plot.y, width: plot.width, height: plot.height }));

  const grid = makeSvg("g", { class: "plot-grid" });
  definition.yTicks.forEach((tick) => {
    const y = yScale(tick);
    grid.append(makeSvg("line", { x1: plot.x, y1: y, x2: plot.x + plot.width, y2: y }));
    graph.append(makeSvg("text", { class: "plot-axis-label", x: plot.x - 7, y: y + 3, "text-anchor": "end" }, definition.yFormat(tick)));
  });
  definition.xTicks.forEach((tick) => {
    const x = xScale(tick);
    grid.append(makeSvg("line", { x1: x, y1: plot.y, x2: x, y2: plot.y + plot.height }));
    graph.append(makeSvg("text", { class: "plot-axis-label", x, y: plot.y + plot.height + 13, "text-anchor": "middle" }, definition.xFormat(tick)));
  });
  graph.append(grid);

  definition.curves.forEach((curve) => {
    const path = curve.points.map(([x, y], index) => `${index ? "L" : "M"}${xScale(x).toFixed(2)} ${yScale(y).toFixed(2)}`).join(" ");
    graph.append(makeSvg("path", { class: `source-curve ${curve.className}`, d: path }));
  });

  graph.append(
    makeSvg("text", { class: "plot-axis-title", x: plot.x, y: 12 }, definition.yTitle),
    makeSvg("text", { class: "plot-axis-title", x: plot.x + plot.width / 2, y: 205, "text-anchor": "middle" }, definition.xTitle),
  );

  const legend = makeSvg("g", { class: "source-legend", "data-zone": definition.legendZone });
  const legendX = 214;
  const legendY = definition.legendZone === "upper-right" ? 35 : 137;
  definition.curves.forEach((curve, index) => {
    const y = legendY + index * 14;
    legend.append(
      makeSvg("line", { x1: legendX, y1: y, x2: legendX + 13, y2: y, class: curve.className }),
      makeSvg("text", { x: legendX + 18, y: y + 3 }, curve.name),
    );
  });
  graph.append(legend);
};

const renderGraphs = () => {
  document.querySelectorAll(".source-graph").forEach((graph) => {
    const definition = graphDefinitions[graph.dataset.familyGraph];
    if (definition) renderGraph(graph, definition);
  });
};

const params = new URLSearchParams(window.location.search);
const requestedFamily = params.get("family");
const family = Object.prototype.hasOwnProperty.call(familyDefinitions, requestedFamily) ? requestedFamily : "metal";
body.dataset.family = family;

const setText = (selector, value) => {
  const element = document.querySelector(selector);
  if (element) element.textContent = value;
};

const setHidden = (selector, hidden) => {
  const element = document.querySelector(selector);
  if (element) element.hidden = hidden;
};

const setStatus = (message) => {
  if (interactionStatus) interactionStatus.textContent = message;
};

const syncScrollCue = (scrollNode, cue) => {
  const thumb = cue?.querySelector("span");
  if (!scrollNode || !cue || !thumb || scrollNode.scrollHeight <= scrollNode.clientHeight) return;
  const trackHeight = cue.clientHeight - 4;
  const thumbHeight = Math.max(34, trackHeight * (scrollNode.clientHeight / scrollNode.scrollHeight));
  const travel = Math.max(0, trackHeight - thumbHeight);
  const progress = scrollNode.scrollTop / Math.max(1, scrollNode.scrollHeight - scrollNode.clientHeight);
  thumb.style.height = `${thumbHeight}px`;
  thumb.style.top = `${2 + travel * progress}px`;
};

const syncScrollCues = () => {
  syncScrollCue(mappingScroll, mappingScrollCue);
  syncScrollCue(nativeScroll, nativeScrollCue);
};

const familyDefinition = () => familyDefinitions[body.dataset.family] || familyDefinitions.metal;
const selectedTarget = () => targetSelect?.value || "";
const mappingRowsForTarget = () => familyDefinition().rows.map(([status, title, copy]) => {
  if (selectedTarget() !== "openradioss") return [status, title, copy];
  if (body.dataset.family === "metal" && title === "Unit convention") return ["exact", title, "kg · m · s → stress in Pa"];
  if (body.dataset.family === "hyperelastic" && title === "Volumetric response") return ["approximated", title, "Incompressible → ν = 0.495 representation"];
  return [status, title, copy];
});
const mappingCountsForTarget = () => {
  const counts = mappingRowsForTarget().reduce((result, [status]) => {
    result[status] = (result[status] || 0) + 1;
    return result;
  }, { exact: 0, transformed: 0, approximated: 0, not_applicable: 0, unsupported: 0 });
  counts.not_applicable = familyDefinition().counts.not_applicable;
  return counts;
};
const familyRequiresReview = () => mappingRowsForTarget().some(([status]) => status === "approximated");
const targetRequiresAcknowledgement = () => selectedTarget() === "openradioss" && familyRequiresReview();

const setStateTruth = (state) => {
  const truths = {
    "preview-ready": ["Ready to create", "Export check complete", "Selected model", "Export check complete", "Ready to create"],
    "source-blocked": ["Cannot create", "Select a model in Fit", "No selected model", "Source required", "Cannot create"],
    "approximation-blocked": ["Review required", "Confirm 1 approximation", "Selected model", "Review required", "1 item to review"],
    delivered: ["Solver Card created", "Card available", "Selected model", "Solver Card created", "Created"],
    "no-target-empty": ["Cannot create", "Select Destination", "Selected model", "Destination required", "Cannot create"],
    loading: ["Checking export…", "Checking export…", "Selected model", "Checking export…", "Checking"],
    "delivery-error": ["Solver Card not created", "Retry available", "Selected model", "Create failed", "Retry available"],
    "long-mapping": ["Ready to create", "Export check complete", "Selected model", "Export check complete", "Ready to create"],
    "target-changed": ["Check required", "Run Export check", "Selected model", "Destination changed", "Check required"],
  };
  const values = [...(truths[state] || truths["preview-ready"] )];
  if (state !== "source-blocked") values[2] = familyDefinition().source;
  if (body.dataset.family !== "metal" && ["preview-ready", "long-mapping"].includes(state)) values[4] = "Ready to create";
  ["[data-session-state]", "[data-stage-status]", "[data-status-selection]", "[data-status-job]", "[data-status-warning]"].forEach((selector, index) => setText(selector, values[index]));
};

const renderFamily = () => {
  const definition = familyDefinition();
  const mappingRows = mappingRowsForTarget();
  const hasTarget = Boolean(selectedTarget());
  setText("[data-context-material]", definition.context);
  setText("[data-fit-family-label]", definition.label);
  setText("[data-fit-copy]", definition.source);
  setText("[data-mapping-digest]", hasTarget ? definition.digest : "");
  setHidden("[data-family-modes]", body.dataset.family !== "hyperelastic");
  document.querySelectorAll(".source-graph").forEach((graph) => {
    graph.toggleAttribute("hidden", graph.dataset.familyGraph !== definition.graph);
  });
  renderGraphs();
  if (mappingList) {
    mappingList.replaceChildren(...mappingRows.map(([status, title, copy]) => {
      const row = document.createElement("li");
      row.className = `mapping-row ${status === "approximated" ? "mapping-review" : ""}`;
      row.dataset.status = status;
      if (status === "approximated") row.dataset.approximationRow = "true";
      if (status === "not_applicable") row.hidden = true;
      const badge = document.createElement("span");
      badge.className = `mapping-status ${status === "approximated" ? "acknowledged" : status}`;
      badge.textContent = status === "approximated" ? "Reviewed" : status === "transformed" ? "Converted" : status === "exact" ? "Exact" : "N/A";
      const copyWrap = document.createElement("div");
      const heading = document.createElement("strong");
      heading.textContent = title;
      const detail = document.createElement("span");
      detail.textContent = copy;
      copyWrap.append(heading, detail);
      row.append(copyWrap, badge);
      return row;
    }));
  }
  const advancedList = document.querySelector(".technical-list");
  if (advancedList) advancedList.querySelectorAll("[data-advanced-family]").forEach((node) => node.remove());
  if (!hasTarget) {
    if (mappingList) {
      const placeholder = document.createElement("li");
      placeholder.className = "mapping-placeholder";
      placeholder.dataset.mappingPlaceholder = "true";
      placeholder.textContent = "No mapping available";
      mappingList.replaceChildren(placeholder);
    }
    setText("[data-mapping-state]", "");
    setText("[data-mapping-subtitle]", "");
    return;
  }
  const visibleRows = mappingRows.filter(([status]) => status !== "not_applicable").length;
  setText("[data-mapping-state]", `${visibleRows} mapped`);
  if (advancedList) {
    definition.advanced.forEach((label) => {
      const row = document.createElement("div");
      row.dataset.advancedFamily = "true";
      row.innerHTML = `<dt>${label}</dt><dd><span class="technical-status">NOT_APPLICABLE</span> · Advanced</dd>`;
      advancedList.prepend(row);
    });
  }
};

const renderNative = () => {
  if (!nativeText) return;
  const target = selectedTarget();
  if (!target) {
    nativeText.textContent = "";
    return;
  }
  if (body.dataset.family === "metal") nativeText.textContent = targetText[target] || metalText;
  else if (body.dataset.family === "linear-viscoelastic") nativeText.textContent = `*HEADING\n** CMP reference / non-production · linear viscoelastic\n*MATERIAL, NAME=LINEAR_VISCO_REFERENCE_R1\n** Unit convention: kg · m · s; stress in Pa\n*DENSITY\n  1.12000000E+03,\n*ELASTIC\n  2.40000000E+06, 4.90000000E-01\n*VISCOELASTIC, TIME=PRONY, TYPE=ISOTROPIC\n  2.50000000E-01, 0.00000000E+00, 1.00000000E-02\n  1.50000000E-01, 0.00000000E+00, 1.00000000E+00\n** Mapping: shear and bulk Prony terms exact\n** Mapping: temperature applicability not_applicable · Advanced\n** Preview only · Create solver card writes one immutable revision`;
  else nativeText.textContent = `*HEADING\n** CMP reference / non-production · Ogden-Prony hyperelastic\n*MATERIAL, NAME=OGDEN_PRONY_REFERENCE_R1\n** Mode: Uniaxial · Unit convention: kg · m · s; stress in Pa\n*DENSITY\n  9.80000000E+02,\n*HYPERELASTIC, OGDEN, N=1\n  1.20000000E+06, 2.00000000E+00, 0.00000000E+00\n*VISCOELASTIC, TIME=PRONY\n  2.50000000E-01, 1.00000000E-02\n** Volumetric response: Abaqus D1=0 exact\n** Available Fit modes: Uniaxial | Biaxial | Planar | Volumetric\n** Preview only · Create solver card writes one immutable revision`;
};

const updateCounts = (counts) => {
  setText("[data-count='exact']", String(counts.exact));
  setText("[data-count='transformed']", String(counts.transformed));
  setText("[data-count='approximated']", String(counts.approximated));
  setText("[data-count='not_applicable']", String(counts.not_applicable));
  body.dataset.mappingCounts = JSON.stringify(counts);
};

const setSourceFields = (missing) => {
  setText("[data-source-state]", missing ? "Missing" : "Available");
  const definition = familyDefinition();
  setText("[data-field='model-result']", missing ? "Not selected" : definition.fitResult);
  setText("[data-fit-family-label]", missing ? "Fit source unavailable" : definition.label);
  setText("[data-fit-copy]", missing ? "No selected model" : definition.source);
  ["[data-action='view-source']", "[data-action='open-fit']"].forEach((selector) => {
    const control = document.querySelector(selector);
    if (!control) return;
    control.disabled = missing;
    control.setAttribute("aria-disabled", String(missing));
  });
};

const setTargetFields = () => {
  const selected = Boolean(selectedTarget());
  setText("[data-target-state]", selected ? "Selected" : "Choose destination");
  setText("[data-target-version]", selected ? "2025" : "");
  if (unitSystemSelect) {
    unitSystemSelect.disabled = !selected;
    unitSystemSelect.value = selected ? "kg_m_s" : "";
  }
  setText("[data-target-helper]", body.dataset.state === "target-changed" ? "Run Export check for this destination." : "");
  setHidden("[data-target-helper]", body.dataset.state !== "target-changed");
  setText("[data-preview-target]", selected ? `${selectedTarget() === "openradioss" ? "OpenRadioss" : "Abaqus"} 2025 · kg · m · s · synthetic reference` : "No target selected");
};

const setButton = (label, action, disabled = false) => {
  if (!createButton) return;
  createButton.textContent = label;
  createButton.dataset.action = action;
  createButton.disabled = disabled;
  createButton.setAttribute("aria-disabled", String(disabled));
};

const setRowsForState = (state) => {
  const rows = [...document.querySelectorAll(".mapping-row")];
  rows.forEach((row) => { row.hidden = row.dataset.status === "not_applicable"; });
  if (state === "source-blocked") {
    if (mappingList) {
      mappingList.replaceChildren();
      const row = document.createElement("li");
      row.className = "mapping-row";
      row.dataset.status = "blocked";
      row.innerHTML = `<div><strong>No mapping available</strong><span>Selected model required</span></div><span class="mapping-status blocked">Blocked</span>`;
      mappingList.append(row);
    }
    setText("[data-mapping-state]", "Unavailable");
    body.dataset.mappingCounts = JSON.stringify({ exact: 0, transformed: 0, approximated: 0, not_applicable: 0, unsupported: 0, blockers: 1 });
    return;
  }
  if (state === "no-target-empty") {
    if (mappingList) {
      const placeholder = document.createElement("li");
      placeholder.className = "mapping-placeholder";
      placeholder.dataset.mappingPlaceholder = "true";
      placeholder.textContent = "No mapping available";
      mappingList.replaceChildren(placeholder);
    }
    setText("[data-mapping-state]", "");
    setText("[data-mapping-subtitle]", "");
    body.dataset.mappingCounts = JSON.stringify({ exact: 0, transformed: 0, approximated: 0, not_applicable: 0, unsupported: 0 });
    return;
  }
  if (mappingList && !mappingList.children.length) renderFamily();
  const approxRequired = state !== "source-blocked" && state !== "no-target-empty";
  const reviewedState = state !== "approximation-blocked" || Boolean(acknowledgement?.checked);
  document.querySelectorAll("[data-approximation-row]").forEach((row) => {
    row.hidden = !approxRequired;
    row.classList.toggle("mapping-warning", approxRequired && !reviewedState);
    const badge = row.querySelector(".mapping-status");
    if (badge) {
      badge.className = `mapping-status ${reviewedState ? "acknowledged" : "approximated"}`;
      badge.textContent = reviewedState ? "Reviewed" : "Review";
    }
    const detail = row.querySelector("div > span");
    if (detail) detail.textContent = "Bounded extension → target behavior";
  });
  updateCounts(state === "source-blocked" ? { exact: 0, transformed: 0, approximated: 0, not_applicable: 0, unsupported: 0, blockers: 1 } : mappingCountsForTarget());
};

const setCheckResult = (label, summary, tone = "ready") => {
  setText("[data-check-state]", label);
  setText("[data-check-summary]", summary);
  const result = document.querySelector("[data-check-status]");
  if (!result) return;
  result.classList.remove("warning", "blocked");
  if (tone !== "ready") result.classList.add(tone);
};

const updateControls = (state) => {
  const approx = state === "approximation-blocked" || (targetRequiresAcknowledgement() && body.dataset.previewCurrent === "true");
  const acknowledged = Boolean(acknowledgement?.checked);
  setHidden("[data-ack-row]", !approx || state === "source-blocked" || state === "no-target-empty");
  setHidden("[data-action='delivery-details']", state !== "delivered");
  setHidden("[data-action='retry-preview']", state !== "target-changed");
  setHidden("[data-action='run-check']", state !== "target-changed");
  document.querySelector("[data-preview-state]")?.classList.remove("warning", "blocked", "good");
  setText("[data-properties-state]", state === "loading" ? "Checking" : state === "source-blocked" || state === "no-target-empty" || state === "target-changed" ? "Blocked" : "Ready");
  if (state === "source-blocked") {
    setCheckResult("Cannot create", "Select a model in Fit.", "blocked");
    setButton("Back to Fit", "back-fit", false);
    setText("[data-preview-state]", "Unavailable");
    document.querySelector("[data-preview-state]")?.classList.add("blocked");
    setRowsForState(state);
  } else if (state === "no-target-empty") {
    setCheckResult("Cannot create", "Select a destination.", "blocked");
    setButton("Select Destination", "select-destination", false);
    setText("[data-preview-state]", "Unavailable");
    document.querySelector("[data-preview-state]")?.classList.add("blocked");
    setRowsForState(state);
  } else if (state === "loading") {
    setCheckResult("Checking export…", "Create is temporarily unavailable.", "warning");
    setButton("Create solver card", "create-card", true);
    setText("[data-preview-state]", "");
    setRowsForState(state);
  } else if (state === "delivery-error") {
    setCheckResult("Solver Card not created", "Retry create.", "blocked");
    setButton("Retry create", "retry-create", false);
    setText("[data-preview-state]", "Current preview");
    document.querySelector("[data-preview-state]")?.classList.add("blocked");
    setRowsForState(state);
  } else if (state === "target-changed") {
    setCheckResult("Check required", "Run Export check for this destination.", "warning");
    setButton("Create solver card", "create-card", true);
    setText("[data-preview-state]", "Stale · run Export check");
    document.querySelector("[data-preview-state]")?.classList.add("warning");
    setRowsForState(state);
  } else if (state === "approximation-blocked") {
    setCheckResult(acknowledged ? "Ready to create" : "Review required", acknowledged ? "Approximation confirmed." : "Confirm 1 approximation.", acknowledged ? "ready" : "warning");
    setButton("Create solver card", "create-card", !acknowledged);
    setText("[data-preview-state]", "Current preview");
    setRowsForState(state);
  } else if (state === "delivered") {
    setCheckResult("Solver Card created", "Open the created card.");
    setButton("Open solver card", "open-card", false);
    setText("[data-preview-state]", "Delivered · Solver Card");
    document.querySelector("[data-preview-state]")?.classList.add("good");
    setRowsForState(state);
  } else {
    setCheckResult("Ready to create", "No blockers.");
    setButton("Create solver card", "create-card", false);
    setText("[data-preview-state]", "Current preview · not created");
    document.querySelector("[data-preview-state]")?.classList.remove("warning", "blocked", "good");
    setRowsForState(state);
  }
  const sourceMissing = state === "source-blocked";
  setSourceFields(sourceMissing);
  setTargetFields();
  updateCounts(state === "source-blocked" ? { exact: 0, transformed: 0, approximated: 0, not_applicable: 0, unsupported: 0, blockers: 1 } : state === "no-target-empty" ? { exact: 0, transformed: 0, approximated: 0, not_applicable: 0, unsupported: 0 } : mappingCountsForTarget());
  setStateTruth(state);
  requestAnimationFrame(syncScrollCues);
};

const setState = (state) => {
  const allowed = ["preview-ready", "source-blocked", "approximation-blocked", "delivered", "no-target-empty", "loading", "delivery-error", "long-mapping", "target-changed"];
  const next = allowed.includes(state) ? state : "preview-ready";
  body.dataset.state = next;
  body.dataset.previewCurrent = ["preview-ready", "approximation-blocked", "delivered", "loading", "delivery-error", "long-mapping"].includes(next) ? "true" : "false";
  if (next === "delivered") {
    body.dataset.deliveryCount = "1";
    body.dataset.deliveryPointer = "SC-DEMO-00041";
  }
  if (next === "source-blocked") targetSelect.value = "abaqus";
  else if (next === "approximation-blocked") targetSelect.value = "openradioss";
  else if (next === "no-target-empty") targetSelect.value = "";
  else if (!targetSelect.value) targetSelect.value = body.dataset.family === "linear-viscoelastic" ? "abaqus" : "abaqus";
  renderFamily();
  renderNative();
  if (next === "source-blocked") {
    setText("[data-preview-target]", `${selectedTarget() === "openradioss" ? "OpenRadioss" : "Abaqus"} 2025 · kg · m · s`);
    setText("[data-preview-state]", "Unavailable · model required");
  } else if (next === "no-target-empty") {
    setText("[data-preview-target]", "No target selected");
  }
  setHidden("[data-preview-loading]", next !== "loading");
  setHidden("[data-preview-error]", next !== "delivery-error");
  if (next === "delivery-error") setText("[data-preview-error]", "Solver Card was not created. The checked preview is unchanged.");
  if (next === "source-blocked" || next === "no-target-empty" || next === "target-changed") nativeText.textContent = "";
  else renderNative();
  if (next === "long-mapping" && mappingList) {
    const base = mappingRowsForTarget().filter(([status]) => status !== "not_applicable");
    const expanded = Array.from({ length: 28 }, (_, index) => base[index % base.length].map((value, part) => part === 1 ? `${value} · target field ${String(index + 1).padStart(2, "0")}` : value));
    mappingList.replaceChildren(...expanded.map(([status, title, copy]) => {
      const row = document.createElement("li"); row.className = "mapping-row"; row.dataset.status = status;
      const badge = document.createElement("span"); badge.className = `mapping-status ${status === "approximated" ? "acknowledged" : status}`; badge.textContent = status === "approximated" ? "Reviewed" : status === "transformed" ? "Converted" : "Exact";
      const wrap = document.createElement("div"); wrap.innerHTML = `<strong>${title}</strong><span>${copy}</span>`; row.append(wrap, badge); return row;
    }));
    setText("[data-mapping-state]", "28 mapped");
    if (nativeText) {
      const baseText = targetText[selectedTarget() || "abaqus"] || metalText;
      nativeText.textContent = `${baseText}\n${Array.from({ length: 40 }, (_, index) => `** Target field ${String(index + 1).padStart(2, "0")} · source revision pinned`).join("\n")}`;
    }
  }
  updateControls(next);
};

targetSelect?.addEventListener("change", () => {
  body.dataset.deliveryCount = "0";
  body.dataset.deliveryPointer = "";
  body.dataset.previewCurrent = "false";
  if (acknowledgement) acknowledgement.checked = false;
  const next = selectedTarget() ? "target-changed" : "no-target-empty";
  setState(next);
  setStatus(selectedTarget() ? "Target changed · preview, acknowledgement and delivery cleared" : "Destination cleared · select one declared target");
});

unitSystemSelect?.addEventListener("change", () => {
  if (!selectedTarget() || !unitSystemSelect.value) return;
  body.dataset.deliveryCount = "0";
  body.dataset.deliveryPointer = "";
  body.dataset.previewCurrent = "false";
  if (acknowledgement) acknowledgement.checked = false;
  setState("target-changed");
  setStatus("Output unit system changed · preview, acknowledgement and delivery cleared");
});

acknowledgement?.addEventListener("change", () => {
  updateControls(body.dataset.state);
  setStatus(acknowledgement.checked ? "Acknowledgement recorded for this exact approximation identity" : "Acknowledgement cleared · Create solver card is blocked");
});

const runCheck = () => {
  body.dataset.previewCurrent = "true";
  body.dataset.state = targetRequiresAcknowledgement() ? "approximation-blocked" : "preview-ready";
  renderNative();
  setState(body.dataset.state);
  setStatus("Export check complete · deterministic preview replaced for the selected target");
};

retryButton?.addEventListener("click", runCheck);
runCheckButton?.addEventListener("click", runCheck);

createButton?.addEventListener("click", () => {
  const action = createButton.dataset.action;
  if (action === "back-fit") { setStatus("Back to Fit requested · Export context preserved"); return; }
  if (action === "select-destination") { targetSelect?.focus(); setStatus("Select one declared Destination tuple before Export check"); return; }
  if (action === "open-card") { setStatus("Opened immutable Solver Card preview"); return; }
  if (createButton.disabled) { setStatus("Create solver card blocked · resolve the adjacent Export check item"); return; }
  body.dataset.deliveryCount = "1";
  body.dataset.deliveryPointer = "SC-DEMO-00041";
  body.dataset.previewCurrent = "true";
  setState("delivered");
  setStatus("Created one immutable Solver Card");
});

document.querySelector("[data-action='delivery-details']")?.addEventListener("click", () => setStatus("Delivery details opened · receipt SC-DEMO-00041"));
document.querySelector("[data-action='advanced']")?.addEventListener("click", () => { document.querySelector("[data-advanced-disclosure]")?.setAttribute("open", ""); setStatus("Advanced mapping and delivery details opened"); });
document.querySelector("[data-action='view-source']")?.addEventListener("click", () => setStatus("View source material requested · Export keeps physical values read-only"));
document.querySelector("[data-action='open-fit']")?.addEventListener("click", () => setStatus("Open full graph requested · Fit source identity remains pinned"));

document.querySelectorAll("[data-stage]").forEach((button) => button.addEventListener("click", () => setStatus(`${button.textContent} stage selected · Export source context remains available`)));

document.querySelector("[data-action='toggle-properties']")?.addEventListener("click", (event) => {
  const button = event.currentTarget;
  const expanded = button.getAttribute("aria-expanded") === "true";
  button.setAttribute("aria-expanded", String(!expanded));
  button.querySelector("span")?.replaceChildren(document.createTextNode(expanded ? "›" : "‹"));
  if (propertiesPane) propertiesPane.hidden = expanded;
  divider?.classList.toggle("collapsed", expanded);
  setStatus(expanded ? "Export setup collapsed · native preview expanded" : "Export setup restored");
});

dividerResizer?.addEventListener("keydown", (event) => {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  const min = Number(dividerResizer.getAttribute("aria-valuemin") || 300);
  const max = Number(dividerResizer.getAttribute("aria-valuemax") || 360);
  const current = Number(dividerResizer.getAttribute("aria-valuenow") || 320);
  const value = event.key === "Home" ? min : event.key === "End" ? max : Math.max(min, Math.min(max, current + (event.key === "ArrowRight" ? 8 : -8)));
  dividerResizer.setAttribute("aria-valuenow", String(value));
  document.documentElement.style.setProperty("--export-setup-width", `${value}px`);
  setStatus(`Export setup resized to ${value} px`);
});

mappingScroll?.addEventListener("keydown", (event) => {
  const delta = event.key === "PageDown" || event.key === "ArrowDown" ? mappingScroll.clientHeight * .8 : event.key === "PageUp" || event.key === "ArrowUp" ? -mappingScroll.clientHeight * .8 : event.key === "End" ? mappingScroll.scrollHeight : event.key === "Home" ? -mappingScroll.scrollHeight : 0;
  if (!delta) return;
  event.preventDefault();
  mappingScroll.scrollBy({ top: delta, behavior: "instant" });
  setStatus("Mapping details scrolled locally");
});
mappingScroll?.addEventListener("scroll", syncScrollCues, { passive: true });

nativeScroll?.addEventListener("keydown", (event) => {
  if (!["PageDown", "PageUp", "ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
  setStatus("Native preview scrolled locally");
});
nativeScroll?.addEventListener("scroll", syncScrollCues, { passive: true });

document.querySelectorAll("[data-mode]").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll("[data-mode]").forEach((candidate) => candidate.classList.toggle("active", candidate === button));
  setText("[data-fit-copy]", `Ogden N=1 + shear Prony · ${button.textContent} response`);
  setStatus(`${button.textContent} Fit source mode selected · graph quantity remains family-specific`);
}));

const initialState = params.get("state") || body.dataset.state || "preview-ready";
renderFamily();
setState(initialState);
