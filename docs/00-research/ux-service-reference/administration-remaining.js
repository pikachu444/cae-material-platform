(() => {
  "use strict";

  const query = window.__REFERENCE_QUERY__ || {};
  const family = query.family || "layout";
  const state = query.state || (family === "publish" ? "blocked" : "draft");
  const role = query.role || "administrator";
  document.body.dataset.referenceFamily = family;
  document.body.dataset.referenceState = state;
  document.body.dataset.role = role;

  const refs = {
    pageTitle: document.querySelector("[data-page-title]"),
    pageContext: document.querySelector("[data-page-context]"),
    taskActions: document.querySelector("[data-task-actions]"),
    navTitle: document.querySelector("[data-nav-title]"),
    navCount: document.querySelector("[data-nav-count]"),
    navFamilies: document.querySelector("[data-object-families]"),
    scopeEditor: document.querySelector("[data-scope-editor]"),
    navFoot: document.querySelector("[data-nav-foot]"),
    listTitle: document.querySelector("[data-list-title]"),
    listCount: document.querySelector("[data-list-count]"),
    listBody: document.querySelector("[data-list-body]"),
    editorBody: document.querySelector("[data-editor-body]"),
    statusBar: document.querySelector("[data-status-bar]"),
    topbarContext: document.querySelector("[data-topbar-context]"),
  };

  const schemaFamilies = [
    ["tables", "Tables", 5],
    ["attributes", "Attributes", 18],
    ["layout", "Layouts", 3],
    ["subset", "Subsets", 4],
    ["link", "Link Types", 3],
  ];
  const accessFamilies = [
    ["access", "Assignments", 8],
    ["role-presets", "Role presets", 3],
    ["access-help", "Access guidance", 1],
  ];
  const publishFamilies = [
    ["publish", "Publish readiness", 5],
    ["validation", "Validation results", 4],
    ["history", "Draft history", 6],
  ];

  const layouts = [
    { id: "layout-engineering", name: "Engineering datasheet", fields: 9, revision: 7 },
    { id: "layout-card", name: "Solver delivery summary", fields: 6, revision: 4 },
    { id: "layout-test", name: "Test evidence", fields: 8, revision: 3 },
  ];
  const subsets = [
    { id: "subset-released-metal", name: "Released metal cards", result: "24 rows", revision: 6 },
    { id: "subset-room-temp", name: "Room-temperature tensile", result: "38 rows", revision: 5 },
    { id: "subset-review", name: "Needs technical review", result: "7 rows", revision: 2 },
    { id: "subset-polymer", name: "Polymer relaxation data", result: "16 rows", revision: 4 },
  ];
  const links = [
    { id: "link-neutral-card", name: "Neutral model to solver cards", endpoints: "1 → many", revision: 5 },
    { id: "link-test-material", name: "Test Data to material", endpoints: "many → 1", revision: 3 },
    { id: "link-material-related", name: "Related materials", endpoints: "many ↔ many", revision: 2 },
  ];
  const assignments = [
    { id: "acc-reviewers", name: "material-reviewers", role: "Reviewer", scope: "Project", classification: "Confidential", status: "Active" },
    { id: "acc-users", name: "material-engineers", role: "User", scope: "Project", classification: "Confidential", status: "Active" },
    { id: "acc-admin", name: "materials-admins", role: "Administrator", scope: "Organization", classification: "Restricted", status: "Active" },
    { id: "acc-lab", name: "test-lab-users", role: "User", scope: "Project", classification: "Internal", status: "Active" },
    { id: "acc-cae", name: "cae-card-reviewers", role: "Reviewer", scope: "Project", classification: "Confidential", status: "Active" },
    { id: "acc-polymer", name: "polymer-modeling", role: "User", scope: "Project", classification: "Confidential", status: "Active" },
    { id: "acc-auditors", name: "materials-auditors", role: "Reviewer", scope: "Organization", classification: "Restricted", status: "Active" },
    { id: "acc-contractor", name: "external-lab-readers", role: "User", scope: "Project", classification: "Internal", status: "Expires 30 d" },
  ];
  const publishItems = [
    { id: "pub-table", name: "Materials master Table", status: "Saved draft", revision: "r12" },
    { id: "pub-attrs", name: "18 Attribute definitions", status: "Saved drafts", revision: "18" },
    { id: "pub-layout", name: "Engineering datasheet Layout", status: "Saved draft", revision: "r7" },
    { id: "pub-subset", name: "Released metal cards Subset", status: "Saved draft", revision: "r6" },
    { id: "pub-link", name: "Neutral model to solver cards", status: "Saved draft", revision: "r5" },
  ];

  let selectedId = family === "layout" ? layouts[0].id : family === "subset" ? subsets[0].id : family === "link" ? links[0].id : family === "access" ? assignments[0].id : publishItems[0].id;
  let statusText = state.includes("loading") ? "Loading" : state.includes("error") ? "Attention required" : "Ready";

  function esc(value) {
    return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
  }

  function button(label, action, classes = "button", attrs = "") {
    return `<button type="button" class="${classes}" data-action="${action}" ${attrs}>${esc(label)}</button>`;
  }

  function renderStatus() {
    const selection = family === "layout" ? "Layout · Engineering datasheet" : family === "subset" ? "Subset · Released metal cards" : family === "link" ? "Link Type · Neutral model to solver cards" : family === "access" ? (state === "denied" ? "Users and access" : "Assignment · material-reviewers") : "Catalog publish boundary";
    const revision = family === "access" ? "Task-based access" : family === "publish" ? "Draft definitions preserved" : "Exact revision editing";
    refs.statusBar.innerHTML = `<span>${esc(selection)}</span><span>${esc(revision)}</span><span>${esc(statusText)}</span><span>Online</span>`;
  }

  function renderTop() {
    if (["layout", "subset", "link"].includes(family)) {
      refs.pageTitle.textContent = "Database design";
      refs.pageContext.textContent = "Atlas workspace · Materials master";
      refs.topbarContext.textContent = "Administrator · Atlas workspace";
      const previewLabel = family === "layout" ? "Preview datasheet" : family === "subset" ? "Preview results" : "Test Related";
      const loading = state.endsWith("loading");
      const blocked = state.includes("blocked") || state === "link-invalid";
      refs.taskActions.innerHTML = `<span class="task-status">${esc(statusText)}</span>${button("Validate", "validate", "button", loading ? "disabled" : "")}${button(previewLabel, "preview", "button", loading ? "disabled" : "")}${button("Save new revision", "save", "button primary", blocked || loading ? "disabled" : "")}`;
    } else if (family === "access") {
      refs.pageTitle.textContent = "Users and access";
      refs.pageContext.textContent = state === "denied" ? "Administrator access required" : "Atlas workspace · task-based product roles";
      refs.topbarContext.textContent = state === "denied" ? "Demo user" : "Administrator · Atlas workspace";
      if (state === "denied") {
        refs.taskActions.innerHTML = "";
      } else if (state === "revoke-confirm") {
        refs.taskActions.innerHTML = `<span class="task-status">Confirmation required</span>${button("Cancel", "cancel-revoke", "button")}`;
      } else {
        refs.taskActions.innerHTML = `<span class="task-status">${esc(statusText)}</span>${button("Refresh", "refresh", "button", state === "loading" ? "disabled" : "")}${button("Add assignment", "add-assignment", state === "empty" ? "button" : "button primary", state === "loading" ? "disabled" : "")}`;
      }
    } else {
      refs.pageTitle.textContent = "Catalog publish";
      refs.pageContext.textContent = "Atlas workspace · publication capability boundary";
      refs.topbarContext.textContent = "Administrator · Atlas workspace";
      refs.taskActions.innerHTML = `<span class="task-status">Not configured</span>${button("Validate drafts", "validate-publish", "button", state === "validation-loading" ? "disabled" : "")}${button("Publish catalog", "publish", "button primary", "disabled aria-describedby=publish-disabled-reason")}`;
    }
  }

  function renderNavigator() {
    const families = ["layout", "subset", "link"].includes(family) ? schemaFamilies : family === "access" ? accessFamilies : publishFamilies;
    refs.navTitle.textContent = family === "access" ? "Access administration" : family === "publish" ? "Catalog lifecycle" : "Schema objects";
    refs.navCount.textContent = `${families.length} areas`;
    refs.navFamilies.innerHTML = families.map(([key, label, count]) => `<button type="button" class="object-family${key === family || (family === "publish" && key === "publish") ? " is-selected" : ""}" data-family="${key}"><span>${esc(label)}</span><span class="family-count">${count}</span></button>`).join("");
    if (["layout", "subset", "link"].includes(family)) {
      refs.scopeEditor.innerHTML = `<label for="current-table">Current Table</label><select id="current-table" aria-label="Current Table"><option>Materials master</option><option>Test records</option><option>Solver cards</option></select><span>Definitions pin this exact Table revision.</span>`;
      refs.navFoot.textContent = "Current Table scope retained";
    } else if (family === "access") {
      refs.scopeEditor.innerHTML = "";
      refs.navFoot.textContent = state === "denied" ? "No assignment data disclosed" : "Organization and project scope";
    } else {
      refs.scopeEditor.innerHTML = "";
      refs.navFoot.textContent = "Saved drafts remain editable";
    }
  }

  function listRow(item, kind) {
    const selected = item.id === selectedId;
    if (kind === "layout") return `<button type="button" class="remaining-row layout${selected ? " is-selected" : ""}" data-row-id="${item.id}" aria-pressed="${selected}"><span class="row-name">${esc(item.name)}</span><span class="row-meta">${item.fields} fields</span><span class="row-revision">${item.revision}</span></button>`;
    if (kind === "subset") return `<button type="button" class="remaining-row subset${selected ? " is-selected" : ""}" data-row-id="${item.id}" aria-pressed="${selected}"><span class="row-name">${esc(item.name)}</span><span class="row-meta">${esc(item.result)}</span><span class="row-revision">${item.revision}</span></button>`;
    if (kind === "link") return `<button type="button" class="remaining-row link${selected ? " is-selected" : ""}" data-row-id="${item.id}" aria-pressed="${selected}"><span class="row-name">${esc(item.name)}</span><span class="row-meta">${esc(item.endpoints)}</span><span class="row-revision">${item.revision}</span></button>`;
    if (kind === "access") return `<button type="button" class="remaining-row access${selected ? " is-selected" : ""}" data-row-id="${item.id}" aria-pressed="${selected}"><span class="row-name">${esc(item.name)}</span><span class="row-meta">${esc(item.role)}</span><span class="row-status is-active">${esc(item.status)}</span></button>`;
    return `<button type="button" class="remaining-row publish${selected ? " is-selected" : ""}" data-row-id="${item.id}" aria-pressed="${selected}"><span class="row-name">${esc(item.name)}</span><span class="row-status is-blocked">${esc(item.status)}</span><span class="row-revision">${esc(item.revision)}</span></button>`;
  }

  function renderList() {
    if (family === "layout") {
      refs.listTitle.textContent = "Layouts"; refs.listCount.textContent = `${layouts.length} items`;
      refs.listBody.innerHTML = `<div class="remaining-list-columns layout"><span>Name</span><span>Fields</span><span>Rev</span></div>${layouts.map((item) => listRow(item, "layout")).join("")}`;
    } else if (family === "subset") {
      refs.listTitle.textContent = "Subsets"; refs.listCount.textContent = `${subsets.length} items`;
      refs.listBody.innerHTML = `<div class="remaining-list-columns subset"><span>Name</span><span>Preview</span><span>Rev</span></div>${subsets.map((item) => listRow(item, "subset")).join("")}`;
    } else if (family === "link") {
      refs.listTitle.textContent = "Link Types"; refs.listCount.textContent = `${links.length} items`;
      refs.listBody.innerHTML = `<div class="remaining-list-columns link"><span>Name</span><span>Cardinality</span><span>Rev</span></div>${links.map((item) => listRow(item, "link")).join("")}`;
    } else if (family === "access") {
      refs.listTitle.textContent = "Assignments";
      if (state === "denied") {
        refs.listCount.textContent = "Hidden";
        refs.listBody.innerHTML = `<div class="empty-flat"><strong>Assignments are not available</strong><span>Only an Administrator may view or change product access.</span></div>`;
      } else if (state === "loading") {
        refs.listCount.textContent = "Loading";
        refs.listBody.innerHTML = `<div class="remaining-list-columns access"><span>User or team</span><span>Role</span><span>Status</span></div><div class="list-loading" aria-label="Loading assignments"><span></span><span></span><span></span><span></span><span></span></div>`;
      } else if (state === "empty") {
        refs.listCount.textContent = "0 items";
        refs.listBody.innerHTML = `<div class="remaining-list-columns access"><span>User or team</span><span>Role</span><span>Status</span></div><div class="empty-flat"><strong>No product assignments</strong><span>Add the first task-based role for this workspace.</span></div>`;
      } else {
        refs.listCount.textContent = `${assignments.length} items`;
        refs.listBody.innerHTML = `<div class="remaining-list-columns access"><span>User or team</span><span>Role</span><span>Status</span></div>${assignments.map((item) => listRow(item, "access")).join("")}`;
      }
    } else {
      refs.listTitle.textContent = "Draft change set"; refs.listCount.textContent = `${publishItems.length} groups`;
      refs.listBody.innerHTML = `<div class="remaining-list-columns publish"><span>Definition</span><span>State</span><span>Rev</span></div>${publishItems.map((item) => listRow(item, "publish")).join("")}`;
    }
  }

  function commonEditorHeading(title, subtitle, marker = "Unsaved draft") {
    return `<header class="editor-heading is-dirty"><div><h2>${esc(title)}</h2><p>${esc(subtitle)}</p></div><span class="editor-state">${esc(marker)}</span></header>`;
  }

  function layoutEditor() {
    const missing = state === "missing-attribute-blocked";
    const previewLoading = state === "preview-loading";
    const previewError = state === "preview-error";
    const fields = [
      [1, "Material name", "Text"], [2, "Grade", "Text"], [3, "Material condition", "Discrete"],
      [4, "Density", "Number"], [5, "Young's modulus", "Number"], [6, "Poisson ratio", "Number"],
      [7, "Yield strength", "Number"], [8, "Stress–strain response", "Curve"], [9, missing ? "Deleted Attribute revision" : "Related solver cards", missing ? "Missing" : "Record reference"],
    ];
    const preview = previewLoading
      ? `<div class="preview-surface"><div class="preview-surface-header"><div><h3>Record preview</h3><p>Engineering datasheet · r7 · 9 fields</p></div><span>Loading</span></div><div class="preview-loading" aria-label="Loading datasheet preview"><span></span><span></span><span></span><span></span><span></span></div></div>`
      : `<div class="preview-surface"><div class="preview-surface-header"><div><h3>Record preview</h3><p>Engineering datasheet · r7 · 9 saved fields</p></div><span>DP780-REF · r3</span></div>${previewError ? `<div class="validation-strip error" role="alert"><strong>Preview refresh failed</strong><p>The last valid saved Record remains visible. Retry without discarding the Layout draft.</p></div>` : ""}<div class="preview-body"><table class="preview-table compact"><thead><tr><th>Property</th><th>Value</th><th>Condition</th></tr></thead><tbody><tr><td>Material name</td><td class="nowrap">DP780 synthetic demo steel</td><td class="muted">—</td></tr><tr><td>Grade</td><td>DP780-REF</td><td class="muted">—</td></tr><tr><td>Material condition</td><td>As received</td><td class="muted">293 K</td></tr><tr><td>Density</td><td class="numeric">7.80e-9 tonne/mm³</td><td class="muted">Nominal</td></tr><tr><td>Young's modulus</td><td class="numeric">210,000 MPa</td><td class="muted">293 K</td></tr><tr><td>Poisson ratio</td><td class="numeric">0.30</td><td class="muted">293 K</td></tr><tr><td>Yield strength</td><td class="numeric">560 MPa</td><td class="muted">Quasi-static</td></tr><tr><td>Stress–strain response</td><td>1 saved curve</td><td class="muted">Tensile</td></tr><tr><td>Related solver cards</td><td>3 exact revisions</td><td class="muted">Abaqus · OpenRadioss</td></tr></tbody></table></div></div>`;
    return `<div class="remaining-editor-content"><div class="remaining-editor-grid"><section class="editor-column">${commonEditorHeading("Engineering datasheet", "Layout revision 7 · Materials master", missing ? "Blocked draft" : "Unsaved draft")} ${missing ? `<div class="validation-strip error" role="alert"><strong>Missing Attribute revision</strong><p>One ordered field no longer resolves. Replace or remove it before saving a new Layout revision.</p></div>` : ""}<form class="compact-property-form" data-editor-form="layout"><div class="form-row"><label for="layout-name">Layout name</label><div class="form-value"><input id="layout-name" value="Engineering datasheet"></div></div><div class="form-row"><label for="layout-desc">Purpose</label><div class="form-value"><textarea id="layout-desc">Primary engineering datasheet for material identity, condition, properties, response curve and available solver cards.</textarea></div></div></form><div class="inline-toolbar"><strong>Ordered fields</strong>${button("Add field", "add-field", "button")}</div><ol class="ordered-field-list">${fields.map(([order, name, type]) => `<li class="ordered-field-row${type === "Missing" ? " is-missing" : ""}"><span class="order">${order}</span><span class="field-name" title="${esc(name)}">${esc(name)}</span><span class="field-type">${esc(type)}</span><button type="button" aria-label="Move ${esc(name)}">↕</button></li>`).join("")}</ol><div class="editor-actions">${button("Save new revision", "save-layout", "button", missing ? "disabled" : "")}${button("Discard draft", "discard", "button")}${missing ? `<span class="save-disabled-reason">Save disabled · resolve the missing Attribute.</span>` : ""}</div></section><aside class="preview-column">${commonEditorHeading("Live datasheet preview", "Saved Record values in current Layout order", "Read-only")}${preview}</aside></div></div>`;
  }

  function subsetEditor() {
    const invalid = state === "invalid-filter-blocked";
    const loading = state === "preview-loading";
    const error = state === "preview-error";
    const filters = [
      ["Family", "equals Metal", "Discrete"],
      ["Card status", "equals Released", "Discrete"],
      ["Temperature", invalid ? "minimum exceeds maximum" : "273 K to 333 K", "Number"],
    ];
    const preview = loading
      ? `<div class="preview-surface"><div class="preview-surface-header"><div><h3>Scoped result preview</h3><p>Current authorization and saved filter definition</p></div><span>Loading</span></div><div class="preview-loading"><span></span><span></span><span></span><span></span></div></div>`
      : `<div class="preview-surface"><div class="preview-surface-header"><div><h3>Scoped result preview</h3><p>Released metal cards · 24 authorized matches</p></div><span>1–8 of 24</span></div>${error ? `<div class="validation-strip error" role="alert"><strong>Preview refresh failed</strong><p>The last valid result page remains visible; the Subset draft is preserved.</p></div>` : ""}<div class="preview-body"><table class="preview-table compact"><thead><tr><th>Material</th><th>State</th><th>Available cards</th></tr></thead><tbody>${[["DP780","As received","Abaqus · OpenRadioss"],["DP600","As received","Abaqus · LS-DYNA"],["HC340LA","Cold rolled","OpenRadioss"],["AA6061-T6","T6","Abaqus"],["DC04","Annealed","Abaqus · OpenRadioss"],["SUS304","Solution treated","LS-DYNA"],["SPFC980","As received","OpenRadioss"],["Q&P980","As received","Abaqus"]].map(row => `<tr><td>${row[0]}</td><td class="muted">${row[1]}</td><td class="nowrap">${row[2]}</td></tr>`).join("")}</tbody></table></div></div>`;
    return `<div class="remaining-editor-content"><div class="remaining-editor-grid"><section class="editor-column">${commonEditorHeading("Released metal cards", "Subset revision 6 · Materials master", invalid ? "Blocked draft" : "Unsaved draft")}${invalid ? `<div class="validation-strip error" role="alert"><strong>Invalid numeric range</strong><p>Temperature minimum must not exceed maximum. The last saved Subset remains unchanged.</p></div>` : ""}<form class="compact-property-form" data-editor-form="subset"><div class="form-row"><label for="subset-name">Subset name</label><div class="form-value"><input id="subset-name" value="Released metal cards"></div></div><div class="form-row"><label for="subset-desc">Purpose</label><div class="form-value"><textarea id="subset-desc">Reusable view of released metal records with at least one downloadable solver card.</textarea></div></div></form><div class="inline-toolbar"><strong>Filter definition</strong>${button("Add filter", "add-filter", "button")}</div><ul class="filter-list">${filters.map(([field, value, operator], index) => `<li class="filter-row${invalid && index === 2 ? " is-invalid" : ""}"><span class="filter-field">${esc(field)}</span><span class="filter-value">${esc(value)}</span><span class="filter-operator">${esc(operator)}</span></li>`).join("")}</ul><div class="editor-actions">${button("Save new revision", "save-subset", "button", invalid ? "disabled" : "")}${button("Discard draft", "discard", "button")}${invalid ? `<span class="save-disabled-reason">Save disabled · correct the range.</span>` : ""}</div></section><aside class="preview-column">${commonEditorHeading("Result preview", "Same server-scoped query supplies count and rows", "Read-only")}${preview}</aside></div></div>`;
  }

  function linkEditor() {
    const invalid = state === "link-invalid";
    const loading = state === "validation-loading";
    const error = state === "related-error";
    const targetTable = invalid ? "Neutral materials" : "Solver cards";
    const related = [["Neutral metal model · r4","Abaqus 2025 kg-m-s · r2"],["Neutral metal model · r4","OpenRadioss 2025 kg-m-s · r1"],["Neutral metal model · r4","LS-DYNA R15 mm-ms-tonne · r1"],["Neutral polymer model · r2","Abaqus 2025 kg-m-s · r1"],["Neutral polymer model · r2","OpenRadioss 2025 kg-m-s · r1"]];
    const preview = `<div class="preview-surface"><div class="preview-surface-header"><div><h3>Related Records test</h3><p>Forward label: Available solver cards · exact Record revisions</p></div><span>${error ? "Last valid result" : `${related.length} links`}</span></div>${error ? `<div class="validation-strip error" role="alert"><strong>Related test failed</strong><p>The Link Type draft and last valid exact-revision branches remain visible. Retry the test.</p></div>` : ""}${loading ? `<div class="preview-loading"><span></span><span></span><span></span><span></span></div>` : `<div class="preview-body"><ul class="link-test-list">${related.map(([source, target], i) => `<li class="link-test-row"><span class="source">${esc(source)}</span><span class="arrow">→</span><span class="target">${esc(target)}</span><span class="revision">${i < 3 ? "r4" : "r2"}</span></li>`).join("")}</ul></div>`}</div>`;
    return `<div class="remaining-editor-content"><div class="remaining-editor-grid"><section class="editor-column">${commonEditorHeading("Neutral model to solver cards", "Link Type revision 5", invalid ? "Blocked draft" : loading ? "Validating" : "Unsaved draft")}${invalid ? `<div class="validation-strip error" role="alert"><strong>Invalid endpoints</strong><p>Source and target cannot both be Neutral materials for this Link Type. Choose the governed Solver cards Table.</p></div>` : loading ? `<div class="validation-strip"><strong>Validating endpoints and cardinality</strong><p>Save and Related test remain disabled while the exact Table revisions are checked.</p></div>` : ""}<form class="compact-property-form" data-editor-form="link"><div class="form-row"><label for="link-name">Name</label><div class="form-value"><input id="link-name" value="Neutral model to solver cards"></div></div><div class="form-row"><label>Source / target</label><div class="form-value"><div class="range-fields"><div class="range-field"><label for="source-table">Source Table</label><select id="source-table"><option>Neutral materials</option></select></div><div class="range-field"><label for="target-table">Target Table</label><select id="target-table"><option>${esc(targetTable)}</option></select></div></div><p class="form-help">Current Table revisions are pinned when this Link Type revision is saved.</p></div></div><div class="form-row"><label>Direction labels</label><div class="form-value"><div class="range-fields direction-fields"><div class="range-field"><label for="forward-label">Forward</label><input id="forward-label" value="Available solver cards"></div><div class="range-field"><label for="reverse-label">Reverse</label><input id="reverse-label" value="Generated from neutral model"></div></div></div></div><div class="form-row"><label>Cardinality</label><div class="form-value"><div class="cardinality-grid"><div class="cardinality-field"><label for="source-cardinality">Sources allowed per target</label><select id="source-cardinality"><option>one</option><option>many</option></select></div><div class="cardinality-field"><label for="target-cardinality">Targets allowed per source</label><select id="target-cardinality"><option>many</option><option>one</option></select></div></div><p class="form-help">One exact Neutral revision may branch to several solver/version/unit-specific cards.</p></div></div></form><p class="exact-pin-note"><strong>Exact revision policy:</strong> each Record Link pins the source revision and target revision. There is no “latest” alias.</p><div class="editor-actions">${button("Save new revision", "save-link", "button", invalid || loading ? "disabled" : "")}${button("Validate and test", "validate-link", "button", invalid || loading ? "disabled" : "")}${button("Discard draft", "discard", "button")}</div></section><aside class="preview-column">${commonEditorHeading("Branching relationship preview", "One-to-many and many-to-one are independently configured", "Read-only")}${preview}</aside></div></div>`;
  }

  function accessEditor() {
    if (state === "denied") {
      return `<div class="remaining-editor-content"><div class="remaining-editor-grid single"><section class="editor-column">${commonEditorHeading("Administrator access required", "Users and access is restricted to workspace administrators", "Blocked")}<div class="denied-strip" role="alert"><strong>You cannot view or change product assignments.</strong><p>Your current User role still allows authorized Materials lookup, Modeling work and review requests.</p></div><div class="editor-actions">${button("Back to Materials", "back-materials", "button primary")}</div><details class="advanced-disclosure"><summary>Why this is blocked</summary><p>Assignment listing, grant and revoke APIs require Administrator access. No assignment names or scopes were loaded.</p></details></section></div></div>`;
    }
    if (state === "revoke-confirm") {
      return `<div class="remaining-editor-content"><div class="remaining-editor-grid access-grid"><section class="editor-column">${commonEditorHeading("Revoke material-reviewers access", "Existing Reviewer assignment · current project", "Confirmation required")}<div class="confirm-strip" role="alert"><strong>This removes task access for the selected team.</strong><p>Existing immutable review decisions remain preserved. New Reviewer actions will be blocked after revocation.</p></div><dl class="assignment-summary"><div class="definition-row"><dt>User or team</dt><dd>material-reviewers</dd></div><div class="definition-row"><dt>Current role</dt><dd>Reviewer</dd></div><div class="definition-row"><dt>Scope</dt><dd>Atlas workspace · current project</dd></div><div class="definition-row"><dt>Classification</dt><dd>Up to Confidential</dd></div></dl><form class="compact-property-form"><div class="form-row"><label for="revoke-reason">Reason</label><div class="form-value"><textarea id="revoke-reason">Team membership moved to the consolidated CAE review group.</textarea><p class="form-help">A reason is required and is retained with the access change.</p></div></div></form><div class="editor-actions">${button("Revoke access", "confirm-revoke", "button primary danger")}${button("Cancel", "cancel-revoke", "button")}</div></section><aside class="preview-column">${commonEditorHeading("Included Reviewer work", "The assignment being removed", "Read-only")}<ul class="task-list"><li class="task-row"><strong>Find and download governed materials</strong><span>Included</span></li><li class="task-row"><strong>Process and fit test data</strong><span>Included</span></li><li class="task-row"><strong>Review material and solver-card requests</strong><span>Included</span></li><li class="task-row"><strong>Configure schema and access</strong><span class="not-granted">Not granted</span></li></ul></aside></div></div>`;
    }
    const empty = state === "empty";
    const loading = state === "loading";
    const serviceError = state === "service-error";
    if (empty) {
      return `<div class="remaining-editor-content"><div class="remaining-editor-grid single"><section class="editor-column">${commonEditorHeading("Add the first product assignment", "Task-based User, Reviewer or Administrator role", "New assignment")}<div class="empty-flat"><strong>No assignments exist in this workspace.</strong><span>Choose one team, role, scope and maximum classification.</span></div>${accessGrantForm()} </section></div></div>`;
    }
    if (loading) {
      return `<div class="remaining-editor-content"><div class="remaining-editor-grid single"><section class="editor-column">${commonEditorHeading("Loading product access", "The prior workspace remains visible while assignments are requested", "Loading")}<div class="preview-loading"><span></span><span></span><span></span><span></span><span></span></div><div class="editor-actions">${button("Add assignment", "add-assignment", "button primary", "disabled")}</div><span class="save-disabled-reason">Commands are disabled until the assignment list is available.</span></section></div></div>`;
    }
    return `<div class="remaining-editor-content"><div class="remaining-editor-grid access-grid"><section class="editor-column">${commonEditorHeading("material-reviewers", "Reviewer assignment · current project", serviceError ? "Last valid assignment" : "Active")}${serviceError ? `<div class="service-error-strip" role="alert"><strong>Access service refresh failed</strong><p>The last valid assignments and selection remain visible. Retry without changing the assignment.</p></div>` : ""}<dl class="assignment-summary"><div class="definition-row"><dt>Subject</dt><dd>Identity-provider group · material-reviewers</dd></div><div class="definition-row"><dt>Product role</dt><dd>Reviewer</dd></div><div class="definition-row"><dt>Scope</dt><dd>Atlas workspace · current project</dd></div><div class="definition-row"><dt>Classification</dt><dd>Up to Confidential · export-controlled data excluded</dd></div><div class="definition-row"><dt>Valid from</dt><dd>2026-07-18 · no expiry</dd></div></dl><div class="editor-actions">${button("Edit assignment", "edit-assignment", "button")}${button("Revoke access…", "revoke", "button danger")}${serviceError ? button("Retry refresh", "refresh", "button") : ""}</div></section><aside class="preview-column">${commonEditorHeading("Included Reviewer work", "Readable task preset backed by feature grants", "Read-only")}<ul class="task-list"><li class="task-row"><strong>Find, compare and download materials</strong><span>Included</span></li><li class="task-row"><strong>Upload, process and fit test data</strong><span>Included</span></li><li class="task-row"><strong>Review material and solver-card requests</strong><span>Included</span></li><li class="task-row"><strong>Create approved solver-card deliveries</strong><span>Included</span></li><li class="task-row"><strong>Configure schema and access</strong><span class="not-granted">Not granted</span></li></ul><p class="exact-pin-note"><strong>Enforcement:</strong> detailed service permissions and PostgreSQL row policies remain behind this task-based role.</p></aside></div></div>`;
  }

  function accessGrantForm() {
    return `<form class="compact-property-form" data-editor-form="access"><div class="form-row"><label for="access-team">User or team</label><div class="form-value"><input id="access-team" value="material-engineers" placeholder="Identity-provider group"></div></div><div class="form-row"><label for="access-role">Role</label><div class="form-value"><select id="access-role"><option>User</option><option>Reviewer</option><option>Administrator</option></select><p class="form-help">User can search, download, request review, and process or fit material data.</p></div></div><div class="form-row"><label for="access-scope">Scope</label><div class="form-value"><select id="access-scope"><option>Current project</option><option>Organization</option></select></div></div><div class="form-row"><label for="access-classification">Maximum classification</label><div class="form-value"><select id="access-classification"><option>Confidential</option><option>Internal</option><option>Restricted</option></select></div></div><div class="form-row"><label for="access-reason">Reason</label><div class="form-value"><textarea id="access-reason">Provide standard material search, Modeling and solver-card request work for the current project.</textarea></div></div></form><div class="editor-actions">${button("Create assignment", "save-access", "button primary")}${button("Cancel", "cancel-add", "button")}</div>`;
  }

  function publishEditor() {
    const validationBlocked = state === "validation-blocked";
    const validationLoading = state === "validation-loading";
    const publishError = state === "publish-error";
    const rows = [
      ["Table and Attribute definitions", validationBlocked ? "1 issue" : "Valid", "20"],
      ["Layouts", validationBlocked ? "Blocked" : "Valid", "3"],
      ["Subsets", "Valid", "4"],
      ["Link Types", "Valid", "3"],
      ["Access boundary", "Valid", "3 roles"],
    ];
    return `<div class="remaining-editor-content"><div class="remaining-editor-grid publish-grid"><section class="editor-column">${commonEditorHeading("Catalog publication readiness", "Saved definitions in Atlas workspace", validationLoading ? "Validating" : validationBlocked ? "Validation blocked" : "Not configured")}${validationBlocked ? `<div class="validation-strip error" role="alert"><strong>Layout validation is blocked</strong><p>Engineering datasheet still contains a missing Attribute revision. Correct the saved draft before publication can be considered.</p></div>` : validationLoading ? `<div class="validation-strip"><strong>Validating saved draft revisions</strong><p>Table, Attribute, Layout, Subset and Link Type checks are running. Draft editing remains available.</p></div>` : publishError ? `<div class="service-error-strip" role="alert"><strong>Publication capability check failed</strong><p>No publication request was sent. All saved draft revisions remain unchanged and editable.</p></div>` : ""}<ul class="readiness-list">${rows.map(([name, result, count], index) => `<li class="readiness-row${(validationBlocked && index < 2) || result === "Blocked" ? " is-blocked" : ""}"><strong>${esc(name)}</strong><span>${validationLoading ? "Checking" : esc(result)}</span><em>${esc(count)}</em></li>`).join("")}</ul><div class="editor-actions">${button("Open Database design", "open-database", "button")}${button("Validate again", "validate-publish", "button", validationLoading ? "disabled" : "")}</div></section><aside class="preview-column">${commonEditorHeading("Publish catalog", "Publication transition and policy endpoint", "Not configured")}<div class="publish-boundary"><h3>Catalog publishing is not available in this build.</h3><p>Table, Attribute, Layout, Subset and Link Type resources currently remain governed saved drafts. The service exposes no catalog publication transition or publication-policy endpoint.</p><div class="editor-actions">${button("Publish catalog", "publish", "button primary", "disabled aria-describedby=publish-disabled-reason")}</div><p class="disabled-reason" id="publish-disabled-reason">Publish is disabled because the required backend capability is not configured.</p></div><dl class="assignment-summary"><div class="definition-row"><dt>Preserved now</dt><dd>Exact saved draft revisions, validation evidence and editor state</dd></div><div class="definition-row"><dt>Not fabricated</dt><dd>Published state, publication date, release receipt or successful transition</dd></div><div class="definition-row"><dt>Next action</dt><dd>Continue editing and validating drafts in Database design</dd></div></dl></aside></div></div>`;
  }

  function renderEditor() {
    refs.editorBody.innerHTML = family === "layout" ? layoutEditor() : family === "subset" ? subsetEditor() : family === "link" ? linkEditor() : family === "access" ? accessEditor() : publishEditor();
  }

  function syncSplitterValues() {
    const workspace = document.querySelector(".workspace");
    if (!workspace) return;
    document.querySelectorAll("[data-splitter]").forEach((separator) => {
      const variable = separator.dataset.splitter === "navigator" ? "--navigator-width" : "--list-width";
      const width = parseFloat(getComputedStyle(workspace).getPropertyValue(variable));
      if (Number.isFinite(width)) separator.setAttribute("aria-valuenow", String(Math.round(width)));
    });
  }

  function render() {
    renderTop(); renderNavigator(); renderList(); renderEditor(); renderStatus(); syncSplitterValues();
    document.body.dataset.ready = "true";
  }

  function setStatus(text) { statusText = text; renderStatus(); }

  document.addEventListener("click", (event) => {
    const row = event.target.closest("[data-row-id]");
    if (row) { selectedId = row.dataset.rowId; renderList(); renderEditor(); setStatus("Selection changed"); return; }
    const action = event.target.closest("[data-action]")?.dataset.action;
    if (!action) return;
    if (action === "revoke") { document.body.dataset.referenceState = "revoke-confirm"; setStatus("Confirmation required"); refs.editorBody.innerHTML = accessEditorFor("revoke-confirm"); return; }
    if (action === "cancel-revoke") { setStatus("Revocation cancelled"); return; }
    if (action === "confirm-revoke") { setStatus("Access revoked"); return; }
    if (action.startsWith("save")) { setStatus("Draft save requested"); return; }
    if (action.includes("validate")) { setStatus("Validation complete"); return; }
    if (action === "refresh") { setStatus("Refresh requested"); return; }
    if (action === "preview") { setStatus("Preview refreshed"); return; }
    if (action === "open-database" || action === "back-materials") { setStatus("Navigation requested"); return; }
    setStatus("Ready");
  });

  function accessEditorFor(nextState) {
    const previous = state;
    try {
      Object.defineProperty(window.__REFERENCE_QUERY__ || {}, "state", { value: nextState, configurable: true });
    } catch (_) { /* static capture only */ }
    if (nextState === "revoke-confirm") {
      return `<div class="remaining-editor-content"><div class="remaining-editor-grid access-grid"><section class="editor-column">${commonEditorHeading("Revoke material-reviewers access", "Existing Reviewer assignment · current project", "Confirmation required")}<div class="confirm-strip" role="alert"><strong>This removes task access for the selected team.</strong><p>Existing immutable review decisions remain preserved. New Reviewer actions will be blocked after revocation.</p></div><dl class="assignment-summary"><div class="definition-row"><dt>User or team</dt><dd>material-reviewers</dd></div><div class="definition-row"><dt>Current role</dt><dd>Reviewer</dd></div><div class="definition-row"><dt>Scope</dt><dd>Atlas workspace · current project</dd></div></dl><form class="compact-property-form"><div class="form-row"><label for="revoke-reason-live">Reason</label><div class="form-value"><textarea id="revoke-reason-live">Team membership moved to the consolidated CAE review group.</textarea></div></div></form><div class="editor-actions">${button("Revoke access", "confirm-revoke", "button primary danger")}${button("Cancel", "cancel-revoke", "button")}</div></section></div></div>`;
    }
    return previous;
  }

  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
      const save = document.querySelector('[data-action^="save"]:not(:disabled)');
      if (save) { event.preventDefault(); save.click(); }
    }
    const separator = event.target.closest?.('[role="separator"]');
    if (separator && ["ArrowLeft", "ArrowRight"].includes(event.key)) {
      event.preventDefault();
      const variable = separator.dataset.splitter === "navigator" ? "--navigator-width" : "--list-width";
      const current = parseFloat(getComputedStyle(document.querySelector(".workspace")).getPropertyValue(variable)) || Number(separator.getAttribute("aria-valuenow"));
      const next = Math.max(Number(separator.getAttribute("aria-valuemin")), Math.min(Number(separator.getAttribute("aria-valuemax")), current + (event.key === "ArrowRight" ? 12 : -12)));
      document.querySelector(".workspace").style.setProperty(variable, `${next}px`);
      separator.setAttribute("aria-valuenow", String(next));
      setStatus("Pane size adjusted");
    }
  });

  render();
})();
