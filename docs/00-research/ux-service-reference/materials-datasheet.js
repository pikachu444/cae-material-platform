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

(() => {
  const plot = document.querySelector(".response-plot");
  const frame = plot?.closest(".plot-frame");
  const sourceElement = plot?.dataset.seriesSource
    ? document.querySelector(plot.dataset.seriesSource)
    : null;
  if (!plot || !frame || !sourceElement) return;

  let series;
  try {
    series = JSON.parse(sourceElement.textContent || "[]").map((point) => ({
      point: Number(point.point),
      strain: Number(point.strain),
      stress_mpa: Number(point.stress_mpa),
    }));
  } catch (error) {
    console.error("Representative response series could not be parsed", error);
    return;
  }
  if (
    !series.length ||
    series.some(
      (point, index) =>
        point.point !== index + 1 ||
        !Number.isFinite(point.strain) ||
        !Number.isFinite(point.stress_mpa),
    )
  ) {
    console.error("Representative response series is not an ordered finite point set");
    return;
  }

  const gridRows = document.querySelector("#response-point-rows");
  const gridScrollShell = document.querySelector("[data-response-grid-scroll-shell]");
  const gridScroll = document.querySelector("#response-grid-scroll");
  const gridScrollbar = document.querySelector("#response-grid-scrollbar-y");
  const gridThumb = gridScrollbar?.querySelector(".response-grid-scrollbar-thumb");
  const responseLayout = plot.closest(".response-layout");
  const svgNamespace = "http://www.w3.org/2000/svg";

  const createElement = (name, attributes = {}) => {
    const element = document.createElementNS(svgNamespace, name);
    Object.entries(attributes).forEach(([attribute, value]) => {
      element.setAttribute(attribute, String(value));
    });
    return element;
  };

  const numeric = (value, digits = 3) => Number(value.toFixed(digits));

  const niceStep = (roughStep, factors) => {
    const exponent = Math.floor(Math.log10(roughStep));
    const candidates = [];
    for (let power = exponent - 1; power <= exponent + 3; power += 1) {
      factors.forEach((factor) => candidates.push(factor * 10 ** power));
    }
    return Math.min(...candidates.filter((candidate) => candidate >= roughStep - 1e-12));
  };

  const deriveAxis = (minimum, maximum, ratio, intervals, factors) => {
    const paddedMaximum = maximum + (maximum - minimum) * ratio;
    const roughStep = (paddedMaximum - minimum) / intervals;
    const step = niceStep(roughStep, factors);
    return {
      paddedMaximum,
      niceStep: step,
      domainMaximum: Math.ceil(paddedMaximum / step - 1e-12) * step,
    };
  };

  const renderPointGrid = () => {
    if (!gridRows) return;
    const rows = series.map((point) => {
      const row = document.createElement("tr");
      const pointCell = document.createElement("th");
      pointCell.scope = "row";
      pointCell.className = "numeric";
      pointCell.textContent = String(point.point);
      const strainCell = document.createElement("td");
      strainCell.className = "numeric";
      strainCell.textContent = point.strain.toFixed(3);
      const stressCell = document.createElement("td");
      stressCell.className = "numeric";
      stressCell.textContent = point.stress_mpa.toLocaleString("en-US");
      row.append(pointCell, strainCell, stressCell);
      return row;
    });
    gridRows.replaceChildren(...rows);
    const table = gridRows.closest("table");
    if (table) {
      table.dataset.seriesSource = plot.dataset.seriesSource;
      table.dataset.seriesPointCount = String(series.length);
    }
  };

  const syncGridScrollbar = () => {
    if (!gridScroll || !gridScrollShell || !gridScrollbar || !gridThumb) return;
    const range = Math.max(0, gridScroll.scrollHeight - gridScroll.clientHeight);
    const overflowing = range > 1;
    gridScrollShell.dataset.overflow = String(overflowing);
    gridScrollbar.hidden = !overflowing;
    gridScrollbar.setAttribute("aria-valuemin", "0");
    gridScrollbar.setAttribute("aria-valuemax", String(Math.round(range)));
    if (!overflowing) {
      gridScrollbar.setAttribute("aria-valuenow", "0");
      gridThumb.style.height = "0px";
      gridThumb.style.transform = "translateY(0px)";
      return;
    }
    const trackLength = gridScrollbar.clientHeight;
    const viewportLength = gridScroll.clientHeight;
    const contentLength = gridScroll.scrollHeight;
    const thumbLength = Math.max(36, Math.round((viewportLength / contentLength) * Math.max(0, trackLength - 4)));
    const available = Math.max(0, trackLength - 4 - thumbLength);
    const offset = Math.round((gridScroll.scrollTop / range) * available);
    gridThumb.style.height = `${thumbLength}px`;
    gridThumb.style.transform = `translateY(${offset}px)`;
    gridScrollbar.setAttribute("aria-valuenow", String(Math.round(gridScroll.scrollTop)));
  };

  const syncResponseLayoutHeight = () => {
    if (!responseLayout || !gridScrollShell) return;
    if (window.getComputedStyle(responseLayout).display !== "grid") {
      responseLayout.style.removeProperty("height");
      return;
    }
    const legend = frame.querySelector(".plot-legend");
    const plotHeight = plot.getBoundingClientRect().height;
    const legendHeight = legend?.getBoundingClientRect().height ?? 0;
    if (plotHeight > 0) {
      responseLayout.style.height = `${Math.ceil(plotHeight + legendHeight + 2)}px`;
    }
  };

  const setGridScroll = (value) => {
    if (!gridScroll) return;
    const maximum = Math.max(0, gridScroll.scrollHeight - gridScroll.clientHeight);
    gridScroll.scrollTo({ top: Math.max(0, Math.min(maximum, value)), behavior: "auto" });
    syncGridScrollbar();
  };

  const bindGridScrollbar = () => {
    if (!gridScroll || !gridScrollbar || !gridThumb) return;
    gridScroll.addEventListener("scroll", syncGridScrollbar, { passive: true });
    gridScroll.addEventListener(
      "wheel",
      (event) => {
        if (gridScroll.scrollHeight <= gridScroll.clientHeight) return;
        const before = gridScroll.scrollTop;
        gridScroll.scrollBy({ top: event.deltaY, behavior: "auto" });
        if (gridScroll.scrollTop !== before) event.preventDefault();
      },
      { passive: false },
    );
    gridScroll.addEventListener("keydown", (event) => {
      const current = gridScroll.scrollTop;
      const viewport = gridScroll.clientHeight;
      let next = null;
      if (event.key === "ArrowDown") next = current + 36;
      else if (event.key === "ArrowUp") next = current - 36;
      else if (event.key === "PageDown") next = current + viewport * 0.8;
      else if (event.key === "PageUp") next = current - viewport * 0.8;
      else if (event.key === "Home") next = 0;
      else if (event.key === "End") next = gridScroll.scrollHeight - viewport;
      if (next === null || gridScroll.scrollHeight <= viewport) return;
      event.preventDefault();
      setGridScroll(next);
    });
    gridScrollbar.addEventListener("keydown", (event) => {
      const current = gridScroll.scrollTop;
      const viewport = gridScroll.clientHeight;
      let next = null;
      if (event.key === "ArrowDown") next = current + 36;
      else if (event.key === "ArrowUp") next = current - 36;
      else if (event.key === "PageDown") next = current + viewport * 0.8;
      else if (event.key === "PageUp") next = current - viewport * 0.8;
      else if (event.key === "Home") next = 0;
      else if (event.key === "End") next = gridScroll.scrollHeight - viewport;
      if (next === null) return;
      event.preventDefault();
      setGridScroll(next);
    });
    gridScrollbar.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      event.preventDefault();
      const railBox = gridScrollbar.getBoundingClientRect();
      const thumbBox = gridThumb.getBoundingClientRect();
      const maximum = Math.max(0, gridScroll.scrollHeight - gridScroll.clientHeight);
      const available = Math.max(1, railBox.height - 4 - thumbBox.height);
      if (event.target !== gridThumb) {
        const offset = event.clientY - railBox.top - 2;
        setGridScroll(((offset - thumbBox.height / 2) / available) * maximum);
        return;
      }
      gridScrollbar.setPointerCapture?.(event.pointerId);
      const startPointer = event.clientY;
      const startValue = gridScroll.scrollTop;
      const move = (moveEvent) => {
        setGridScroll(startValue + ((moveEvent.clientY - startPointer) / available) * maximum);
      };
      const end = (endEvent) => {
        gridScrollbar.releasePointerCapture?.(endEvent.pointerId);
        gridScrollbar.removeEventListener("pointermove", move);
        gridScrollbar.removeEventListener("pointerup", end);
        gridScrollbar.removeEventListener("pointercancel", end);
      };
      gridScrollbar.addEventListener("pointermove", move);
      gridScrollbar.addEventListener("pointerup", end);
      gridScrollbar.addEventListener("pointercancel", end);
    });
  };

  const mapPoint = (point, area, domains) => ({
    x: area.left + (point.strain / domains.strain.domainMaximum) * area.width,
    y: area.bottom - (point.stress_mpa / domains.stress.domainMaximum) * area.height,
  });

  const scheduleRender = () => {
    if (scheduleRender.pending) return;
    scheduleRender.pending = true;
    window.requestAnimationFrame(() => {
      scheduleRender.pending = false;
      renderPlot();
    });
  };

  const renderPlot = () => {
    const plotBox = plot.getBoundingClientRect();
    const width = plotBox.width;
    const height = plotBox.height;
    if (width < 1 || height < 1) return;
    const key = `${numeric(width, 2)}x${numeric(height, 2)}`;
    if (renderPlot.lastKey === key) return;

    const seriesBounds = {
      strain: {
        minimum: Math.min(...series.map((point) => point.strain)),
        maximum: Math.max(...series.map((point) => point.strain)),
      },
      stress: {
        minimum: Math.min(...series.map((point) => point.stress_mpa)),
        maximum: Math.max(...series.map((point) => point.stress_mpa)),
      },
    };
    const ratio = Number(plot.dataset.axisHeadroomRatio);
    const factors = plot.dataset.axisNiceStepFactors.split(",").map(Number);
    const domains = {
      strain: deriveAxis(
        seriesBounds.strain.minimum,
        seriesBounds.strain.maximum,
        ratio,
        Number(plot.dataset.axisTargetIntervalsStrain),
        factors,
      ),
      stress: deriveAxis(
        seriesBounds.stress.minimum,
        seriesBounds.stress.maximum,
        ratio,
        Number(plot.dataset.axisTargetIntervalsStress),
        factors,
      ),
    };

    const margin = { left: 78, right: 24, top: 28, bottom: 54 };
    const area = {
      left: margin.left,
      right: width - margin.right,
      top: margin.top,
      bottom: height - margin.bottom,
      width: width - margin.left - margin.right,
      height: height - margin.top - margin.bottom,
    };
    if (area.width <= 0 || area.height <= 0) return;

    const xTicks = Array.from({ length: 6 }, (_, index) => index * 0.05);
    const yTicks = Array.from({ length: 5 }, (_, index) => index * 250);
    const title = plot.querySelector("title");
    const description = plot.querySelector("desc");
    const grid = createElement("g", { class: "plot-grid", "aria-hidden": "true" });
    const axes = createElement("g", { class: "plot-axis", "aria-hidden": "true" });
    const labels = createElement("g", { class: "plot-labels" });

    xTicks.forEach((value) => {
      const x = area.left + (value / domains.strain.domainMaximum) * area.width;
      grid.appendChild(createElement("line", { x1: x, y1: area.top, x2: x, y2: area.bottom }));
      const label = createElement("text", {
        x,
        y: area.bottom + 18,
        "text-anchor": value === 0 ? "start" : value === 0.25 ? "end" : "middle",
        "data-tick": "x",
      });
      label.textContent = value === 0 ? "0" : value.toFixed(2);
      labels.appendChild(label);
    });

    yTicks.forEach((value) => {
      const y = area.bottom - (value / domains.stress.domainMaximum) * area.height;
      grid.appendChild(createElement("line", { x1: area.left, y1: y, x2: area.right, y2: y }));
      const label = createElement("text", {
        x: area.left - 10,
        y: y + 4,
        "text-anchor": "end",
        "data-tick": "y",
      });
      label.textContent = value.toLocaleString("en-US");
      labels.appendChild(label);
    });

    axes.append(
      createElement("line", { x1: area.left, y1: area.bottom, x2: area.right, y2: area.bottom }),
      createElement("line", { x1: area.left, y1: area.top, x2: area.left, y2: area.bottom }),
    );

    const xTitle = createElement("text", {
      class: "axis-title",
      x: area.left + area.width / 2,
      y: height - 11,
      "text-anchor": "middle",
      "data-axis-title": "x",
    });
    xTitle.textContent = "Engineering strain";
    labels.appendChild(xTitle);

    const yTitle = createElement("text", {
      class: "axis-title",
      transform: `translate(17 ${area.top + area.height / 2}) rotate(-90)`,
      "text-anchor": "middle",
      "data-axis-title": "y",
    });
    yTitle.textContent = "Engineering stress (MPa)";
    labels.appendChild(yTitle);

    const points = series.map((point) => mapPoint(point, area, domains));
    const response = createElement("polyline", {
      class: "response-line",
      points: points.map((point) => `${numeric(point.x, 4)},${numeric(point.y, 4)}`).join(" "),
      "data-point-count": series.length,
    });

    plot.setAttribute("viewBox", `0 0 ${width} ${height}`);
    plot.dataset.renderedWidth = numeric(width, 2);
    plot.dataset.renderedHeight = numeric(height, 2);
    plot.dataset.plotLeft = numeric(area.left, 2);
    plot.dataset.plotRight = numeric(area.right, 2);
    plot.dataset.plotTop = numeric(area.top, 2);
    plot.dataset.plotBottom = numeric(area.bottom, 2);
    plot.dataset.axisMaxStrain = numeric(domains.strain.domainMaximum, 4);
    plot.dataset.axisMaxStressMpa = numeric(domains.stress.domainMaximum, 2);
    plot.dataset.seriesPointCount = String(series.length);

    const children = [title, description, grid, axes, response, labels].filter(Boolean);
    plot.replaceChildren(...children);
    syncResponseLayoutHeight();
    renderPlot.lastKey = key;
  };

  renderPointGrid();
  bindGridScrollbar();
  renderPlot.lastKey = "";
  scheduleRender.pending = false;
  renderPlot();
  syncResponseLayoutHeight();
  syncGridScrollbar();
  if ("ResizeObserver" in window) {
    const observer = new ResizeObserver(() => {
      scheduleRender();
      syncResponseLayoutHeight();
      syncGridScrollbar();
    });
    observer.observe(frame);
    if (gridScrollShell) observer.observe(gridScrollShell);
  }
  window.addEventListener("resize", () => {
    scheduleRender();
    syncResponseLayoutHeight();
    syncGridScrollbar();
  }, { passive: true });
  window.MaterialsResponseGrid = {
    series,
    render: scheduleRender,
    sync: syncGridScrollbar,
    scrollTo: setGridScroll,
  };
})();
