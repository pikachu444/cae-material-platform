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
    { id: "density", name: "Density", detail: "number · mass per volume", type: "number", revision: "5", description: "Mass density used in the selected material model." },
    { id: "yield-strength", name: "Yield strength", detail: "number · stress", type: "number", revision: "7", description: "Onset of plastic response at the recorded condition." },
    { id: "material-condition", name: "Material condition", detail: "discrete · controlled choice", type: "discrete", revision: "3", description: "Controlled condition label for a material record." },
    { id: "source-reference", name: "Source reference", detail: "record reference", type: "record-reference", revision: "4", description: "Provenance reference associated with the current value." },
    { id: "test-method", name: "Test method", detail: "text", type: "text", revision: "4", description: "Method identifier supplied by the test engineer." },
    { id: "measurement-date", name: "Measurement date", detail: "date", type: "date", revision: "2", description: "Date on which the test measurement was recorded." }
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
  const familyLabels = { tables: "Tables", attributes: "Attributes", layouts: "Layouts", subsets: "Subsets", links: "Link Types" };
  const familyCounts = { tables: 5, attributes: 18, layouts: 3, subsets: 4, links: 2 };

  const params = new URLSearchParams(window.location.search);
  let state = params.get("state") || document.body.dataset.state || "normal";
  document.body.dataset.state = state;

  const refs = {
    workspace: document.querySelector("[data-workspace]"),
    list: document.querySelector("[data-object-list]"),
    listHeading: document.querySelector("[data-list-heading]"),
    listCount: document.querySelector("[data-list-count]"),
    listEmpty: document.querySelector("[data-list-empty]"),
    listLoading: document.querySelector("[data-list-loading]"),
    editor: document.querySelector("[data-editor-scroll]"),
    currentTable: document.querySelector("[data-current-table]"),
    currentTableWrap: document.querySelector("[data-current-table-wrap]"),
    taskStatus: document.querySelector("[data-task-status]"),
    statusSelection: document.querySelector("[data-status-selection]"),
    statusScope: document.querySelector("[data-status-scope]"),
    statusScroll: document.querySelector("[data-status-scroll]"),
    navCount: document.querySelector("[data-nav-count]")
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
      ...ATTRIBUTE_DRAFTS.density
    },
    saving: state === "table-saving" || state === "attribute-saving",
    dirty: ["table-draft", "table-save-error", "attribute-draft", "attribute-save-error", "attribute-long-invalid", "stale-conflict"].includes(state),
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
  function objectsForKind(kind) {
    if (kind === "tables") return TABLES;
    if (kind === "attributes") return model.selectedTable === "materials" ? ATTRIBUTES : ATTRIBUTES.slice(0, 4);
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
    render();
  }
  function selectedListObject() { return objectsForKind(model.objectKind).find((object) => object.id === model.selectedObject) || objectsForKind(model.objectKind)[0]; }

  function renderList() {
    const kind = model.objectKind;
    const objects = state === "empty" && kind === "tables" ? [] : objectsForKind(kind);
    refs.listHeading.textContent = familyLabels[kind];
    refs.listCount.textContent = `${objects.length} ${objects.length === 1 ? "item" : "items"}`;
    refs.listEmpty.hidden = objects.length !== 0;
    refs.listLoading.hidden = !["loading", "catalog-loading"].includes(state);
    refs.list.hidden = objects.length === 0;
    refs.list.innerHTML = objects.map((object) => {
      const selected = object.id === model.selectedObject;
      const displayName = state === "attribute-long-invalid" && object.id === "material-condition" ? model.draft.attributeName : object.name;
      return `<button type="button" class="object-row${selected ? " is-selected" : ""}" role="listitem" data-object-id="${escapeHtml(object.id)}" aria-pressed="${selected}" title="${escapeHtml(displayName)}" aria-label="${escapeHtml(displayName)}">
        <span class="object-name"><span class="object-primary-name" title="${escapeHtml(displayName)}" style="flex:0 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(displayName)}</span><small style="flex:1 1 0;">${escapeHtml(object.detail)}</small></span>
        <span class="object-definition">${escapeHtml(object.description)}</span>
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
      ? `<textarea id="${name}" name="${name}" rows="${options.rows || 3}" aria-describedby="${described}"${options.readonly ? " readonly" : ""}>${escapeHtml(value)}</textarea>`
      : options.select
        ? `<select id="${name}" name="${name}" aria-describedby="${described}"${options.disabled ? " disabled" : ""}>${options.select.map((item) => `<option${item === value ? " selected" : ""}>${escapeHtml(item)}</option>`).join("")}</select>`
        : `<input id="${name}" name="${name}" value="${escapeHtml(value)}" type="${options.type || "text"}" aria-describedby="${described}"${options.readonly ? " readonly" : ""}${options.min !== undefined ? ` min="${options.min}"` : ""}${options.max !== undefined ? ` max="${options.max}"` : ""}>`;
    return `<div class="form-row"><label for="${name}">${label}${required}</label><div class="form-value${error ? " has-error" : ""}">${control}<p class="form-help" id="${name}-help">${escapeHtml(options.help || "")}</p>${error ? `<p class="form-error" id="${name}-error" role="alert">${escapeHtml(error)}</p>` : ""}</div></div>`;
  }

  function tableDraftEditor() {
    const table = currentTable();
    const saveError = model.errors.tableSave ? '<div class="error-region" role="alert"><p>Save failed. The current Table is unchanged; every draft value and the change reason remain available.</p><button type="button" class="button" data-action="retry-save">Retry save</button></div>' : "";
    const savingNote = model.saving ? '<div class="status-note" role="status" aria-live="polite"><strong>Saving new revision</strong> · duplicate submit is blocked while the response is pending.</div>' : "";
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
    const savingNote = model.saving ? '<div class="status-note" role="status" aria-live="polite"><strong>Saving new revision</strong> · duplicate submit is blocked while the response is pending.</div>' : "";
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
    return `<div class="editor-content"><header class="editor-heading"><div><h2>No Table selected</h2><p>Choose a Table when one is available.</p></div><span class="editor-state">Waiting for a Table</span></header><p class="next-step">Use Add Table to define the first governed Table in this workspace.</p><div class="editor-actions"><button type="button" class="button" data-action="add-table">Add Table</button></div></div>`;
  }

  function genericEditor(object) {
    return `<div class="editor-content"><header class="editor-heading"><div><h2>${escapeHtml(object?.name || "Schema object")}</h2><p>${escapeHtml(familyLabels[model.objectKind])} definition</p></div><span class="editor-state">Current definition</span></header><dl class="definition-list"><div class="definition-row"><dt>Purpose</dt><dd>${escapeHtml(object?.description || "No definition is available for this selection.")}</dd></div><div class="definition-row"><dt>Reference</dt><dd class="secondary">Stable identity is available in Evidence.</dd></div></dl><p class="next-step">Select Tables or Attributes to edit a governed definition.</p></div>`;
  }

  function renderEditor() {
    if (state === "empty") { refs.editor.innerHTML = emptyEditor(); return; }
    if (["table-draft", "table-saving", "table-save-error"].includes(state)) { refs.editor.innerHTML = tableDraftEditor(); return; }
    if (state === "stale-conflict") { refs.editor.innerHTML = conflictEditor(); return; }
    if (["attribute-draft", "attribute-saving", "attribute-save-error", "attribute-long-invalid", "attribute-discrete", "attribute-reference", "attribute-text"].includes(state)) { refs.editor.innerHTML = attrDraftEditor(); return; }
    const object = selectedListObject();
    const base = model.objectKind === "tables" ? readOnlyTableEditor(object || currentTable()) : genericEditor(object);
    refs.editor.innerHTML = base;
    if (["catalog-error", "error"].includes(state)) {
      refs.editor.insertAdjacentHTML("afterbegin", '<div class="error-region" role="alert"><p>Catalog refresh failed. The last valid rows and selection remain available.</p><button type="button" class="button" data-action="retry-catalog">Retry</button></div>');
    }
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
    setTaskStatus("Saving new revision");
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
    render();
    refs.editor.focus({ preventScroll: true });
  }

  function setStateStatus() {
    if (["catalog-error", "error", "table-save-error", "attribute-save-error"].includes(state)) setTaskStatus("Needs attention");
    else if (["loading", "catalog-loading"].includes(state)) setTaskStatus("Loading catalog");
    else if (state === "stale-conflict") setTaskStatus("Resolve revision conflict");
    else if (["table-saving", "attribute-saving"].includes(state)) setTaskStatus("Saving new revision");
    else if (state === "attribute-long-invalid") setTaskStatus("Draft has invalid fields");
    else setTaskStatus("Ready");
  }

  document.addEventListener("click", (event) => {
    const target = event.target.closest("button, [data-object-kind]");
    if (!target) return;
    if (target.dataset.objectKind) { setFamilySelection(target.dataset.objectKind); return; }
    if (target.dataset.objectId) { selectObject(target.dataset.objectId); return; }
    const action = target.dataset.action;
    if (!action) return;
    if (action === "edit-table") { model.objectKind = "tables"; state = "table-draft"; document.body.dataset.state = "table-draft"; window.history.replaceState({}, "", `${window.location.pathname}?state=table-draft`); setStateStatus(); model.dirty = false; render(); return; }
    if (action === "save-table") { handleSave("table"); return; }
    if (action === "save-attribute") { handleSave("attribute"); return; }
    if (action === "retry-save") { model.saving = false; delete model.errors.tableSave; delete model.errors.attributeSave; setTaskStatus("Ready"); renderEditor(); return; }
    if (action === "retry-catalog") { setTaskStatus("Ready"); window.__catalogRetried = true; return; }
    if (action === "discard-draft") { model.dirty = false; model.errors = {}; model.saving = false; setTaskStatus("Ready"); render(); return; }
    if (action === "reload-current") { model.dirty = false; state = "normal"; document.body.dataset.state = "normal"; setTaskStatus("Current definition reloaded"); render(); return; }
    if (action === "keep-local") { model.saving = false; model.dirty = true; setTaskStatus("Draft retained"); renderEditor(); refs.editor.querySelector("[data-editor-mode]")?.focus?.(); return; }
    if (action === "cancel-conflict") { setTaskStatus("Draft retained"); renderEditor(); refs.editor.querySelector("[data-conflict-region]")?.focus(); return; }
    if (action === "refresh") { setTaskStatus("Selection retained · refreshed"); window.__refreshRetainedSelection = model.selectedObject; return; }
    if (action === "preview") { setTaskStatus("Datasheet preview opened"); window.__previewRequested = true; return; }
    if (action === "add-table") { setTaskStatus("New Table draft ready"); window.__addTableRequested = true; return; }
  });

  refs.currentTable.addEventListener("change", (event) => {
    model.selectedTable = event.target.value;
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

  window.addEventListener("beforeunload", (event) => {
    if (model.dirty && !model.saving) { event.preventDefault(); event.returnValue = "Your draft changes are not saved."; }
  });

  setupSplitters();
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
