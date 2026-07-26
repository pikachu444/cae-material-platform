const tree = document.querySelector("#contents-tree");
const treeFind = document.querySelector("#tree-find");
const treeNext = document.querySelector("#tree-find-next");
const treeStatus = document.querySelector("#tree-find-status");
const treeClear = document.querySelector("#tree-find-clear");

if (tree && treeFind && treeNext && treeStatus && treeClear) {
  const rows = [...tree.querySelectorAll("[role='treeitem']")];
  const rowById = new Map(rows.map((row) => [row.id, row]));
  let currentMatches = rows;
  let nextMatchIndex = 0;
  tree.dataset.keyboardNavigation = "true";

  const includeAncestors = (row, visible) => {
    let parentId = row.dataset.parent;
    while (parentId) {
      visible.add(parentId);
      parentId = rowById.get(parentId)?.dataset.parent ?? "";
    }
  };

  const applyTreeSearch = () => {
    const query = treeFind.value.trim().toLocaleLowerCase();
    const matches = query
      ? rows.filter((row) => row.textContent.toLocaleLowerCase().includes(query))
      : rows;
    currentMatches = matches;
    nextMatchIndex = 0;
    const visible = new Set(matches.map((row) => row.id));
    matches.forEach((row) => includeAncestors(row, visible));
    rows.forEach((row) => { row.hidden = !visible.has(row.id); });
    treeStatus.textContent = query
      ? `${matches.length} match${matches.length === 1 ? "" : "es"} · ancestor path retained`
      : "Database · Profile · Table · Folder · Record";
    treeClear.hidden = !query;
  };

  const focusRow = (offset) => {
    const visibleRows = rows.filter((row) => !row.hidden);
    const current = visibleRows.indexOf(document.activeElement);
    const next = visibleRows[Math.max(0, Math.min(visibleRows.length - 1, current + offset))];
    if (next) {
      rows.forEach((row) => { row.tabIndex = -1; });
      next.tabIndex = 0;
      next.focus();
    }
  };

  treeFind.addEventListener("input", applyTreeSearch);
  treeNext.addEventListener("click", () => {
    if (!currentMatches.length) return;
    const next = currentMatches[nextMatchIndex % currentMatches.length];
    rows.forEach((row) => { row.tabIndex = -1; });
    next.tabIndex = 0;
    next.focus();
    nextMatchIndex += 1;
  });
  treeClear.addEventListener("click", () => {
    treeFind.value = "";
    applyTreeSearch();
    treeFind.focus();
  });
  tree.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      focusRow(event.key === "ArrowDown" ? 1 : -1);
    } else if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      const visibleRows = rows.filter((row) => !row.hidden);
      const next = event.key === "Home" ? visibleRows[0] : visibleRows[visibleRows.length - 1];
      if (next) {
        rows.forEach((row) => { row.tabIndex = -1; });
        next.tabIndex = 0;
        next.focus();
      }
    } else if (event.key === "Enter") {
      rows.forEach((row) => row.removeAttribute("aria-selected"));
      document.activeElement?.setAttribute("aria-selected", "true");
    }
  });
}

document.querySelectorAll(".plot-toggle").forEach((button) => {
  button.addEventListener("click", () => {
    const isVisible = button.classList.toggle("active");
    const curve = button.closest(".model-tree-row")?.querySelector("span");
    const name = curve?.textContent?.trim() || "curve";
    button.textContent = isVisible ? "◉" : "○";
    button.title = isVisible ? "Hide from plot" : "Show on plot";
    button.setAttribute("aria-label", `${isVisible ? "Hide" : "Show"} ${name} ${isVisible ? "from" : "on"} plot`);
  });
});
