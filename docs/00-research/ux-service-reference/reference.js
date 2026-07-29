const searchForm = document.querySelector("#material-search-form");
const materialQuery = document.querySelector("#material-query");
const materialTree = document.querySelector("#material-tree");
const treeRows = [...document.querySelectorAll("#material-tree [role='treeitem']")];
const resultRows = [...document.querySelectorAll("[data-result-row]")];
const interactionStatus = document.querySelector("#interaction-status");
const openDatasheet = document.querySelector("#open-datasheet");
const splitters = [...document.querySelectorAll(".splitter")];

const setInteractionStatus = (message) => {
  if (interactionStatus) {
    interactionStatus.textContent = message;
  }
};

document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLocaleLowerCase() === "k") {
    event.preventDefault();
    materialQuery?.focus();
    materialQuery?.select();
  }
});

searchForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  const query = materialQuery?.value.trim() ?? "";
  document.body.dataset.queryApplied = query;
  setInteractionStatus(`${query} search applied`);
});

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
  document.body.dataset.selectedTreeId = row.id;
  setInteractionStatus(`${row.dataset.kind} ${row.querySelector(".tree-label")?.textContent ?? ""} selected`);
};

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

const updateSelectedContext = (row) => {
  const fields = {
    "#selected-name": row.dataset.name,
    "#selected-grade": row.dataset.grade,
    "#selected-description": row.dataset.description,
    "#selected-family": row.dataset.family,
    "#selected-status": row.dataset.status,
    "#status-selection": `${row.dataset.name} · ${row.dataset.grade}`,
  };

  Object.entries(fields).forEach(([selector, value]) => {
    const element = document.querySelector(selector);
    if (element && value) element.textContent = value;
  });
};

const selectResultRow = (row) => {
  resultRows.forEach((candidate) => {
    const selected = candidate === row;
    candidate.classList.toggle("selected", selected);
    candidate.setAttribute("aria-selected", String(selected));
    candidate.tabIndex = selected ? 0 : -1;
  });
  updateSelectedContext(row);
  document.body.dataset.selectedResult = row.dataset.grade ?? "";
};

const exposeDatasheetConsequence = (row) => {
  selectResultRow(row);
  document.body.dataset.datasheetConsequence = row.dataset.grade ?? "";
  setInteractionStatus(`Open datasheet ready for ${row.dataset.name ?? "selected material"}`);
};

resultRows.forEach((row) => {
  row.addEventListener("click", (event) => {
    if (event.target instanceof HTMLInputElement) return;
    selectResultRow(row);
  });
  row.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      exposeDatasheetConsequence(row);
    }
  });
});

openDatasheet?.addEventListener("click", () => {
  const selected = document.querySelector("[data-result-row][aria-selected='true']");
  if (selected) exposeDatasheetConsequence(selected);
});

splitters.forEach((splitter) => {
  splitter.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();

    const isNavigator = splitter.classList.contains("navigator-divider");
    const property = isNavigator ? "--navigator-width" : "--context-width";
    const minimum = Number(splitter.getAttribute("aria-valuemin"));
    const maximum = Number(splitter.getAttribute("aria-valuemax"));
    const current = Number(splitter.getAttribute("aria-valuenow"));
    const direction = isNavigator ? 1 : -1;
    let next = current;

    if (event.key === "Home") {
      next = minimum;
    } else if (event.key === "End") {
      next = maximum;
    } else {
      next = current + (event.key === "ArrowRight" ? 8 : -8) * direction;
      next = Math.max(minimum, Math.min(maximum, next));
    }

    document.documentElement.style.setProperty(property, `${next}px`);
    splitter.setAttribute("aria-valuenow", String(next));
  });
});
