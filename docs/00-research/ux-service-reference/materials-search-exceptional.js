(() => {
  "use strict";

  const params = new URLSearchParams(window.location.search);
  const requestedState = params.get("state") || "normal";
  const stateAliases = {
    loading: "search-loading",
    "tree-lazy-loading": "tree-loading",
    "query-error": "query-error",
    "tree-error": "tree-error",
  };
  const initialState = stateAliases[requestedState] || requestedState;

  const elements = {
    body: document.body,
    searchForm: document.querySelector("#material-search-form"),
    query: document.querySelector("#material-query"),
    treeSearchForm: document.querySelector("#tree-search-form"),
    treeQuery: document.querySelector("#tree-query"),
    tree: document.querySelector("#material-tree"),
    treeScroll: document.querySelector(".tree-scroll"),
    treeScrollbarY: document.querySelector("#tree-scrollbar-y"),
    treeScrollbarX: document.querySelector("#tree-scrollbar-x"),
    treeNotice: document.querySelector("#tree-notice"),
    resultBody: document.querySelector("#results-body"),
    resultsScroll: document.querySelector("#results-scroll"),
    resultsScrollbarY: document.querySelector("#results-scrollbar-y"),
    resultCount: document.querySelector("#result-count"),
    familyCounts: document.querySelector("#family-counts"),
    resultsNotice: document.querySelector("#results-notice"),
    resultsEmpty: document.querySelector("#results-empty"),
    clearSearch: document.querySelector("#clear-search"),
    selectedSummary: document.querySelector("#selected-summary"),
    emptyContext: document.querySelector("#empty-context"),
    selectedFields: document.querySelector("#selected-fields"),
    contextAction: document.querySelector("#context-action"),
    openDatasheet: document.querySelector("#open-datasheet"),
    interactionStatus: document.querySelector("#interaction-status"),
    statusSelection: document.querySelector("#status-selection"),
    statusRevision: document.querySelector("#status-revision"),
  };

  const NORMAL_ROWS = [
    ["DP780 synthetic demo steel", "DP780-REF", "Metal", "Synthetic local-demo data; not validated engineering data."],
    ["DP600 synthetic demo steel", "DP600-REF", "Metal", "Synthetic demo steel record; not engineering data."],
    ["HSLA synthetic demo steel", "HSLA-REF", "Metal", "Synthetic demo steel example; not engineering data."],
    ["Mild synthetic demo steel", "MILD-REF", "Metal", "Synthetic demo steel sample; not engineering data."],
    ["Stainless synthetic demo steel", "SS-REF", "Metal", "Synthetic demo steel fixture; not engineering data."],
    ["Press-hardening synthetic demo steel", "PHS-REF", "Metal", "Synthetic demo steel reference; not engineering data."],
  ].map(([name, grade, family, description]) => ({ name, grade, family, description, status: "Draft" }));

  const LONG_FAMILIES = ["Metal", "Polymer", "Elastomer", "Composite", "Ceramic"];
  const LONG_ROWS = Array.from({ length: 50 }, (_, index) => {
    if (index === 0) return { ...NORMAL_ROWS[0] };
    const sequence = String(index + 1).padStart(2, "0");
    const family = LONG_FAMILIES[index % LONG_FAMILIES.length];
    const grade = `SYN-${family.slice(0, 3).toUpperCase()}-${sequence}-REF`;
    const name = `${family} qualification reference coupon ${sequence} with extended label for review`; // deliberately long, realistic fixture text
    const description = `Synthetic ${family.toLowerCase()} record ${sequence} for scoped search density review; not validated engineering data.`;
    return { name, grade, family, description, status: index % 7 === 0 ? "Review" : "Draft" };
  });

  let treeRows = [];
  const splitters = [...document.querySelectorAll(".splitter")];
  let currentRows = NORMAL_ROWS;
  let selectedGrade = "DP780-REF";
  let activeState = initialState;

  const TREE_NODES = [
    ["tree-database", 0, "Database", "Materials Database", true],
    ["tree-profile", 1, "Profile", "Engineering Materials", true],
    ["tree-table", 2, "Table", "Demo Material Records", true],
    ["tree-metals", 3, "Folder", "Metals", true],
    ["tree-steels", 4, "Folder", "Demo steels", true],
    ["tree-dp780", 5, "Record", "DP780 synthetic demo steel", false],
    ["tree-dp600", 5, "Record", "DP600 synthetic demo steel", false],
    ["tree-ahss", 5, "Record", "Advanced high-strength steel qualification sequence with extended governed identity", false],
    ["tree-aluminum", 3, "Folder", "Aluminum", true],
    ["tree-6xxx", 4, "Folder", "6xxx series", true],
    ["tree-aa6016", 5, "Record", "AA6016 solution-treated and naturally-aged forming alloy", false],
    ["tree-aa6111", 5, "Record", "AA6111 bake-hardening alloy", false],
    ["tree-polymers", 3, "Folder", "Polymers", true],
    ["tree-thermoplastics", 4, "Folder", "Thermoplastics", true],
    ["tree-pa66", 5, "Record", "PA66 GF30 conditioned tensile", false],
    ["tree-pbt", 5, "Record", "PBT GF20 injection-molded coupon", false],
    ["tree-elastomers", 3, "Folder", "Elastomers", true],
    ["tree-epdm", 4, "Folder", "EPDM", true],
    ["tree-epdm70", 5, "Record", "EPDM 70A thermal-ageing qualification", false],
    ["tree-composites", 3, "Folder", "Composites", true],
    ["tree-cfrp", 4, "Folder", "CFRP laminates", true],
    ["tree-cfrp-ud", 5, "Record", "CFRP UD [0/90]s coupon qualification", false],
    ["tree-ceramics", 3, "Folder", "Ceramics", true],
    ["tree-alumina", 4, "Folder", "Alumina", true],
    ["tree-al2o3", 5, "Record", "Alumina 96% flexural qualification", false],
    ["tree-archive", 3, "Folder", "Archived qualification records", true],
    ["tree-legacy", 4, "Folder", "Legacy identity mappings", true],
    ["tree-legacy-dp", 5, "Record", "Legacy DP780 exact-reference recovery", false],
  ];

  const renderTree = () => {
    const fragment = document.createDocumentFragment();
    TREE_NODES.forEach(([id, depth, kind, label, expanded]) => {
      const row = create("div", `tree-row depth-${depth}${id === "tree-dp780" ? " selected" : ""}`);
      row.id = id;
      row.setAttribute("role", "treeitem");
      row.setAttribute("aria-level", String(depth + 1));
      row.setAttribute("aria-selected", String(id === "tree-dp780"));
      row.setAttribute("aria-label", `${kind}: ${label}`);
      row.tabIndex = id === "tree-dp780" ? 0 : -1;
      row.dataset.kind = kind;
      if (expanded) row.setAttribute("aria-expanded", "true");
      const disclosure = create("span", "tree-disclosure", expanded ? "▾" : "");
      disclosure.setAttribute("aria-hidden", "true");
      const identity = create("span", "tree-label", label);
      identity.title = label;
      const glyph = create("span", "tree-kind");
      glyph.dataset.kind = kind;
      glyph.title = kind;
      glyph.setAttribute("aria-hidden", "true");
      row.append(disclosure, glyph, identity);
      fragment.append(row);
    });
    elements.tree.replaceChildren(fragment);
    treeRows = [...elements.tree.querySelectorAll("[role='treeitem']")];
  };

  const setInteractionStatus = (message) => {
    if (elements.interactionStatus) elements.interactionStatus.textContent = message;
  };

  const scrollbarAxis = (indicator) => indicator?.getAttribute("aria-orientation") === "horizontal" ? "x" : "y";

  const syncScrollbarIndicator = (scroller, indicator) => {
    if (!scroller || !indicator) return false;
    const axis = scrollbarAxis(indicator);
    const range = axis === "x"
      ? scroller.scrollWidth - scroller.clientWidth
      : scroller.scrollHeight - scroller.clientHeight;
    const shell = scroller.closest("[data-scroll-shell]");
    const overflowed = range > 1;
    indicator.hidden = !overflowed;
    if (shell) shell.dataset[axis === "x" ? "scrollX" : "scrollY"] = String(overflowed);
    indicator.setAttribute("aria-valuemax", String(Math.max(0, Math.round(range))));
    if (!overflowed) {
      indicator.setAttribute("aria-valuenow", "0");
      return false;
    }
    const thumb = indicator.firstElementChild;
    const trackLength = axis === "x" ? indicator.clientWidth : indicator.clientHeight;
    const viewportLength = axis === "x" ? scroller.clientWidth : scroller.clientHeight;
    const contentLength = axis === "x" ? scroller.scrollWidth : scroller.scrollHeight;
    const thumbLength = Math.max(36, Math.round((viewportLength / contentLength) * Math.max(0, trackLength - 4)));
    const available = Math.max(0, trackLength - 4 - thumbLength);
    const offset = Math.round(((axis === "x" ? scroller.scrollLeft : scroller.scrollTop) / range) * available);
    if (axis === "x") {
      thumb.style.width = `${thumbLength}px`;
      thumb.style.transform = `translateX(${offset}px)`;
    } else {
      thumb.style.height = `${thumbLength}px`;
      thumb.style.transform = `translateY(${offset}px)`;
    }
    indicator.setAttribute("aria-valuenow", String(Math.round(axis === "x" ? scroller.scrollLeft : scroller.scrollTop)));
    return true;
  };

  const syncScrollbarIndicators = () => {
    syncScrollbarIndicator(elements.treeScroll, elements.treeScrollbarY);
    syncScrollbarIndicator(elements.treeScroll, elements.treeScrollbarX);
    syncScrollbarIndicator(elements.resultsScroll, elements.resultsScrollbarY);
  };

  const scrollToScrollbarValue = (scroller, indicator, value) => {
    const axis = scrollbarAxis(indicator);
    const maximum = Number(indicator.getAttribute("aria-valuemax")) || 0;
    const next = Math.max(0, Math.min(maximum, value));
    scroller.scrollTo(axis === "x" ? { left: next, behavior: "instant" } : { top: next, behavior: "instant" });
  };

  const bindScrollbar = (scroller, indicator) => {
    if (!scroller || !indicator) return;
    const axis = scrollbarAxis(indicator);
    indicator.addEventListener("keydown", (event) => {
      const maximum = Number(indicator.getAttribute("aria-valuemax")) || 0;
      const current = axis === "x" ? scroller.scrollLeft : scroller.scrollTop;
      const viewport = axis === "x" ? scroller.clientWidth : scroller.clientHeight;
      const increment = event.key === "ArrowRight" || event.key === "ArrowDown" ? 36
        : event.key === "ArrowLeft" || event.key === "ArrowUp" ? -36
          : event.key === "PageDown" ? viewport * 0.8
            : event.key === "PageUp" ? -viewport * 0.8
              : null;
      if (event.key === "Home") scrollToScrollbarValue(scroller, indicator, 0);
      else if (event.key === "End") scrollToScrollbarValue(scroller, indicator, maximum);
      else if (increment !== null) scrollToScrollbarValue(scroller, indicator, current + increment);
      else return;
      event.preventDefault();
    });
    indicator.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      event.preventDefault();
      const thumb = indicator.firstElementChild;
      const railBounds = indicator.getBoundingClientRect();
      const thumbBounds = thumb.getBoundingClientRect();
      const startPointer = axis === "x" ? event.clientX : event.clientY;
      const startValue = axis === "x" ? scroller.scrollLeft : scroller.scrollTop;
      const maximum = Number(indicator.getAttribute("aria-valuemax")) || 0;
      const available = axis === "x"
        ? railBounds.width - 4 - thumbBounds.width
        : railBounds.height - 4 - thumbBounds.height;
      if (event.target !== thumb) {
        const railOffset = (axis === "x" ? event.clientX - railBounds.left : event.clientY - railBounds.top) - 2;
        const thumbLength = axis === "x" ? thumbBounds.width : thumbBounds.height;
        scrollToScrollbarValue(scroller, indicator, ((railOffset - thumbLength / 2) / Math.max(1, available)) * maximum);
        return;
      }
      indicator.setPointerCapture(event.pointerId);
      const move = (moveEvent) => {
        const pointer = axis === "x" ? moveEvent.clientX : moveEvent.clientY;
        scrollToScrollbarValue(scroller, indicator, startValue + ((pointer - startPointer) / Math.max(1, available)) * maximum);
      };
      const end = (endEvent) => {
        indicator.releasePointerCapture?.(endEvent.pointerId);
        indicator.removeEventListener("pointermove", move);
        indicator.removeEventListener("pointerup", end);
        indicator.removeEventListener("pointercancel", end);
      };
      indicator.addEventListener("pointermove", move);
      indicator.addEventListener("pointerup", end);
      indicator.addEventListener("pointercancel", end);
    });
  };

  const setBodyState = (state) => {
    activeState = state;
    elements.body.dataset.state = state;
  };

  const create = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  const updateContext = (row) => {
    if (!row) {
      selectedGrade = "";
      elements.selectedSummary.hidden = true;
      elements.emptyContext.hidden = false;
      elements.selectedFields.hidden = true;
      elements.contextAction.hidden = true;
      elements.statusSelection.textContent = `No material selected · ${elements.resultCount.textContent}`;
      if (elements.statusRevision) elements.statusRevision.textContent = "No selected revision";
      elements.body.dataset.selectedResult = "";
      return;
    }
    selectedGrade = row.grade;
    elements.selectedSummary.hidden = false;
    elements.emptyContext.hidden = true;
    elements.selectedFields.hidden = false;
    elements.contextAction.hidden = false;
    document.querySelector("#selected-name").textContent = row.name;
    document.querySelector("#selected-grade").textContent = row.grade;
    document.querySelector("#selected-description").textContent = row.description;
    document.querySelector("#selected-family").textContent = row.family;
    document.querySelector("#selected-status").textContent = row.status;
    elements.statusSelection.textContent = `${row.name} · ${row.grade}`;
    if (elements.statusRevision) elements.statusRevision.textContent = "r1 · draft";
    elements.body.dataset.selectedResult = row.grade;
  };

  const compareLimit = () => {
    const checked = [...document.querySelectorAll(".compare-control input:checked")];
    if (checked.length > 3) checked.at(-1).checked = false;
    elements.body.dataset.compared = [...document.querySelectorAll(".compare-control input:checked")]
      .map((input) => input.dataset.grade || "")
      .filter(Boolean)
      .join(",");
  };

  const selectResultRow = (row) => {
    document.querySelectorAll("[data-result-row]").forEach((candidate) => {
      const selected = candidate === row;
      candidate.classList.toggle("selected", selected);
      candidate.setAttribute("aria-selected", String(selected));
      candidate.tabIndex = selected ? 0 : -1;
    });
    const record = currentRows.find((candidate) => candidate.grade === row.dataset.grade);
    updateContext(record || null);
  };

  const renderRow = (row, selected) => {
    const result = create("tr", `result-row${selected ? " selected" : ""}`);
    result.dataset.resultRow = "true";
    result.dataset.name = row.name;
    result.dataset.grade = row.grade;
    result.dataset.family = row.family;
    result.dataset.description = row.description;
    result.dataset.status = row.status;
    result.tabIndex = selected ? 0 : -1;
    result.setAttribute("aria-selected", String(selected));

    const compareCell = create("td");
    const compareLabel = create("label", "compare-control");
    const compareInput = document.createElement("input");
    compareInput.type = "checkbox";
    compareInput.dataset.grade = row.grade;
    compareInput.setAttribute("aria-label", `Compare ${row.name}`);
    compareLabel.append(compareInput);
    compareCell.append(compareLabel);

    const identity = create("td", "material-identity");
    identity.title = `${row.name} · ${row.grade}`;
    identity.append(create("strong", "", row.name), create("span", "", row.grade));

    const family = create("td", "", row.family);
    family.title = row.family;
    const description = create("td", "", row.description);
    description.title = row.description;
    const status = create("td", "", row.status);
    status.title = row.status;
    result.append(compareCell, identity, family, description, status);
    return result;
  };

  const familySummary = (rows) => {
    const counts = rows.reduce((summary, row) => {
      summary[row.family] = (summary[row.family] || 0) + 1;
      return summary;
    }, {});
    return Object.entries(counts).map(([family, count]) => `${family} ${count}`).join(" · ");
  };

  const renderResults = (rows, total = rows.length, keepSelection = true) => {
    currentRows = rows;
    elements.resultBody.replaceChildren();
    rows.forEach((row) => elements.resultBody.append(renderRow(row, keepSelection && row.grade === selectedGrade)));
    elements.resultCount.textContent = rows.length ? `1–${rows.length} of ${total} matches` : "0 matches";
    elements.familyCounts.textContent = familySummary(rows);
    elements.familyCounts.title = familySummary(rows) || "0 families";
    elements.resultsEmpty.hidden = rows.length !== 0;
    if (rows.length === 0) {
      updateContext(null);
    } else {
      const selected = rows.find((row) => row.grade === selectedGrade) || rows[0];
      selectedGrade = selected.grade;
      updateContext(selected);
    }
    elements.body.dataset.renderedRowCount = String(rows.length);
    elements.body.dataset.resultTotal = String(total);
  };

  const showNotice = (element, message, type, retryId) => {
    element.replaceChildren();
    element.className = `state-notice ${type}`;
    element.append(document.createTextNode(message));
    if (retryId) {
      const retry = create("button", "button secondary-action", "Retry");
      retry.type = "button";
      retry.id = retryId;
      retry.addEventListener("click", () => {
        element.hidden = true;
        elements.body.dataset[retryId === "retry-query" ? "queryRetry" : "treeRetry"] = "true";
        setInteractionStatus("Retry complete; current query and selected material are retained.");
      });
      element.append(retry);
    }
    element.hidden = false;
  };

  const hideNotice = (element) => {
    element.hidden = true;
    element.replaceChildren();
  };

  const renderState = (state) => {
    setBodyState(state);
    hideNotice(elements.resultsNotice);
    hideNotice(elements.treeNotice);
    const long = state === "long";
    const empty = state === "empty";
    if (long) {
      elements.query.value = "steel";
      renderResults(LONG_ROWS, 126);
    } else if (empty) {
      elements.query.value = "zirconium-missing";
      renderResults([], 0, false);
      clearTreeSelection();
    } else {
      elements.query.value = "steel";
      renderResults(NORMAL_ROWS, 6);
      restoreTreeSelection();
    }
    if (state === "search-loading") {
      showNotice(elements.resultsNotice, "Refreshing search · previous rows and the DP780 selection are retained.", "loading");
    } else if (state === "query-error") {
      showNotice(elements.resultsNotice, "Search request failed · previous rows and the DP780 selection are retained.", "error", "retry-query");
    } else if (state === "tree-loading") {
      showNotice(elements.treeNotice, "Loading folder children · current query, results and DP780 selection are retained.", "loading");
    } else if (state === "tree-error") {
      showNotice(elements.treeNotice, "Catalog tree request failed · current query and result selection are retained.", "error", "retry-tree");
    }
    if (elements.resultsScroll) elements.resultsScroll.dataset.state = state;
    requestAnimationFrame(syncScrollbarIndicators);
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
    elements.body.dataset.selectedTreeId = row.id;
    setInteractionStatus(`${row.dataset.kind} ${row.querySelector(".tree-label")?.textContent || ""} selected`);
  };

  const clearTreeSelection = () => {
    treeRows.forEach((row) => {
      row.classList.remove("selected");
      row.setAttribute("aria-selected", "false");
      row.tabIndex = row === treeRows[0] ? 0 : -1;
    });
    elements.body.dataset.selectedTreeId = "";
  };

  const restoreTreeSelection = () => {
    const selected = document.querySelector("#tree-dp780");
    if (selected) selectTreeRow(selected);
  };

  const syncSplitterRanges = () => {
    const width = window.innerWidth;
    const navigatorMaximum = width >= 1700 ? 360 : 340;
    const contextMaximum = width >= 1700 ? 480 : width >= 1400 ? 420 : 376;
    const navigator = document.querySelector("[data-region='navigator-divider']");
    const context = document.querySelector("[data-region='context-divider']");
    navigator.setAttribute("aria-valuemin", "200");
    navigator.setAttribute("aria-valuemax", String(navigatorMaximum));
    context.setAttribute("aria-valuemin", "260");
    context.setAttribute("aria-valuemax", String(contextMaximum));
    navigator.setAttribute("aria-valuenow", String(Math.round(document.querySelector("[data-region='navigator']").getBoundingClientRect().width)));
    context.setAttribute("aria-valuenow", String(Math.round(document.querySelector("[data-region='selected-context']").getBoundingClientRect().width)));
  };

  const resize = (splitter, key) => {
    const isNavigator = splitter.classList.contains("navigator-divider");
    const property = isNavigator ? "--navigator-width" : "--context-width";
    const minimum = Number(splitter.getAttribute("aria-valuemin"));
    const maximum = Number(splitter.getAttribute("aria-valuemax"));
    const current = Number(splitter.getAttribute("aria-valuenow"));
    const direction = isNavigator ? 1 : -1;
    let next = current;
    if (key === "Home") next = minimum;
    else if (key === "End") next = maximum;
    else next = current + (key === "ArrowRight" ? 8 : -8) * direction;
    next = Math.max(minimum, Math.min(maximum, next));
    document.documentElement.style.setProperty(property, `${next}px`);
    splitter.setAttribute("aria-valuenow", String(next));
    setInteractionStatus(`${isNavigator ? "Catalog navigator" : "Selected material context"} width ${next}px`);
  };

  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLocaleLowerCase() === "k") {
      event.preventDefault();
      elements.query?.focus();
      elements.query?.select();
      return;
    }
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const splitter = event.target.closest?.(".splitter");
    if (!splitter || !splitters.includes(splitter)) return;
    event.preventDefault();
    resize(splitter, event.key);
  }, true);

  elements.searchForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    const query = elements.query.value.trim();
    elements.body.dataset.queryApplied = query;
    setInteractionStatus(`${query || "All materials"} search applied`);
  });

  elements.treeSearchForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    const query = elements.treeQuery.value.trim();
    elements.body.dataset.treeSearchConsequence = query ? "DP780-REF" : "";
    setInteractionStatus(query ? `Tree search applied for ${query}` : "Tree search cleared");
  });

  elements.tree?.addEventListener("keydown", (event) => {
    const currentIndex = treeRows.indexOf(document.activeElement);
    if (currentIndex < 0) return;
    let nextRow = null;
    if (event.key === "PageDown" || event.key === "PageUp") {
      event.preventDefault();
      elements.treeScroll.scrollBy({ top: event.key === "PageDown" ? elements.treeScroll.clientHeight * 0.8 : -elements.treeScroll.clientHeight * 0.8, behavior: "instant" });
      return;
    }
    if (event.key === "ArrowDown") nextRow = treeRows[Math.min(treeRows.length - 1, currentIndex + 1)];
    else if (event.key === "ArrowUp") nextRow = treeRows[Math.max(0, currentIndex - 1)];
    else if (event.key === "Home") nextRow = treeRows[0];
    else if (event.key === "End") nextRow = treeRows.at(-1);
    else if (event.key === "Enter") {
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

  elements.resultBody?.addEventListener("click", (event) => {
    const row = event.target.closest?.("[data-result-row]");
    if (!row) return;
    if (event.target instanceof HTMLInputElement) {
      compareLimit();
      return;
    }
    selectResultRow(row);
  });

  elements.resultBody?.addEventListener("keydown", (event) => {
    const row = event.target.closest?.("[data-result-row]");
    if (!row || event.key !== "Enter") return;
    event.preventDefault();
    selectResultRow(row);
    elements.body.dataset.datasheetConsequence = row.dataset.grade;
    setInteractionStatus(`Open datasheet ready for ${row.dataset.name}`);
  });

  elements.resultsScroll?.addEventListener("keydown", (event) => {
    if (event.key !== "PageDown" && event.key !== "PageUp") return;
    event.preventDefault();
    elements.resultsScroll.scrollBy({ top: event.key === "PageDown" ? elements.resultsScroll.clientHeight * 0.8 : -elements.resultsScroll.clientHeight * 0.8, behavior: "instant" });
  });

  elements.treeScroll?.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    event.preventDefault();
    elements.treeScroll.scrollBy({ left: event.key === "ArrowRight" ? 40 : -40, behavior: "instant" });
  });

  [elements.treeScroll, elements.resultsScroll].filter(Boolean).forEach((scroller) => {
    scroller.addEventListener("wheel", (event) => {
      if (!event.deltaY || scroller.scrollHeight <= scroller.clientHeight) return;
      const previous = scroller.scrollTop;
      scroller.scrollBy({ top: event.deltaY, behavior: "instant" });
      if (scroller.scrollTop !== previous) event.preventDefault();
    }, { passive: false });
    scroller.addEventListener("scroll", syncScrollbarIndicators, { passive: true });
  });

  elements.openDatasheet?.addEventListener("click", () => {
    const selected = document.querySelector("[data-result-row][aria-selected='true']");
    if (selected) {
      elements.body.dataset.datasheetConsequence = selected.dataset.grade;
      setInteractionStatus(`Open datasheet ready for ${selected.dataset.name}`);
    }
  });

  elements.clearSearch?.addEventListener("click", () => {
    elements.query.value = "";
    selectedGrade = "DP780-REF";
    renderResults(NORMAL_ROWS, 6);
    restoreTreeSelection();
    setBodyState("normal");
    elements.body.dataset.clearSearch = "true";
    setInteractionStatus("Search cleared; scoped material results restored.");
  });

  splitters.forEach((splitter) => splitter.addEventListener("focus", syncSplitterRanges));
  window.addEventListener("resize", syncSplitterRanges);
  [
    [elements.treeScroll, elements.treeScrollbarY],
    [elements.treeScroll, elements.treeScrollbarX],
    [elements.resultsScroll, elements.resultsScrollbarY],
  ].forEach(([scroller, indicator]) => bindScrollbar(scroller, indicator));
  if ("ResizeObserver" in window) {
    const scrollbarObserver = new ResizeObserver(() => {
      syncScrollbarIndicators();
      requestAnimationFrame(syncScrollbarIndicators);
    });
    [elements.treeScroll, elements.resultsScroll].filter(Boolean).forEach((scroller) => scrollbarObserver.observe(scroller));
  }

  renderTree();
  renderState(activeState);
  syncSplitterRanges();
  syncScrollbarIndicators();
  requestAnimationFrame(syncScrollbarIndicators);
})();
