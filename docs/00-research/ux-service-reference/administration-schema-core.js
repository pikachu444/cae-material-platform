(() => {
  "use strict";

  const TABLES = [
    { id: "materials", name: "Materials master", detail: "Engineering material data", revision: "12", description: "Published material definitions available to governed catalog users.", attributes: "12", layouts: "1", subsets: "2" },
    { id: "conditions", name: "Test conditions", detail: "Measurement context", revision: "8", description: "Temperature, environment and test-method context for a result.", attributes: "5", layouts: "1", subsets: "1" },
    { id: "sources", name: "Source references", detail: "Traceable provenance", revision: "4", description: "References that explain where an imported or entered value came from.", attributes: "4", layouts: "1", subsets: "0" },
    { id: "aliases", name: "Solver aliases", detail: "Delivery vocabulary", revision: "3", description: "Stable names used when building a solver card for a model.", attributes: "3", layouts: "0", subsets: "1" },
    { id: "batches", name: "Batch runs", detail: "Import and review work", revision: "2", description: "Governed batch activity associated with a set of records.", attributes: "6", layouts: "0", subsets: "0" }
  ];
  const ATTRIBUTES = [
    { id: "density", name: "Density", detail: "number · mass per volume", type: "number", revision: "5", revisionId: "11111111-1111-4111-8111-111111111111", description: "Mass density used in the selected material model." },
    { id: "yield-strength", name: "Yield strength", detail: "number · stress", type: "number", revision: "7", revisionId: "33333333-3333-4333-8333-333333333333", description: "Onset of plastic response at the recorded condition." },
    { id: "material-condition", name: "Material condition", detail: "discrete · controlled choice", type: "discrete", revision: "3", revisionId: "55555555-5555-4555-8555-555555555555", description: "Controlled condition label for a material record." },
    { id: "source-reference", name: "Source reference", detail: "record reference", type: "record-reference", revision: "4", revisionId: "88888888-8888-4888-8888-888888888888", description: "Provenance reference associated with the current value." },
    { id: "test-method", name: "Test method", detail: "text", type: "text", revision: "4", revisionId: "66666666-6666-4666-8666-666666666666", description: "Method identifier supplied by the test engineer." },
    { id: "measurement-date", name: "Measurement date", detail: "date", type: "date", revision: "2", revisionId: "77777777-7777-4777-8777-777777777777", description: "Date on which the test measurement was recorded." },
    { id: "youngs-modulus", name: "Young's modulus", detail: "number · stress", type: "number", revision: "6", revisionId: "22222222-2222-4222-8222-222222222222", description: "Elastic modulus recorded for the selected material condition." },
    { id: "poisson-ratio", name: "Poisson ratio", detail: "number · dimensionless", type: "number", revision: "4", revisionId: "44444444-4444-4444-8444-444444444444", description: "Elastic lateral contraction ratio for the selected material." },
    { id: "test-temperature", name: "Test temperature", detail: "number · temperature", type: "number", revision: "3", revisionId: "99999999-9999-4999-8999-999999999999", description: "Temperature at which the synthetic response was recorded." },
    { id: "test-direction", name: "Test direction", detail: "discrete · controlled choice", type: "discrete", revision: "2", revisionId: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", description: "Controlled direction label for the response measurement." },
    { id: "specimen-thickness", name: "Specimen thickness", detail: "number · length", type: "number", revision: "3", revisionId: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", description: "Nominal specimen thickness retained with the test context." },
    { id: "hardness", name: "Hardness", detail: "number · hardness", type: "number", revision: "2", revisionId: "abababab-abab-4aba-8aba-abababababab", description: "Synthetic hardness value retained with the material condition." },
    { id: "representative-response", name: "Representative response", detail: "curve · linked Artifact", type: "curve", revision: "2", revisionId: "cccccccc-cccc-4ccc-8ccc-cccccccccccc", description: "Saved engineering response curve linked to an immutable Artifact." }
  ];
  const ATTRIBUTE_DRAFTS = {
    density: {
      attributeName: "Density",
      quantity: "mass per volume",
      standardUnit: "kg/m³",
      minimum: "500",
      maximum: "9000",
      entryGuidance: "Enter the measured mass density at the selected test condition.",
      allowedChoices: "Annealed\nNormalized\nQuenched and tempered",
      relatedTable: "Source references",
      maxLength: "120",
      pattern: ""
    },
    "material-condition": {
      attributeName: "Material condition",
      quantity: "",
      standardUnit: "",
      minimum: "",
      maximum: "",
      entryGuidance: "Choose the controlled material condition recorded for this material.",
      allowedChoices: "Annealed\nNormalized\nQuenched and tempered",
      relatedTable: "Source references",
      maxLength: "",
      pattern: ""
    },
    "source-reference": {
      attributeName: "Source reference",
      quantity: "",
      standardUnit: "",
      minimum: "",
      maximum: "",
      entryGuidance: "Link the Source references Record that supports this entered value.",
      allowedChoices: "",
      relatedTable: "Source references",
      maxLength: "",
      pattern: ""
    },
    "test-method": {
      attributeName: "Test method",
      quantity: "",
      standardUnit: "",
      minimum: "",
      maximum: "",
      entryGuidance: "Enter the method identifier used by the test engineer.",
      allowedChoices: "",
      relatedTable: "Source references",
      maxLength: "120",
      pattern: ""
    }
  };
  const GENERIC_OBJECTS = {
    layouts: [
      { id: "material-layout", name: "Material datasheet", detail: "read and edit layout", revision: "6", description: "Record entry layout for materials master." },
      { id: "condition-layout", name: "Condition entry", detail: "read and edit layout", revision: "2", description: "Entry layout for test conditions." },
      { id: "source-layout", name: "Source trace", detail: "read-only layout", revision: "1", description: "Reference display for source records." }
    ],
    subsets: [
      { id: "metals", name: "Metals", detail: "materials filter", revision: "3", description: "Subset of materials used for metallic models." },
      { id: "room-temperature", name: "Room temperature", detail: "conditions filter", revision: "2", description: "Conditions at the standard ambient test point." },
      { id: "solver-ready", name: "Solver-ready", detail: "delivery filter", revision: "2", description: "Records with a selected model and approved mapping." },
      { id: "recent-imports", name: "Recent imports", detail: "batch filter", revision: "1", description: "Records from the latest governed import batch." }
    ],
    links: [
      { id: "material-source", name: "Material → Source", detail: "record relationship", revision: "2", description: "Connects a material record to its traceable source." },
      { id: "material-condition", name: "Material → Condition", detail: "record relationship", revision: "2", description: "Connects a material record to a measured condition." }
    ]
  };
  const PREVIEW_FIELDS = [
    { id: "density", name: "Density", type: "Number", value: "7,800", unit: "kg/m³", condition: "Ambient · as received", detail: "mass density", revision: "5", revisionId: "11111111-1111-4111-8111-111111111111" },
    { id: "youngs-modulus", name: "Young's modulus", type: "Number", value: "210,000", unit: "MPa", condition: "Ambient · as received", detail: "stress", revision: "6", revisionId: "22222222-2222-4222-8222-222222222222" },
    { id: "yield-strength", name: "Yield strength", type: "Number", value: "450", unit: "MPa", condition: "Ambient · as received", detail: "stress", revision: "7", revisionId: "33333333-3333-4333-8333-333333333333" },
    { id: "poisson-ratio", name: "Poisson ratio", type: "Number", value: "0.30", unit: "—", condition: "Ambient · as received", detail: "dimensionless", revision: "4", revisionId: "44444444-4444-4444-8444-444444444444" },
    { id: "material-condition", name: "Material condition", type: "Discrete choice", value: "As received", unit: "—", condition: "Recorded condition", detail: "controlled condition", revision: "3", revisionId: "55555555-5555-4555-8555-555555555555" },
    { id: "test-method", name: "Test method", type: "Text", value: "Ambient tensile reference", unit: "—", condition: "Method identifier", detail: "method identifier", revision: "4", revisionId: "66666666-6666-4666-8666-666666666666" },
    { id: "measurement-date", name: "Measurement date", type: "Date", value: "2026-07-24", unit: "—", condition: "Recorded date", detail: "measurement date", revision: "2", revisionId: "77777777-7777-4777-8777-777777777777" },
    { id: "hardness", name: "Hardness", type: "Number", value: "220", unit: "HV", condition: "Ambient · as received", detail: "hardness", revision: "2", revisionId: "abababab-abab-4aba-8aba-abababababab" },
    { id: "test-temperature", name: "Test temperature", type: "Number", value: "23", unit: "°C", condition: "Ambient · as received", detail: "temperature", revision: "3", revisionId: "99999999-9999-4999-8999-999999999999" },
    { id: "test-direction", name: "Test direction", type: "Discrete choice", value: "Rolling direction", unit: "—", condition: "Specimen orientation", detail: "controlled direction", revision: "2", revisionId: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa" },
    { id: "specimen-thickness", name: "Specimen thickness", type: "Number", value: "1.20", unit: "mm", condition: "Nominal specimen", detail: "length", revision: "3", revisionId: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb" },
    { id: "representative-response", name: "Representative response", type: "Curve / table artifact", value: "Saved linked Artifact", unit: "Engineering strain / stress", condition: "Ambient · as received", detail: "saved curve Artifact", revision: "2", revisionId: "cccccccc-cccc-4ccc-8ccc-cccccccccccc", artifactId: "dddddddd-dddd-4ddd-8ddd-dddddddddddd", artifactSha256: "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd" }
  ];
  const PREVIEW_LAYOUT_BY_TABLE = {
    materials: "material-layout",
    conditions: "condition-layout",
    sources: "source-layout"
  };
  const PREVIEW_RECORD = {
    name: "DP780 synthetic demo steel",
    revision: "1",
    table: "Materials master",
    revisionId: "ffffffff-ffff-4fff-8fff-ffffffffffff",
    tableRevisionId: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
    values: Object.fromEntries(PREVIEW_FIELDS.map((field) => [field.id, { value: field.value, unit: field.unit, condition: field.condition, detail: field.detail, dataType: field.type, attributeDefinitionRevisionId: field.revisionId, ...(field.artifactId ? { artifactId: field.artifactId, artifactSha256: field.artifactSha256 } : {}) }]))
  };
  const familyLabels = { tables: "Tables", attributes: "Attributes", layouts: "Layouts", subsets: "Subsets", links: "Link Types" };
  const familyCounts = { tables: 5, attributes: 18, layouts: 3, subsets: 4, links: 2 };
  const attributeTypeLabels = {
    number: "Number",
    discrete: "Discrete choice",
    "record-reference": "Record reference",
    text: "Text",
    date: "Date",
    curve: "Curve / table artifact"
  };

  const params = new URLSearchParams(window.location.search);
  let state = params.get("state") || document.body.dataset.state || "normal";
  const requestedPreviewOpen = params.get("preview") === "open";
  const requestedProjection = params.get("projection") === "layout" ? "layout" : "record";
  const requestedPreviewField = params.get("field") || "";
  document.body.dataset.state = state;

  const refs = {
    workspace: document.querySelector("[data-workspace]"),
    list: document.querySelector("[data-object-list]"),
    listHeading: document.querySelector("[data-list-heading]"),
    listCount: document.querySelector("[data-list-count]"),
    listColumns: document.querySelector("[data-list-columns]"),
    listEmpty: document.querySelector("[data-list-empty]"),
    listLoading: document.querySelector("[data-list-loading]"),
    editor: document.querySelector("[data-editor-scroll]"),
    editorScrollRail: document.querySelector("[data-editor-scroll-rail]"),
    editorScrollThumb: document.querySelector("[data-editor-scroll-thumb]"),
    editorPane: document.querySelector("[data-pane=editor]"),
    previewPanel: document.querySelector("[data-preview-panel]"),
    previewScroll: document.querySelector("[data-preview-scroll]"),
    previewPlotBand: document.querySelector("[data-preview-plot-band]"),
    previewCommand: document.querySelector("[data-preview-command]"),
    currentTable: document.querySelector("[data-current-table]"),
    currentTableWrap: document.querySelector("[data-current-table-wrap]"),
    taskStatus: document.querySelector("[data-task-status]"),
    statusSelection: document.querySelector("[data-status-selection]"),
    statusScope: document.querySelector("[data-status-scope]"),
    statusScroll: document.querySelector("[data-status-scroll]"),
    navCount: document.querySelector("[data-nav-count]"),
    addObject: document.querySelector("[data-add-object]")
  };
  const model = {
    objectKind: state.startsWith("attribute") ? "attributes" : "tables",
    selectedTable: "materials",
    selectedObject: state.startsWith("attribute") ? "density" : "materials",
    draft: {
      tableName: "Materials master",
      tableDescription: "Published material definitions available to governed catalog users.",
      tableReason: "",
      attributeReason: "",
      required: true,
      newTableName: "Model calibration records",
      newTableKey: "model_calibration_records",
      newTableDescription: "Saved model-calibration branches linked to their exact engineering inputs.",
      newTableReason: "Add a governed place for model-calibration records.",
      newAttributeName: "Fit method",
      newAttributeKey: "fit_method",
      newAttributeType: "Discrete choice",
      newAttributeChoices: "Swift\nVoce\nSwift / Voce blend",
      newAttributeGuidance: "Choose the method used for this saved model branch.",
      newAttributeReason: "Capture the selected fitting method on each saved record.",
      ...ATTRIBUTE_DRAFTS.density
    },
    saving: state === "table-saving" || state === "attribute-saving",
    dirty: ["table-add", "table-draft", "table-save-error", "attribute-add", "attribute-draft", "attribute-save-error", "attribute-long-invalid", "stale-conflict"].includes(state),
    selectedLayout: PREVIEW_LAYOUT_BY_TABLE.materials,
    previewOpen: requestedPreviewOpen,
    previewProjection: requestedProjection,
    previewFieldId: requestedPreviewField,
    previewInvoker: null,
    errors: {}
  };
  if (state === "table-save-error") model.errors.tableSave = true;
  if (state === "attribute-save-error") model.errors.attributeSave = true;
  if (state === "attribute-long-invalid" || state === "attribute-discrete") model.selectedObject = "material-condition";
  if (state === "attribute-reference") model.selectedObject = "source-reference";
  if (state === "attribute-text") model.selectedObject = "test-method";
  if (ATTRIBUTE_DRAFTS[model.selectedObject]) Object.assign(model.draft, ATTRIBUTE_DRAFTS[model.selectedObject]);
  if (state === "attribute-long-invalid") {
    model.selectedObject = "material-condition";
    model.draft.attributeName = "Material condition — controlled vocabulary for heat treatment, processing route and test-stage context";
    model.draft.allowedChoices = "Annealed after solution treatment — verify furnace record and cooling route\nNormalized after hot forming — retain the full route description in the source record\nQuenched and tempered, laboratory-confirmed — include tempering temperature in the entry guidance\nAs-received production condition — do not infer treatment from the alloy designation";
    model.draft.entryGuidance = "Use the exact condition stated on the test certificate, including the processing route, thermal history, cooling medium, tempering temperature and any laboratory qualifier. This guidance is intentionally long to validate local editor scrolling and adjacent field errors.";
    model.draft.attributeReason = "";
    model.errors.allowedChoices = "Each choice must be 80 characters or fewer.";
    model.errors.entryGuidance = "Entry guidance must be 240 characters or fewer.";
    model.errors.attributeReason = "Change reason is required before saving.";
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character]));
  }
  function setTaskStatus(text) { if (refs.taskStatus) refs.taskStatus.textContent = text; }
  function currentTable() { return TABLES.find((table) => table.id === model.selectedTable) || TABLES[0]; }
  function selectedAttribute() { return ATTRIBUTES.find((attribute) => attribute.id === model.selectedObject) || ATTRIBUTES[0]; }
  function materialAttributes() {
    // Keep the existing out-of-layout Source reference available only in its
    // dedicated reference-state fixture; the normal wide catalog exposes the
    // twelve fields defined by the active Material layout.
    return state === "attribute-reference" ? ATTRIBUTES : ATTRIBUTES.filter((attribute) => attribute.id !== "source-reference");
  }
  function objectsForKind(kind) {
    if (kind === "tables") return TABLES;
    if (kind === "attributes") return model.selectedTable === "materials" ? materialAttributes() : ATTRIBUTES.slice(0, 4);
    return GENERIC_OBJECTS[kind] || [];
  }
  function setFamilySelection(kind) {
    model.objectKind = kind;
    const objects = objectsForKind(kind);
    if (!objects.some((object) => object.id === model.selectedObject)) model.selectedObject = objects[0]?.id || "";
    document.querySelectorAll("[data-object-kind]").forEach((button) => {
      const selected = button.dataset.objectKind === kind;
      button.classList.toggle("is-selected", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
    if (kind === "tables") model.selectedTable = model.selectedObject || "materials";
    if (kind === "layouts") model.selectedLayout = model.selectedObject || "material-layout";
    render();
  }
  function selectedListObject() { return objectsForKind(model.objectKind).find((object) => object.id === model.selectedObject) || objectsForKind(model.objectKind)[0]; }
  function selectedLayoutObject() { return GENERIC_OBJECTS.layouts.find((layout) => layout.id === model.selectedLayout) || GENERIC_OBJECTS.layouts[0]; }
  function previewLayoutId() {
    if (model.objectKind === "layouts" && GENERIC_OBJECTS.layouts.some((layout) => layout.id === model.selectedObject)) return model.selectedObject;
    return PREVIEW_LAYOUT_BY_TABLE[model.selectedTable] || model.selectedLayout;
  }
  function previewLayoutFields(layoutId) { return layoutId === "material-layout" ? PREVIEW_FIELDS : []; }
  function isExistingAttributeDraft() {
    return ["attribute-draft", "attribute-saving", "attribute-save-error", "attribute-long-invalid", "attribute-discrete", "attribute-reference", "attribute-text"].includes(state);
  }
  function previewSelectedAttributeId() {
    return model.objectKind === "attributes" && state !== "attribute-add" ? model.selectedObject : "";
  }
  function previewAttributeLabel(field) {
    return field.name;
  }
  function previewHasSavedRecord() { return state !== "empty" && state !== "table-add" && model.selectedTable === "materials"; }
  function previewHasAvailableProjection() { return state !== "empty" && state !== "table-add"; }

  function niceStep(roughStep, factors) {
    const exponent = Math.floor(Math.log10(roughStep));
    const candidates = [];
    for (let power = exponent - 1; power <= exponent + 3; power += 1) factors.forEach((factor) => candidates.push(factor * 10 ** power));
    return Math.min(...candidates.filter((candidate) => candidate >= roughStep - 1e-12));
  }
  function deriveAxis(minimum, maximum, ratio, intervals, factors) {
    const paddedMaximum = maximum + (maximum - minimum) * ratio;
    const step = niceStep((paddedMaximum - minimum) / intervals, factors);
    return { paddedMaximum, niceStep: step, domainMaximum: Math.ceil(paddedMaximum / step - 1e-12) * step };
  }
  function renderCurveGraph() {
    const plot = document.querySelector("[data-preview-plot]");
    const frame = plot?.closest("[data-preview-plot-frame]");
    if (!plot || !frame) return;
    const box = plot.getBoundingClientRect();
    const width = box.width;
    const height = box.height;
    if (width < 1 || height < 1) return;
    const svgNamespace = "http://www.w3.org/2000/svg";
    const sourcePlot = { left: 64, right: 732, top: 27, bottom: 191 };
    const curveSegments = [
      { controls: [{ x: 76, y: 123 }, { x: 94.4, y: 95.8 }], end: { x: 128, y: 83.8 } },
      { controls: [{ x: 175.2, y: 67.8 }, { x: 241.6, y: 63 }], end: { x: 313.6, y: 59.8 } },
      { controls: [{ x: 407.2, y: 55.8 }, { x: 505.6, y: 53.4 }], end: { x: 598.4, y: 51.6 } }
    ];
    const create = (name, attributes = {}) => {
      const element = document.createElementNS(svgNamespace, name);
      Object.entries(attributes).forEach(([attribute, value]) => element.setAttribute(attribute, String(value)));
      return element;
    };
    const domains = {
      strain: deriveAxis(0, 0.2, 0.1, 5, [1, 2, 2.5, 5, 10]),
      stress: deriveAxis(0, 850, 0.1, 4, [1, 2, 2.5, 5, 10])
    };
    const margin = { left: 78, right: 24, top: 28, bottom: 54 };
    const area = { left: margin.left, right: width - margin.right, top: margin.top, bottom: height - margin.bottom };
    area.width = area.right - area.left;
    area.height = area.bottom - area.top;
    if (area.width <= 0 || area.height <= 0) return;
    const mapSourcePoint = (point) => {
      const strain = ((point.x - sourcePlot.left) / (sourcePlot.right - sourcePlot.left)) * 0.25;
      const stress = ((sourcePlot.bottom - point.y) / (sourcePlot.bottom - sourcePlot.top)) * 1000;
      return { x: area.left + (strain / domains.strain.domainMaximum) * area.width, y: area.bottom - (stress / domains.stress.domainMaximum) * area.height };
    };
    const grid = create("g", { class: "preview-plot-grid", "aria-hidden": "true" });
    const axes = create("g", { class: "preview-plot-axis", "aria-hidden": "true" });
    const labels = create("g", { class: "preview-plot-labels" });
    Array.from({ length: 6 }, (_, index) => index * 0.05).forEach((value) => {
      const x = area.left + (value / domains.strain.domainMaximum) * area.width;
      grid.appendChild(create("line", { x1: x, y1: area.top, x2: x, y2: area.bottom }));
      const label = create("text", { x, y: area.bottom + 18, "text-anchor": value === 0 ? "start" : value === domains.strain.domainMaximum ? "end" : "middle", "data-tick": "x" });
      label.textContent = value === 0 ? "0" : value.toFixed(2);
      labels.appendChild(label);
    });
    Array.from({ length: 5 }, (_, index) => index * 250).forEach((value) => {
      const y = area.bottom - (value / domains.stress.domainMaximum) * area.height;
      grid.appendChild(create("line", { x1: area.left, y1: y, x2: area.right, y2: y }));
      const label = create("text", { x: area.left - 10, y: y + 4, "text-anchor": "end", "data-tick": "y" });
      label.textContent = value.toLocaleString("en-US");
      labels.appendChild(label);
    });
    axes.appendChild(create("line", { x1: area.left, y1: area.bottom, x2: area.right, y2: area.bottom }));
    axes.appendChild(create("line", { x1: area.left, y1: area.top, x2: area.left, y2: area.bottom }));
    const xTitle = create("text", { class: "axis-title", x: area.left + area.width / 2, y: height - 11, "text-anchor": "middle", "data-axis-title": "x" });
    xTitle.textContent = "Engineering strain";
    labels.appendChild(xTitle);
    const yTitle = create("text", { class: "axis-title", transform: `translate(17 ${area.top + area.height / 2}) rotate(-90)`, "text-anchor": "middle", "data-axis-title": "y" });
    yTitle.textContent = "Engineering stress (MPa)";
    labels.appendChild(yTitle);
    const start = mapSourcePoint({ x: sourcePlot.left, y: sourcePlot.bottom });
    const pathParts = [`M ${start.x} ${start.y}`];
    curveSegments.forEach((segment) => {
      const controlOne = mapSourcePoint(segment.controls[0]);
      const controlTwo = mapSourcePoint(segment.controls[1]);
      const end = mapSourcePoint(segment.end);
      pathParts.push(`C ${controlOne.x} ${controlOne.y}, ${controlTwo.x} ${controlTwo.y}, ${end.x} ${end.y}`);
    });
    const response = create("path", { class: "preview-response-line", d: pathParts.join(" ") });
    plot.setAttribute("viewBox", `0 0 ${width} ${height}`);
    plot.dataset.renderedWidth = Number(width.toFixed(2));
    plot.dataset.renderedHeight = Number(height.toFixed(2));
    plot.dataset.plotLeft = Number(area.left.toFixed(2));
    plot.dataset.plotRight = Number(area.right.toFixed(2));
    plot.dataset.plotTop = Number(area.top.toFixed(2));
    plot.dataset.plotBottom = Number(area.bottom.toFixed(2));
    plot.dataset.axisMaxStrain = Number(domains.strain.domainMaximum.toFixed(4));
    plot.dataset.axisMaxStressMpa = Number(domains.stress.domainMaximum.toFixed(2));
    plot.replaceChildren(plot.querySelector("title"), plot.querySelector("desc"), grid, axes, response, labels);
    const pathBox = response.getBBox();
    plot.dataset.pathLeft = Number(pathBox.x.toFixed(2));
    plot.dataset.pathRight = Number((pathBox.x + pathBox.width).toFixed(2));
    plot.dataset.pathTop = Number(pathBox.y.toFixed(2));
    plot.dataset.pathBottom = Number((pathBox.y + pathBox.height).toFixed(2));
    if (window.ResizeObserver) {
      model.previewGraphObserver?.disconnect();
      model.previewGraphObserver = new ResizeObserver(() => renderCurveGraph());
      model.previewGraphObserver.observe(frame);
    }
  }

  function bindPreviewTableRails() {
    document.querySelectorAll("[data-preview-values-scroll], [data-preview-layout-scroll]").forEach((scroll, index) => {
      if (window.innerWidth < 2400) {
        const scrollBox = scroll.getBoundingClientRect();
        const completeRows = [...scroll.querySelectorAll("thead tr, tbody tr")].filter((row) => {
          const rowBox = row.getBoundingClientRect();
          return rowBox.bottom <= scrollBox.bottom + .01;
        });
        const lastCompleteRow = completeRows.at(-1)?.getBoundingClientRect();
        if (lastCompleteRow && lastCompleteRow.bottom < scrollBox.bottom) {
          scroll.style.height = `${lastCompleteRow.bottom - scrollBox.top}px`;
        }
      }
      let region = scroll.closest("[data-preview-table-region]");
      if (!region) {
        region = document.createElement("div");
        region.className = "preview-table-region";
        region.dataset.previewTableRegion = "";
        scroll.before(region);
        region.append(scroll);
      }
      let rail = region?.querySelector("[data-preview-table-rail]");
      let thumb = region?.querySelector("[data-preview-table-thumb]");
      if (region && (!rail || !thumb)) {
        const newRail = document.createElement("div");
        const newThumb = document.createElement("span");
        const scrollId = scroll.id || `preview-table-scroll-${index}`;
        scroll.id = scrollId;
        scroll.dataset.previewTableScroll = "";
        newRail.className = "preview-table-rail";
        newRail.dataset.previewTableRail = "";
        newRail.setAttribute("role", "scrollbar");
        newRail.setAttribute("aria-label", scroll.getAttribute("aria-label") || "Scroll preview table");
        newRail.setAttribute("aria-controls", scrollId);
        newRail.setAttribute("aria-orientation", "vertical");
        newRail.setAttribute("aria-valuemin", "0");
        newRail.tabIndex = 0;
        newThumb.className = "preview-table-thumb";
        newThumb.dataset.previewTableThumb = "";
        newThumb.setAttribute("aria-hidden", "true");
        newRail.append(newThumb);
        region.append(newRail);
        rail = region.querySelector("[data-preview-table-rail]");
        thumb = region.querySelector("[data-preview-table-thumb]");
      }
      if (!region || !rail || !thumb) return;
      const update = () => {
        const maximum = Math.max(0, scroll.scrollHeight - scroll.clientHeight);
        rail.hidden = maximum === 0;
        rail.setAttribute("aria-valuemax", String(Math.round(maximum)));
        rail.setAttribute("aria-valuenow", String(Math.round(scroll.scrollTop)));
        if (!maximum) return;
        const height = Math.max(22, Math.round((scroll.clientHeight / scroll.scrollHeight) * rail.clientHeight));
        const travel = Math.max(0, rail.clientHeight - height);
        thumb.style.height = `${height}px`;
        thumb.style.transform = `translateY(${Math.round((scroll.scrollTop / maximum) * travel)}px)`;
      };
      const setScroll = (next) => {
        scroll.scrollTop = Math.max(0, Math.min(scroll.scrollHeight - scroll.clientHeight, next));
        update();
      };
      scroll.addEventListener("scroll", update, { passive: true });
      rail.addEventListener("wheel", (event) => { event.preventDefault(); setScroll(scroll.scrollTop + event.deltaY); }, { passive: false });
      rail.addEventListener("keydown", (event) => {
        const page = Math.max(36, Math.round(scroll.clientHeight * .8));
        const steps = { ArrowUp: -28, ArrowDown: 28, PageUp: -page, PageDown: page };
        if (event.key === "Home") { event.preventDefault(); setScroll(0); }
        else if (event.key === "End") { event.preventDefault(); setScroll(scroll.scrollHeight); }
        else if (Object.prototype.hasOwnProperty.call(steps, event.key)) { event.preventDefault(); setScroll(scroll.scrollTop + steps[event.key]); }
      });
      rail.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        const track = rail.getBoundingClientRect();
        setScroll(((event.clientY - track.top) / Math.max(1, track.height)) * scroll.scrollHeight);
        rail.setPointerCapture?.(event.pointerId);
      });
      update();
    });
  }
  function renderPreview() {
    const open = model.previewOpen;
    const layoutId = previewLayoutId();
    const layout = GENERIC_OBJECTS.layouts.find((item) => item.id === layoutId) || selectedLayoutObject();
    const fields = previewLayoutFields(layoutId);
    const selectedId = previewSelectedAttributeId();
    const selectedInLayout = Boolean(selectedId && fields.some((field) => field.id === selectedId));
    const savedRecord = previewHasSavedRecord();
    const draftTable = state === "table-add";
    const projection = model.previewProjection === "layout" ? "layout" : "record";
    if (refs.editorPane) {
      refs.editorPane.classList.toggle("is-preview-hidden", !open);
      refs.editorPane.classList.toggle("is-preview-open", open);
    }
    document.body.classList.toggle("is-preview-open", open);
    if (refs.previewPanel) refs.previewPanel.hidden = !open;
    const graphSuppressedForRecovery = ["table-saving", "table-save-error"].includes(state);
    const curveField = fields.find((field) => field.id === "representative-response");
    const graphSelected = model.previewFieldId === "representative-response" && model.objectKind !== "attributes" && (!state.startsWith("attribute") || selectedId === "representative-response");
    const showGraph = open && projection === "record" && previewHasAvailableProjection() && savedRecord && Boolean(curveField) && graphSelected && !graphSuppressedForRecovery;
    if (refs.previewPlotBand) {
      refs.previewPlotBand.hidden = true;
      refs.previewPlotBand.replaceChildren();
    }
    if (refs.previewCommand) {
      refs.previewCommand.textContent = open ? "Close preview" : "Preview datasheet";
      refs.previewCommand.setAttribute("aria-expanded", String(open));
      refs.previewCommand.setAttribute("aria-label", open ? "Close preview" : "Preview datasheet");
    }
    if (!refs.previewScroll) return;
    if (!previewHasAvailableProjection()) {
      const isNewTable = state === "table-add";
      const title = isNewTable ? "No saved projection" : "No preview available";
      const note = isNewTable
        ? "This new Table has no saved Record or Layout projection yet. Save the Table, then configure its Layout."
        : "Create a Table, then configure its Layout to preview a saved Record.";
      refs.previewScroll.innerHTML = `<div class="preview-content" data-preview-content data-preview-projection="unavailable"><header class="preview-heading"><div><p class="preview-kicker">Preview datasheet</p><h2 id="datasheet-preview-title" data-preview-title>${title}</h2></div><button type="button" class="button text" data-action="preview-close">Back to editor</button></header><div class="preview-tabs" role="tablist" aria-label="Preview task"><button type="button" role="tab" aria-selected="true" class="preview-tab is-selected" data-action="preview-projection" data-projection="record">Record preview</button><button type="button" role="tab" aria-selected="false" class="preview-tab" data-action="preview-projection" data-projection="layout">Layout definition</button></div><p class="preview-empty" data-preview-note>${note}</p></div>`;
      return;
    }
    const contextRecord = savedRecord ? PREVIEW_RECORD.name : draftTable ? "No saved Record" : "Not available for this Table";
    const note = draftTable || !savedRecord
      ? "No Record preview until this Table is saved."
      : state.startsWith("attribute")
        ? "Saved values remain linked to this Layout. Unsaved Attribute changes stay in the editor draft."
        : "";
    const valueRows = savedRecord && fields.length
      ? fields.map((field) => {
        const selected = field.id === selectedId && selectedInLayout;
        const value = PREVIEW_RECORD.values[field.id];
        const displayValue = value?.value ? `${value.value}${value.unit && value.unit !== "—" ? ` ${value.unit}` : ""}` : "—";
        const artifactAttrs = field.artifactId ? ` data-artifact-id="${escapeHtml(field.artifactId)}" data-artifact-sha256="${escapeHtml(field.artifactSha256)}"` : "";
        return `<tr class="preview-row${selected ? " is-selected" : ""}" data-preview-row data-preview-field-id="${escapeHtml(field.id)}" data-preview-selected="${selected}" data-preview-attribute-revision-id="${escapeHtml(field.revisionId)}"${artifactAttrs}><th scope="row"><button type="button" class="preview-row-button" data-action="preview-field" data-preview-field="${escapeHtml(field.id)}"><strong>${escapeHtml(previewAttributeLabel(field))}</strong><small>Attribute revision ${escapeHtml(field.revision)}</small></button></th><td class="preview-value" data-preview-value>${escapeHtml(displayValue)}${field.artifactId ? "<small>Saved linked Artifact · read-only</small>" : ""}</td><td class="preview-condition">${escapeHtml(value?.condition || field.condition || "—")}</td></tr>`;
      }).join("")
      : "<tr><td colspan=\"3\" class=\"preview-empty\">No saved values are available for this Table.</td></tr>";
    const layoutRows = fields.length
      ? fields.map((field, index) => {
        const selected = field.id === selectedId && selectedInLayout;
        const artifactAttrs = field.artifactId ? ` data-artifact-id="${escapeHtml(field.artifactId)}" data-artifact-sha256="${escapeHtml(field.artifactSha256)}"` : "";
        return `<tr class="preview-row${selected ? " is-selected" : ""}" data-layout-field data-preview-field-id="${escapeHtml(field.id)}" data-preview-selected="${selected}" data-layout-ordinal="${index}" data-preview-attribute-revision-id="${escapeHtml(field.revisionId)}"${artifactAttrs}><td class="preview-order">${index + 1}</td><td><button type="button" class="preview-row-button" data-action="preview-field" data-preview-field="${escapeHtml(field.id)}"><strong>${escapeHtml(previewAttributeLabel(field))}</strong><small>Definition revision ${escapeHtml(field.revision)}</small></button></td><td>${escapeHtml(field.type)}</td></tr>`;
      }).join("")
      : "<tr><td colspan=\"3\" class=\"preview-empty\">This Layout has no synthetic fields yet.</td></tr>";
    const graphMarkup = `<section class="preview-section preview-graph-section" data-preview-graph-section aria-labelledby="preview-graph-title"><header class="preview-section-heading"><h3 id="preview-graph-title">Representative response</h3><span>Saved curve value · read-only</span></header><p class="preview-graph-note">Layout field · Representative response · linked Artifact value from the saved Record</p><div class="preview-plot-frame" data-preview-plot-frame><svg class="preview-plot" data-preview-plot viewBox="0 0 760 420" role="img" aria-labelledby="preview-plot-title preview-plot-description" data-series-min-strain="0.00" data-series-max-strain="0.20" data-series-min-stress-mpa="0" data-series-max-stress-mpa="850" data-axis-headroom-ratio="0.10" data-axis-target-intervals-strain="5" data-axis-target-intervals-stress="4" data-axis-nice-step-factors="1,2,2.5,5,10" data-axis-max-strain="0.25" data-axis-max-stress-mpa="1000" data-artifact-id="${escapeHtml(curveField?.artifactId || "")}" data-artifact-sha256="${escapeHtml(curveField?.artifactSha256 || "")}" data-curve-selected="${graphSelected}"><title id="preview-plot-title">DP780 representative engineering response</title><desc id="preview-plot-description">Saved linked Artifact value for the Representative response Layout field. Engineering stress rises through the synthetic DP780 response against engineering strain; the axes retain data-relative headroom.</desc></svg><div class="preview-plot-legend" aria-label="Plot legend"><span><span class="preview-legend-swatch" aria-hidden="true"></span>Representative response</span><span>Condition: Ambient · as received</span></div></div></section>`;
    const recordSection = `<section class="preview-section${projection === "record" ? " is-active" : ""}" data-preview-active-section data-preview-values-section aria-labelledby="preview-values-title"><header class="preview-section-heading"><h3 id="preview-values-title">Record preview</h3><span>${savedRecord ? `Saved Record · revision ${escapeHtml(PREVIEW_RECORD.revision)}` : "No saved Record"}</span></header><div class="preview-table-region" data-preview-table-region><div class="preview-table-scroll" data-preview-values-scroll tabindex="0" aria-label="Scroll saved Record values"><table class="preview-table" data-preview-values><thead><tr><th scope="col">Attribute</th><th scope="col">Value</th><th scope="col">Condition</th></tr></thead><tbody>${valueRows}</tbody></table></div></div></section>`;
    const layoutSection = `<section class="preview-section${projection === "layout" ? " is-active" : ""}" data-preview-active-section data-preview-layout-section aria-labelledby="preview-layout-title"><header class="preview-section-heading"><h3 id="preview-layout-title">Layout definition</h3><span>Ordered · exact revisions</span></header><div class="preview-table-region" data-preview-table-region><div class="preview-table-scroll" data-preview-layout-scroll tabindex="0" aria-label="Scroll ordered Layout definition"><table class="preview-table" data-preview-layout><thead><tr><th scope="col">#</th><th scope="col">Attribute</th><th scope="col">Type</th></tr></thead><tbody>${layoutRows}</tbody></table></div></div></section>`;
    refs.previewScroll.innerHTML = `<div class="preview-content" data-preview-content data-preview-projection="saved" data-preview-active-task="${projection}" data-layout-id="${escapeHtml(layout.id)}" data-layout-revision="${escapeHtml(layout.revision)}" data-layout-revision-id="eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee" data-record-revision="${escapeHtml(PREVIEW_RECORD.revision)}" data-record-revision-id="${escapeHtml(PREVIEW_RECORD.revisionId)}" data-record-table-revision-id="${escapeHtml(PREVIEW_RECORD.tableRevisionId)}"><header class="preview-heading"><div><p class="preview-kicker">Preview datasheet</p><h2 id="datasheet-preview-title" data-preview-title>${escapeHtml(layout.name)}</h2><p data-preview-subtitle>Layout · ${escapeHtml(layout.name)} · revision ${escapeHtml(layout.revision)} · ${fields.length} fields</p></div><button type="button" class="button text" data-action="preview-close">Back to editor</button></header><div class="preview-tabs" role="tablist" aria-label="Preview task"><button type="button" role="tab" class="preview-tab${projection === "record" ? " is-selected" : ""}" aria-selected="${projection === "record"}" data-action="preview-projection" data-projection="record">Record preview</button><button type="button" role="tab" class="preview-tab${projection === "layout" ? " is-selected" : ""}" aria-selected="${projection === "layout"}" data-action="preview-projection" data-projection="layout">Layout definition</button></div><div class="preview-context" data-preview-context><div class="preview-context-row"><span>Record</span><strong data-preview-record>${escapeHtml(contextRecord)}</strong></div><div class="preview-context-row"><span>Table</span><strong data-preview-table>${escapeHtml(currentTable().name)}</strong></div></div>${note ? `<p class="preview-empty" data-preview-note>${escapeHtml(note)}</p>` : ""}<div class="preview-sections" data-preview-sections>${projection === "record" ? recordSection + (showGraph ? graphMarkup : "") : layoutSection}</div></div>`;
    bindPreviewTableRails();
    if (showGraph) window.requestAnimationFrame(renderCurveGraph);
  }

  function listMetadata(kind, object) {
    if (kind === "attributes") return attributeTypeLabels[object.type] || object.type;
    if (kind === "layouts") return object.detail.includes("read-only") ? "Read-only layout" : "Entry layout";
    if (kind === "subsets") return "Saved filter";
    if (kind === "links") return "Record relationship";
    return "";
  }

  function renderList() {
    const kind = model.objectKind;
    const objects = state === "empty" && kind === "tables" ? [] : objectsForKind(kind);
    const identityOnly = kind === "tables";
    refs.listHeading.textContent = familyLabels[kind];
    refs.listCount.textContent = `${objects.length} ${objects.length === 1 ? "item" : "items"}`;
    refs.listColumns.classList.toggle("is-identity-only", identityOnly);
    refs.listColumns.innerHTML = identityOnly
      ? "<span>Name</span><span>Rev</span>"
      : `<span>Name</span><span>${kind === "attributes" ? "Value type" : "Kind"}</span><span>Rev</span>`;
    refs.listEmpty.hidden = objects.length !== 0;
    refs.listLoading.hidden = !["loading", "catalog-loading"].includes(state);
    refs.list.hidden = objects.length === 0;
    refs.list.innerHTML = objects.map((object) => {
      const selected = object.id === model.selectedObject;
      const displayName = object.name;
      const metadata = listMetadata(kind, object);
      return `<button type="button" class="object-row${selected ? " is-selected" : ""}${identityOnly ? " is-identity-only" : ""}" role="listitem" data-object-id="${escapeHtml(object.id)}" aria-pressed="${selected}" title="${escapeHtml(displayName)}" aria-label="${escapeHtml(displayName)}">
        <span class="object-name"><span class="object-primary-name" title="${escapeHtml(displayName)}">${escapeHtml(displayName)}</span></span>
        ${identityOnly ? "" : `<span class="object-definition">${escapeHtml(metadata)}</span>`}
        <span class="object-revision" aria-label="revision ${escapeHtml(object.revision)}">${escapeHtml(object.revision)}</span>
      </button>`;
    }).join("");
    refs.list.setAttribute("aria-label", `${familyLabels[kind]} list`);
  }

  function readOnlyTableEditor(table) {
    return `<div class="editor-content" data-editor-mode="table-readonly">
      <header class="editor-heading"><div><h2>${escapeHtml(table.name)}</h2><p>Current Table definition</p></div><span class="editor-state">Current definition</span></header>
      <dl class="definition-list">
        <div class="definition-row"><dt>Purpose</dt><dd>${escapeHtml(table.description)}</dd></div>
        <div class="definition-row"><dt>Attributes</dt><dd>${escapeHtml(table.attributes)} defined fields</dd></div>
        <div class="definition-row"><dt>Layouts</dt><dd>${escapeHtml(table.layouts)} entry layout${table.layouts === "1" ? "" : "s"}</dd></div>
        <div class="definition-row"><dt>Subsets</dt><dd>${escapeHtml(table.subsets)} scoped subset${table.subsets === "1" ? "" : "s"}</dd></div>
      </dl>
      <p class="next-step">Inspect the current definition or edit it as a new immutable revision.</p>
      <div class="editor-actions"><button type="button" class="button" data-action="edit-table">Edit Table</button><button type="button" class="button text" data-action="preview">Preview datasheet</button></div>
      <details class="advanced-disclosure"><summary>Advanced definition details</summary><p>Stable identity and exact revision metadata are available in Evidence.</p></details>
    </div>`;
  }

  function formInput(name, label, value, options = {}) {
    const required = options.required ? '<span class="required"> *</span>' : "";
    const error = model.errors[name];
    const described = `${name}-help${error ? ` ${name}-error` : ""}`;
    const control = options.textarea
      ? `<textarea id="${name}" name="${name}" rows="${options.rows || 3}" aria-describedby="${described}" autocomplete="off"${options.readonly ? " readonly" : ""}>${escapeHtml(value)}</textarea>`
      : options.select
        ? `<select id="${name}" name="${name}" aria-describedby="${described}"${options.disabled ? " disabled" : ""}>${options.select.map((item) => `<option${item === value ? " selected" : ""}>${escapeHtml(item)}</option>`).join("")}</select>`
        : `<input id="${name}" name="${name}" value="${escapeHtml(value)}" type="${options.type || "text"}" aria-describedby="${described}" autocomplete="off"${options.spellcheck === false ? ' spellcheck="false"' : ""}${options.readonly ? " readonly" : ""}${options.min !== undefined ? ` min="${options.min}"` : ""}${options.max !== undefined ? ` max="${options.max}"` : ""}>`;
    return `<div class="form-row"><label for="${name}">${label}${required}</label><div class="form-value${error ? " has-error" : ""}">${control}<p class="form-help" id="${name}-help">${escapeHtml(options.help || "")}</p>${error ? `<p class="form-error" id="${name}-error" role="alert">${escapeHtml(error)}</p>` : ""}</div></div>`;
  }

  function tableAddEditor() {
    return `<div class="editor-content" data-editor-mode="table-add">
      <header class="editor-heading is-dirty"><div><h2>New Table</h2><p>New governed record type · existing Tables remain unchanged</p></div><span class="editor-state">New definition</span></header>
      <form class="property-form" data-form="table-add">
        ${formInput("newTableName", "Table name", model.draft.newTableName, { required: true, help: "Shown to people choosing where to store a Record." })}
        ${formInput("newTableKey", "Reference key", model.draft.newTableKey, { required: true, spellcheck: false, help: "Stable key for this new Table identity." })}
        ${formInput("newTableDescription", "Purpose", model.draft.newTableDescription, { textarea: true, rows: 3, help: "State what records belong here; this appears in the property editor, not the Object list." })}
        ${formInput("newTableReason", "Change reason", model.draft.newTableReason, { required: true, help: "Recorded with immutable revision 1." })}
      </form>
      <p class="status-note"><strong>Creates revision 1.</strong> The new Table becomes available for typed Attributes, Layouts and Records after save.</p>
      <div class="editor-actions"><button type="button" class="button primary" data-action="save-new-table">Save new Table</button><button type="button" class="button" data-action="cancel-add">Cancel</button></div>
      <details class="advanced-disclosure"><summary>Advanced definition details</summary><p>Classification and exact identifiers remain in Administration evidence.</p></details>
    </div>`;
  }

  function attributeAddEditor() {
    const type = model.draft.newAttributeType;
    let fields = "";
    fields += formInput("newAttributeName", "Attribute name", model.draft.newAttributeName, { required: true, help: "Visible label used in Record entry and datasheets." });
    fields += formInput("newAttributeKey", "Reference key", model.draft.newAttributeKey, { required: true, spellcheck: false, help: "Stable key for this new Attribute identity." });
    fields += formInput("newAttributeType", "Value type", type, { required: true, select: ["Number", "Integer", "Text", "Boolean", "Date", "Discrete choice", "File artifact", "Curve / table artifact", "Record reference"], help: "Choose the stored value and validation behavior." });
    fields += `<div class="form-row"><label for="newAttributeRequired">Required when creating a record</label><div class="form-value"><label class="inline-check"><input id="newAttributeRequired" name="required" type="checkbox"${model.draft.required ? " checked" : ""}>Required for new records</label><p class="form-help" id="newAttributeRequired-help">Controls whether a new Record can be saved without this value.</p></div></div>`;
    if (type === "Number") {
      fields += formInput("quantity", "Quantity / meaning", model.draft.quantity, { required: true, help: "Engineering quantity represented by the number." });
      fields += formInput("standardUnit", "Standard unit", model.draft.standardUnit, { required: true, help: "Original and normalized unit semantics remain explicit." });
    } else if (type === "Discrete choice") {
      fields += formInput("newAttributeChoices", "Allowed choices", model.draft.newAttributeChoices, { textarea: true, rows: 4, required: true, help: "One stored choice per line." });
    } else if (type === "Record reference") {
      fields += formInput("relatedTable", "Related Table", model.draft.relatedTable, { select: ["Source references", "Materials master", "Test conditions"], required: true, help: "The saved value pins one exact target Record revision." });
    }
    fields += formInput("newAttributeGuidance", "Entry guidance", model.draft.newAttributeGuidance, { textarea: true, rows: 3, help: "Short help shown when a person enters this value." });
    fields += formInput("newAttributeReason", "Change reason", model.draft.newAttributeReason, { required: true, help: "Recorded with immutable revision 1." });
    return `<div class="editor-content" data-editor-mode="attribute-add">
      <header class="editor-heading is-dirty"><div><h2>New Attribute for ${escapeHtml(currentTable().name)}</h2><p>User-selected field · fields follow the chosen value type</p></div><span class="editor-state">New definition</span></header>
      <form class="property-form" data-form="attribute-add">${fields}</form>
      <p class="status-note"><strong>Creates revision 1.</strong> Add this Attribute to a Layout to make it visible in Record entry and the datasheet.</p>
      <div class="editor-actions"><button type="button" class="button primary" data-action="save-new-attribute">Save new Attribute</button><button type="button" class="button" data-action="cancel-add">Cancel</button></div>
      <details class="advanced-disclosure"><summary>Advanced definition details</summary><p>Exact revision identity and validation schema remain available in Evidence.</p></details>
    </div>`;
  }

  function tableDraftEditor() {
    const table = currentTable();
    const saveError = model.errors.tableSave ? '<div class="error-region" role="alert"><p>Save failed. The current Table is unchanged; every draft value and the change reason remain available.</p><button type="button" class="button" data-action="retry-save">Retry save</button></div>' : "";
    const savingNote = model.saving ? '<div class="status-note" role="status" aria-live="polite"><strong>Saving new revision…</strong> · duplicate submit is blocked while the response is pending.</div>' : "";
    return `<div class="editor-content" data-editor-mode="table-draft">
      <header class="editor-heading${model.dirty ? " is-dirty" : ""}"><div><h2>Edit ${escapeHtml(table.name)}</h2><p>Table draft · fields are local until a new revision is saved</p></div><span class="editor-state">${model.dirty ? "Draft changes" : "Based on current revision"}</span></header>
      ${saveError}${savingNote}
      <form class="property-form" data-form="table">
        ${formInput("tableName", "Table name", model.draft.tableName, { required: true, help: "Shown to catalog users and in Table selectors." })}
        ${formInput("tableReference", "Reference key", "Materials master", { readonly: true, help: "Stable identity; it does not change when a revision is saved." })}
        ${formInput("tableDescription", "Description", model.draft.tableDescription, { textarea: true, rows: 3, help: "Describe the decision or record scope in plain language." })}
        ${formInput("tableReason", "Change reason", model.draft.tableReason, { required: true, help: "Required to explain why this immutable revision is needed." })}
      </form>
      <p class="status-note"><strong>Based on current revision.</strong> Saving appends a new revision and leaves existing Records and history intact.</p>
      <div class="editor-actions"><button type="button" class="button primary" data-action="save-table"${model.saving ? " disabled" : ""}>Save new revision</button><button type="button" class="button" data-action="discard-draft">Discard draft</button></div>
      ${model.saving ? '<span class="save-disabled-reason" data-save-state>Saving in progress · submit is disabled.</span>' : ""}
      <details class="advanced-disclosure"><summary>Advanced revision details</summary><p>Exact revision and ETag values are available in Evidence when the request is sent.</p></details>
    </div>`;
  }

  function attrDraftEditor() {
    const attribute = selectedAttribute();
    const type = state === "attribute-long-invalid" ? "discrete" : attribute.type;
    const attrName = state === "attribute-long-invalid" ? model.draft.attributeName : model.draft.attributeName;
    const saveError = model.errors.attributeSave ? '<div class="error-region" role="alert"><p>Save failed. The Attribute definition is unchanged; all draft fields remain available.</p><button type="button" class="button" data-action="retry-save">Retry save</button></div>' : "";
    const savingNote = model.saving ? '<div class="status-note" role="status" aria-live="polite"><strong>Saving new revision…</strong> · duplicate submit is blocked while the response is pending.</div>' : "";
    const longSummary = state === "attribute-long-invalid" ? '<div class="invalid-summary" role="alert"><strong>3 invalid fields.</strong> Correct the highlighted values before saving; other draft values are preserved.</div>' : "";
    let fields = "";
    fields += formInput("attributeName", "Attribute name", attrName, { required: true, help: "Visible label for a Record entry field." });
    fields += formInput("attributeReference", "Reference key", attribute.name, { readonly: true, help: "Stable identity; immutable revisions share this key." });
    fields += formInput("attributeType", "Value type", type === "record-reference" ? "Record reference" : type === "discrete" ? "Discrete choice" : type === "text" ? "Text" : "Number", { readonly: true, help: "Existing definitions keep their value type." });
    fields += `<div class="form-row"><label for="attributeRequired">Required when creating a record</label><div class="form-value"><label class="inline-check"><input id="attributeRequired" name="required" type="checkbox"${model.draft.required ? " checked" : ""}>Required for new records</label><p class="form-help" id="attributeRequired-help">Controls whether a new Record can be saved without this value.</p></div></div>`;
    if (type === "number") {
      fields += formInput("quantity", "Quantity / meaning", model.draft.quantity, { required: true, help: "Engineering quantity represented by the number." });
      fields += formInput("standardUnit", "Standard unit", model.draft.standardUnit, { required: true, help: "Original unit text is retained with the normalized unit." });
      fields += `<div class="form-row"><label>Valid range</label><div class="form-value"><div class="range-fields"><div class="range-field"><label for="minimum">Minimum</label><input id="minimum" name="minimum" type="number" value="${escapeHtml(model.draft.minimum)}" aria-describedby="minimum-help"><p class="form-help" id="minimum-help">Optional lower bound.</p></div><div class="range-field"><label for="maximum">Maximum</label><input id="maximum" name="maximum" type="number" value="${escapeHtml(model.draft.maximum)}" aria-describedby="maximum-help"><p class="form-help" id="maximum-help">Optional upper bound.</p></div></div></div></div>`;
    } else if (type === "discrete") {
      fields += formInput("allowedChoices", "Allowed choices", model.draft.allowedChoices, { textarea: true, rows: state === "attribute-long-invalid" ? 7 : 3, required: true, help: "One controlled choice per line; no number-unit fields apply to this type." });
    } else if (type === "record-reference") {
      fields += formInput("relatedTable", "Related Table", model.draft.relatedTable, { select: ["Source references", "Materials master", "Test conditions"], required: true, help: "Record selection is scoped to this Table." });
    } else if (type === "text") {
      fields += formInput("maxLength", "Maximum length", model.draft.maxLength, { type: "number", help: "Optional contract-provided text limit." });
      fields += formInput("pattern", "Entry pattern", model.draft.pattern, { help: "Optional contract-provided validation pattern." });
    }
    fields += formInput("entryGuidance", "Entry guidance", model.draft.entryGuidance, { textarea: true, rows: state === "attribute-long-invalid" ? 7 : 3, help: "Short guidance appears beside the Record field." });
    fields += formInput("attributeReason", "Change reason", model.draft.attributeReason, { required: true, help: "Required before saving a new immutable revision." });
    const disableSave = model.saving || state === "attribute-long-invalid" || Boolean(model.errors.attributeSave);
    return `<div class="editor-content" data-editor-mode="attribute-draft">
      <header class="editor-heading${model.dirty ? " is-dirty" : ""}"><div><h2>${state === "attribute-long-invalid" ? "Review long Attribute definition" : `Edit ${escapeHtml(attribute.name)}`}</h2><p>Attribute draft · typed fields follow the existing definition</p></div><span class="editor-state">${model.dirty ? "Draft changes" : "Based on current revision"}</span></header>
      ${saveError}${savingNote}${longSummary}
      <form class="property-form" data-form="attribute">${fields}</form>
      <div class="editor-actions"><button type="button" class="button primary" data-action="save-attribute"${disableSave ? " disabled" : ""}>Save new revision</button><button type="button" class="button" data-action="discard-draft">Discard draft</button>${state === "attribute-long-invalid" ? '<span class="save-disabled-reason">Save disabled · correct the 3 invalid fields first.</span>' : ""}</div>
      <details class="advanced-disclosure"><summary>Advanced definition details</summary><p>Stable key, schema version and exact ETag values remain in Evidence.</p></details>
    </div>`;
  }

  function conflictEditor() {
    const table = currentTable();
    const conflict = `<div class="conflict-region" role="alert" tabindex="-1" data-conflict-region><strong>Newer Table definition detected</strong><p>Your local draft is preserved. Resolve the conflict before sending another revision request.</p><div class="conflict-actions"><button type="button" class="button primary" data-action="reload-current">Reload current</button><button type="button" class="button" data-action="keep-local">Keep local as new revision</button><button type="button" class="button text" data-action="cancel-conflict">Cancel</button></div></div>`;
    const form = tableDraftEditor();
    const wrapper = document.createElement("div");
    wrapper.innerHTML = form;
    const content = wrapper.firstElementChild;
    content.querySelector(".editor-actions")?.remove();
    content.insertAdjacentHTML("afterbegin", conflict);
    return content.outerHTML;
  }

  function emptyEditor() {
    return `<div class="editor-content"><header class="editor-heading"><div><h2>No Table selected</h2><p>Choose a Table when one is available.</p></div><span class="editor-state">Waiting for a Table</span></header><p class="next-step">Use Add Table to define the first governed Table in this workspace.</p><div class="editor-actions"><button type="button" class="button" data-action="add-object">Add Table</button></div></div>`;
  }

  function genericEditor(object) {
    return `<div class="editor-content"><header class="editor-heading"><div><h2>${escapeHtml(object?.name || "Schema object")}</h2><p>${escapeHtml(familyLabels[model.objectKind])} definition</p></div><span class="editor-state">Current definition</span></header><dl class="definition-list"><div class="definition-row"><dt>Purpose</dt><dd>${escapeHtml(object?.description || "No definition is available for this selection.")}</dd></div><div class="definition-row"><dt>Reference</dt><dd class="secondary">Stable identity is available in Evidence.</dd></div></dl><p class="next-step">Select Tables or Attributes to edit a governed definition.</p></div>`;
  }

  function updateEditorScrollRail() {
    const rail = refs.editorScrollRail;
    const thumb = refs.editorScrollThumb;
    if (!rail || !thumb) return;
    const maxScroll = Math.max(0, refs.editor.scrollHeight - refs.editor.clientHeight);
    const hasOverflow = maxScroll > 1;
    rail.hidden = !hasOverflow;
    rail.setAttribute("aria-valuemax", String(Math.round(maxScroll)));
    rail.setAttribute("aria-valuenow", String(Math.round(Math.min(maxScroll, refs.editor.scrollTop))));
    if (!hasOverflow) {
      thumb.style.height = "0px";
      thumb.style.transform = "translateY(0px)";
      return;
    }
    const trackHeight = rail.clientHeight;
    const proportionalHeight = Math.round(trackHeight * refs.editor.clientHeight / refs.editor.scrollHeight);
    const thumbHeight = Math.min(trackHeight, Math.max(48, proportionalHeight));
    const maxTravel = Math.max(0, trackHeight - thumbHeight);
    const thumbTop = maxScroll ? Math.round(maxTravel * refs.editor.scrollTop / maxScroll) : 0;
    thumb.style.height = `${thumbHeight}px`;
    thumb.style.transform = `translateY(${thumbTop}px)`;
  }

  function scheduleEditorScrollRailUpdate() {
    window.requestAnimationFrame(updateEditorScrollRail);
  }

  function renderEditor() {
    let content;
    if (state === "empty") content = emptyEditor();
    else if (state === "table-add") content = tableAddEditor();
    else if (state === "attribute-add") content = attributeAddEditor();
    else if (["table-draft", "table-saving", "table-save-error"].includes(state)) content = tableDraftEditor();
    else if (state === "stale-conflict") content = conflictEditor();
    else if (["attribute-draft", "attribute-saving", "attribute-save-error", "attribute-long-invalid", "attribute-discrete", "attribute-reference", "attribute-text"].includes(state)) content = attrDraftEditor();
    else {
      const object = selectedListObject();
      content = model.objectKind === "tables" ? readOnlyTableEditor(object || currentTable()) : genericEditor(object);
    }
    refs.editor.innerHTML = content;
    if (!["empty", "table-add", "attribute-add", "table-draft", "table-saving", "table-save-error", "stale-conflict", "attribute-draft", "attribute-saving", "attribute-save-error", "attribute-long-invalid", "attribute-discrete", "attribute-reference", "attribute-text"].includes(state) && ["catalog-error", "error"].includes(state)) {
      refs.editor.insertAdjacentHTML("afterbegin", '<div class="error-region" role="alert"><p>Catalog refresh failed. The last valid rows and selection remain available.</p><button type="button" class="button" data-action="retry-catalog">Retry</button></div>');
    }
    scheduleEditorScrollRailUpdate();
    renderPreview();
  }

  function render() {
    refs.currentTable.value = model.selectedTable;
    refs.currentTableWrap.hidden = state === "empty";
    document.querySelectorAll("[data-object-kind]").forEach((button) => {
      const selected = button.dataset.objectKind === model.objectKind;
      button.classList.toggle("is-selected", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
    refs.navCount.textContent = "5 types";
    refs.statusSelection.textContent = model.objectKind === "attributes" ? `Attributes · ${selectedAttribute()?.name || "none"}` : `${familyLabels[model.objectKind]} · ${selectedListObject()?.name || "none"}`;
    refs.statusScope.textContent = model.objectKind === "attributes" ? `Scoped to ${currentTable().name}` : "Table-scoped definitions";
    refs.statusScroll.textContent = state === "attribute-long-invalid" ? "Local editor scroll · validation" : "Local pane scrolling";
    const canAdd = state === "normal" && ["tables", "attributes"].includes(model.objectKind);
    refs.addObject.hidden = !canAdd;
    refs.addObject.textContent = model.objectKind === "attributes" ? "Add Attribute" : "Add Table";
    refs.addObject.setAttribute("aria-label", refs.addObject.textContent);
    renderList();
    renderEditor();
    document.body.dataset.state = state;
  }

  function updateDraft(name, value) {
    if (name === "required") model.draft.required = value;
    else if (Object.prototype.hasOwnProperty.call(model.draft, name)) model.draft[name] = value;
    model.dirty = true;
    if (model.errors[name] && value.trim()) delete model.errors[name];
    renderEditor();
    const control = document.getElementById(name);
    if (control) { control.focus(); control.setSelectionRange?.(control.value.length, control.value.length); }
  }

  function validateBeforeSave(kind) {
    if (kind === "table") {
      if (!model.draft.tableName.trim()) model.errors.tableName = "Table name is required.";
      if (!model.draft.tableReason.trim()) model.errors.tableReason = "Change reason is required before saving.";
      return Object.keys(model.errors).some((key) => ["tableName", "tableReason"].includes(key));
    }
    if (!model.draft.attributeName.trim()) model.errors.attributeName = "Attribute name is required.";
    if (!model.draft.attributeReason.trim()) model.errors.attributeReason = "Change reason is required before saving.";
    return Object.keys(model.errors).some((key) => ["attributeName", "attributeReason", "allowedChoices", "entryGuidance"].includes(key));
  }

  function handleSave(kind) {
    if (model.saving) { window.__duplicateSubmitBlocked = true; return; }
    if (validateBeforeSave(kind)) { renderEditor(); document.querySelector(".form-error")?.scrollIntoView({ block: "nearest" }); return; }
    model.saving = true;
    setTaskStatus("Saving new revision…");
    renderEditor();
    window.__saveSubmitCount = (window.__saveSubmitCount || 0) + 1;
  }

  function attachFormHandlers() {
    refs.editor.querySelectorAll("input, textarea, select").forEach((control) => {
      control.addEventListener("input", () => updateDraft(control.name, control.type === "checkbox" ? control.checked : control.value));
      control.addEventListener("change", () => updateDraft(control.name, control.type === "checkbox" ? control.checked : control.value));
    });
  }

  function selectObject(id) {
    const object = objectsForKind(model.objectKind).find((item) => item.id === id);
    if (!object) return;
    model.selectedObject = id;
    if (model.objectKind === "tables") model.selectedTable = id;
    if (model.objectKind === "layouts") model.selectedLayout = id;
    render();
    refs.editor.focus({ preventScroll: true });
  }

  function setStateStatus() {
    if (["catalog-error", "error", "table-save-error", "attribute-save-error"].includes(state)) setTaskStatus("Needs attention");
    else if (["loading", "catalog-loading"].includes(state)) setTaskStatus("Loading catalog…");
    else if (state === "stale-conflict") setTaskStatus("Resolve revision conflict");
    else if (["table-saving", "attribute-saving"].includes(state)) setTaskStatus("Saving new revision…");
    else if (state === "attribute-long-invalid") setTaskStatus("Draft has invalid fields");
    else if (state === "table-add") setTaskStatus("New Table draft");
    else if (state === "attribute-add") setTaskStatus("New Attribute draft");
    else setTaskStatus("Ready");
  }

  document.addEventListener("click", (event) => {
    const target = event.target.closest("button, [data-object-kind]");
    if (!target) return;
    if (target.dataset.objectKind) { setFamilySelection(target.dataset.objectKind); return; }
    if (target.dataset.objectId) { selectObject(target.dataset.objectId); return; }
    const action = target.dataset.action;
    if (!action) return;
    if (action === "preview-projection") {
      model.previewProjection = target.dataset.projection === "layout" ? "layout" : "record";
      model.previewFieldId = "";
      renderPreview();
      target.focus({ preventScroll: true });
      return;
    }
    if (action === "preview-field") {
      model.previewFieldId = target.dataset.previewField || "";
      renderPreview();
      document.querySelector(`[data-preview-field="${CSS.escape(model.previewFieldId)}"]`)?.focus({ preventScroll: true });
      return;
    }
    if (action === "preview-close") {
      const invoker = model.previewInvoker || refs.previewCommand;
      model.previewOpen = false;
      setTaskStatus("Datasheet preview closed");
      renderPreview();
      invoker?.focus({ preventScroll: true });
      model.previewInvoker = null;
      return;
    }
    if (action === "edit-table") { model.objectKind = "tables"; state = "table-draft"; document.body.dataset.state = "table-draft"; window.history.replaceState({}, "", `${window.location.pathname}?state=table-draft`); setStateStatus(); model.dirty = false; render(); return; }
    if (action === "add-object") {
      model.objectKind = model.objectKind === "attributes" ? "attributes" : "tables";
      state = model.objectKind === "attributes" ? "attribute-add" : "table-add";
      document.body.dataset.state = state;
      window.history.replaceState({}, "", `${window.location.pathname}?state=${state}`);
      model.dirty = true;
      setStateStatus();
      render();
      refs.editor.querySelector("input")?.focus();
      return;
    }
    if (action === "cancel-add") {
      state = "normal";
      document.body.dataset.state = state;
      window.history.replaceState({}, "", window.location.pathname);
      model.dirty = false;
      setStateStatus();
      render();
      refs.addObject.focus();
      return;
    }
    if (action === "save-new-table") { window.__addTableSubmitted = true; setTaskStatus("New Table ready to save"); return; }
    if (action === "save-new-attribute") { window.__addAttributeSubmitted = true; setTaskStatus("New Attribute ready to save"); return; }
    if (action === "save-table") { handleSave("table"); return; }
    if (action === "save-attribute") { handleSave("attribute"); return; }
    if (action === "retry-save") { model.saving = false; delete model.errors.tableSave; delete model.errors.attributeSave; setTaskStatus("Ready"); renderEditor(); return; }
    if (action === "retry-catalog") { setTaskStatus("Ready"); window.__catalogRetried = true; return; }
    if (action === "discard-draft") { model.dirty = false; model.errors = {}; model.saving = false; setTaskStatus("Ready"); render(); return; }
    if (action === "reload-current") { model.dirty = false; state = "normal"; document.body.dataset.state = "normal"; setTaskStatus("Current definition reloaded"); render(); return; }
    if (action === "keep-local") { model.saving = false; model.dirty = true; setTaskStatus("Draft retained"); renderEditor(); refs.editor.querySelector("[data-editor-mode]")?.focus?.(); return; }
    if (action === "cancel-conflict") { setTaskStatus("Draft retained"); renderEditor(); refs.editor.querySelector("[data-conflict-region]")?.focus(); return; }
    if (action === "refresh") { setTaskStatus("Selection retained · refreshed"); window.__refreshRetainedSelection = model.selectedObject; return; }
    if (action === "preview" || action === "preview-toggle") {
      model.previewInvoker = target;
      model.previewOpen = !model.previewOpen;
      setTaskStatus(model.previewOpen ? "Datasheet preview opened" : "Datasheet preview closed");
      renderPreview();
      if (model.previewOpen) {
        refs.previewScroll?.focus({ preventScroll: true });
        refs.previewPanel?.querySelector("[data-action=preview-close]")?.focus({ preventScroll: true });
      } else {
        model.previewInvoker?.focus({ preventScroll: true });
      }
      return;
    }
  });

  document.addEventListener("keydown", (event) => {
    const tab = event.target.closest?.('[role="tab"][data-action="preview-projection"]');
    if (!tab || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const tabs = [...document.querySelectorAll('[role="tab"][data-action="preview-projection"]')];
    const index = tabs.indexOf(tab);
    const nextIndex = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    event.preventDefault();
    const next = tabs[nextIndex];
    if (next && next !== tab) next.click();
    next?.focus({ preventScroll: true });
  });

  refs.currentTable.addEventListener("change", (event) => {
    model.selectedTable = event.target.value;
    model.selectedLayout = PREVIEW_LAYOUT_BY_TABLE[model.selectedTable] || "material-layout";
    if (model.objectKind === "attributes") model.selectedObject = objectsForKind("attributes")[0]?.id || "";
    else model.selectedObject = model.selectedTable;
    render();
  });

  refs.editor.addEventListener("input", () => attachFormHandlers());
  refs.editor.addEventListener("change", () => attachFormHandlers());

  function setupSplitters() {
    const splitters = [...document.querySelectorAll("[data-splitter]")];
    const values = { navigator: { property: "--navigator-width", pane: "navigator-pane" }, list: { property: "--list-width", pane: "object-list-pane" } };
    splitters.forEach((splitter) => {
      const key = splitter.dataset.splitter;
      const config = values[key];
      const min = Number(splitter.getAttribute("aria-valuemin"));
      const max = Number(splitter.getAttribute("aria-valuemax"));
      if (window.innerWidth >= 1700) splitter.setAttribute("aria-valuenow", key === "navigator" ? "260" : "364");
      else if (window.innerWidth < 1400) splitter.setAttribute("aria-valuenow", key === "navigator" ? "226" : "304");
      const update = (next) => {
        const clamped = Math.max(min, Math.min(max, Math.round(next)));
        document.documentElement.style.setProperty(config.property, `${clamped}px`);
        splitter.setAttribute("aria-valuenow", String(clamped));
        splitter.setAttribute("aria-valuetext", `${clamped} pixels`);
        window.__splitterValues = { ...(window.__splitterValues || {}), [key]: clamped };
      };
      splitter.addEventListener("keydown", (event) => {
        const current = Number(splitter.getAttribute("aria-valuenow"));
        if (event.key === "ArrowLeft" || event.key === "ArrowDown") { event.preventDefault(); update(current - 8); }
        if (event.key === "ArrowRight" || event.key === "ArrowUp") { event.preventDefault(); update(current + 8); }
        if (event.key === "Home") { event.preventDefault(); update(min); }
        if (event.key === "End") { event.preventDefault(); update(max); }
      });
      let pointerStart = null;
      splitter.addEventListener("pointerdown", (event) => { pointerStart = { x: event.clientX, value: Number(splitter.getAttribute("aria-valuenow")) }; splitter.setPointerCapture?.(event.pointerId); });
      splitter.addEventListener("pointermove", (event) => { if (pointerStart) update(pointerStart.value + (event.clientX - pointerStart.x)); });
      splitter.addEventListener("pointerup", () => { pointerStart = null; });
      splitter.addEventListener("pointercancel", () => { pointerStart = null; });
      update(Number(splitter.getAttribute("aria-valuenow")));
    });
  }

  function setupEditorScrollRail() {
    const rail = refs.editorScrollRail;
    const thumb = refs.editorScrollThumb;
    if (!rail || !thumb) return;
    const setScrollTop = (value) => {
      const maxScroll = Math.max(0, refs.editor.scrollHeight - refs.editor.clientHeight);
      refs.editor.scrollTop = Math.max(0, Math.min(maxScroll, value));
      updateEditorScrollRail();
    };
    refs.editor.addEventListener("scroll", updateEditorScrollRail, { passive: true });
    rail.addEventListener("wheel", (event) => {
      event.preventDefault();
      setScrollTop(refs.editor.scrollTop + event.deltaY);
    }, { passive: false });
    rail.addEventListener("keydown", (event) => {
      const pageStep = Math.max(48, Math.round(refs.editor.clientHeight * .8));
      const keySteps = {
        ArrowUp: -36,
        ArrowDown: 36,
        PageUp: -pageStep,
        PageDown: pageStep
      };
      if (event.key === "Home") { event.preventDefault(); setScrollTop(0); }
      else if (event.key === "End") { event.preventDefault(); setScrollTop(refs.editor.scrollHeight); }
      else if (Object.prototype.hasOwnProperty.call(keySteps, event.key)) {
        event.preventDefault();
        setScrollTop(refs.editor.scrollTop + keySteps[event.key]);
      }
    });
    let dragStart = null;
    rail.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      const track = rail.getBoundingClientRect();
      const thumbRect = thumb.getBoundingClientRect();
      if (event.clientY >= thumbRect.top && event.clientY <= thumbRect.bottom) {
        dragStart = { pointerY: event.clientY, scrollTop: refs.editor.scrollTop };
      } else {
        const maxScroll = Math.max(0, refs.editor.scrollHeight - refs.editor.clientHeight);
        const maxTravel = Math.max(1, track.height - thumbRect.height);
        setScrollTop(((event.clientY - track.top - thumbRect.height / 2) / maxTravel) * maxScroll);
        dragStart = { pointerY: event.clientY, scrollTop: refs.editor.scrollTop };
      }
      rail.setPointerCapture?.(event.pointerId);
    });
    rail.addEventListener("pointermove", (event) => {
      if (!dragStart) return;
      const maxScroll = Math.max(0, refs.editor.scrollHeight - refs.editor.clientHeight);
      const maxTravel = Math.max(1, rail.clientHeight - thumb.getBoundingClientRect().height);
      setScrollTop(dragStart.scrollTop + ((event.clientY - dragStart.pointerY) / maxTravel) * maxScroll);
    });
    const finishDrag = () => { dragStart = null; };
    rail.addEventListener("pointerup", finishDrag);
    rail.addEventListener("pointercancel", finishDrag);
    window.addEventListener("resize", scheduleEditorScrollRailUpdate);
    if ("ResizeObserver" in window) new ResizeObserver(scheduleEditorScrollRailUpdate).observe(refs.editor);
  }

  window.addEventListener("beforeunload", (event) => {
    if (model.dirty && !model.saving) { event.preventDefault(); event.returnValue = "Your draft changes are not saved."; }
  });

  setupSplitters();
  setupEditorScrollRail();
  window.addEventListener("resize", () => renderPreview());
  setStateStatus();
  render();
  attachFormHandlers();
  window.__testDuplicateSubmit = () => {
    if (model.saving) { window.__duplicateSubmitBlocked = true; return "blocked"; }
    model.saving = true;
    return "started";
  };
  if (state === "stale-conflict") window.setTimeout(() => document.querySelector("[data-conflict-region]")?.focus(), 0);
})();
