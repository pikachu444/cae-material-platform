const root = document.documentElement;
const body = document.body;
const interactionStatus = document.querySelector("#interaction-status");
const treeSearch = document.querySelector("#tree-search-form");
const treeQuery = document.querySelector("#tree-query");
const materialTree = document.querySelector("#material-tree");
const treeRows = [...document.querySelectorAll("#material-tree [role='treeitem']")];
const navigatorPane = document.querySelector("[data-region='navigator']");
const navigatorDivider = document.querySelector("[data-region='navigator-divider']");
const tabList = document.querySelector("[role='tablist']");
const tabButtons = [...document.querySelectorAll("[role='tab']")];

const setInteractionStatus = (message) => {
  if (interactionStatus) interactionStatus.textContent = message;
};

const focusTreeRow = (row) => {
  if (!row) return;
  treeRows.forEach((candidate) => {
    candidate.tabIndex = candidate === row ? 0 : -1;
  });
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
  const label = row.querySelector(".tree-label")?.textContent?.trim() ?? "selected item";
  setInteractionStatus(`${row.dataset.kind ?? "Record"} ${label} selected`);
};

document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLocaleLowerCase() === "k") {
    event.preventDefault();
    treeQuery?.focus();
    treeQuery?.select();
    body.dataset.navigatorSearchFocused = "true";
    setInteractionStatus("Navigator search focused");
  }
});

treeSearch?.addEventListener("submit", (event) => {
  event.preventDefault();
  const query = treeQuery?.value.trim() ?? "";
  body.dataset.treeSearchConsequence = query.toLocaleLowerCase() === "dp780" ? "DP780-REF" : query;
  setInteractionStatus(`Tree search applied: ${query || "all records"}; ancestors retained`);
});

materialTree?.addEventListener("keydown", (event) => {
  const currentIndex = treeRows.indexOf(document.activeElement);
  if (currentIndex < 0) return;

  let nextRow = null;
  if (event.key === "ArrowDown") {
    nextRow = treeRows[Math.min(treeRows.length - 1, currentIndex + 1)];
  } else if (event.key === "ArrowUp") {
    nextRow = treeRows[Math.max(0, currentIndex - 1)];
  } else if (event.key === "Home") {
    nextRow = treeRows[0];
  } else if (event.key === "End") {
    nextRow = treeRows.at(-1);
  } else if (event.key === "Enter") {
    event.preventDefault();
    selectTreeRow(treeRows[currentIndex]);
    return;
  }

  if (nextRow) {
    event.preventDefault();
    focusTreeRow(nextRow);
  }
});

treeRows.forEach((row) => {
  row.addEventListener("click", () => {
    focusTreeRow(row);
    selectTreeRow(row);
  });
});

const syncNavigatorAria = () => {
  if (!navigatorPane || !navigatorDivider) return;
  const width = Math.round(navigatorPane.getBoundingClientRect().width);
  navigatorDivider.setAttribute("aria-valuenow", String(width));
};

syncNavigatorAria();

navigatorDivider?.addEventListener("keydown", (event) => {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  event.preventDefault();

  const minimum = Number(navigatorDivider.getAttribute("aria-valuemin"));
  const maximum = Number(navigatorDivider.getAttribute("aria-valuemax"));
  const current = Number(navigatorDivider.getAttribute("aria-valuenow"));
  let next = current;
  if (event.key === "Home") {
    next = minimum;
  } else if (event.key === "End") {
    next = maximum;
  } else {
    next = current + (event.key === "ArrowRight" ? 8 : -8);
    next = Math.max(minimum, Math.min(maximum, next));
  }

  root.style.setProperty("--navigator-width", `${next}px`);
  syncNavigatorAria();
  body.dataset.splitterConsequence = String(next);
  setInteractionStatus(`Catalog navigator width ${next}px`);
});

const restoreOverview = () => {
  const overview = tabButtons.find((button) => button.dataset.tab === "Overview");
  if (overview) activateTab(overview, false);
};

const activateTab = (button, focus = true) => {
  if (!button) return;
  tabButtons.forEach((candidate) => {
    const selected = candidate === button;
    candidate.classList.toggle("active", selected);
    candidate.setAttribute("aria-selected", String(selected));
    candidate.tabIndex = selected ? 0 : -1;
  });
  body.dataset.activeTab = button.dataset.tab ?? "Overview";
  setInteractionStatus(`${button.dataset.tab ?? "Overview"} tab selected`);
  if (focus) button.focus();
};

tabButtons.forEach((button) => {
  button.addEventListener("click", () => activateTab(button));
  button.addEventListener("keydown", (event) => {
    const currentIndex = tabButtons.indexOf(button);
    let nextIndex = null;
    if (event.key === "ArrowRight") {
      nextIndex = (currentIndex + 1) % tabButtons.length;
    } else if (event.key === "ArrowLeft") {
      nextIndex = (currentIndex - 1 + tabButtons.length) % tabButtons.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = tabButtons.length - 1;
    }
    if (nextIndex !== null) {
      event.preventDefault();
      activateTab(tabButtons[nextIndex]);
    }
  });
});

tabList?.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    const focused = document.activeElement;
    if (focused?.getAttribute("role") === "tab") {
      event.preventDefault();
      activateTab(focused);
    }
  }
});

document.querySelector("#back-to-results")?.addEventListener("click", (event) => {
  event.preventDefault();
  body.dataset.restoredQuery = "steel";
  body.dataset.restoredSelection = "DP780-REF";
  setInteractionStatus("Returned to results · steel · DP780-REF selection restored");
});

document.querySelector("#preview-inp")?.addEventListener("click", () => {
  body.dataset.cardPreview = "Abaqus:.inp";
  setInteractionStatus("Preview opened · Abaqus .inp reference card");
});

document.querySelector("#download-inp")?.addEventListener("click", () => {
  body.dataset.cardDownload = "Abaqus:.inp";
  setInteractionStatus("Download prepared · Abaqus .inp reference card");
});

document.querySelector("#preview-rad")?.addEventListener("click", () => {
  body.dataset.cardPreview = "OpenRadioss:.rad";
  setInteractionStatus("Preview opened · OpenRadioss .rad reference card");
});

document.querySelector("#download-rad")?.addEventListener("click", () => {
  body.dataset.cardDownload = "OpenRadioss:.rad";
  setInteractionStatus("Download prepared · OpenRadioss .rad reference card");
});

// Keep the normal reference state explicit if a consumer invokes this helper after a tab exercise.
window.restoreDatasheetOverview = restoreOverview;
