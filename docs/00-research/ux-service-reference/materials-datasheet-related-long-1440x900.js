(() => {
  const panel = document.querySelector("#overview-panel");
  const tabButtons = [...document.querySelectorAll("[role='tab']")];
  const relatedTab = document.querySelector("#tab-related");
  const body = document.body;
  if (!panel || !relatedTab) return;

  const relationships = [
    {
      direction:
        "Forward · validation specimen derived from this selected material Record",
      record: "DP780 long-cycle validation specimen — east press line / replicate 03",
      type: "Test Data record",
      revision: "r2 · exact",
      consequence: "Open the exact related Record",
      key: "DP780-LONG-CYCLE-03",
      detail:
        "Forward relation from the selected DP780 Record to the long-cycle validation specimen. The exact revision remains read-only and the current Record stays selected in the navigator.",
    },
    {
      direction:
        "Reverse · available solver-card record prepared for this selected material Record",
      record: "DP780 solver-card delivery package — OpenRadioss thin-shell baseline",
      type: "Solver card record",
      revision: "r1 · exact",
      consequence: "Open the exact related Record",
      key: "DP780-OPENRADIOSS-CARD-01",
      detail:
        "Reverse relation from an available solver-card reference back to this selected Record. Open the exact related Record to inspect its own governed context without mutating this relation.",
    },
  ];

  const relationRows = relationships
    .map(
      (relation, index) => `
        <tr class="relation-row${index === 0 ? " selected" : ""}" data-relation-key="${relation.key}" tabindex="-1">
          <td class="relation-direction" title="${relation.direction}">${relation.direction}</td>
          <th scope="row" class="relation-record">
            <button class="relation-select" type="button" data-relation-index="${index}" title="${relation.record}">
              ${relation.record}
            </button>
          </th>
          <td class="relation-type">${relation.type}</td>
          <td class="relation-revision">${relation.revision}</td>
          <td class="relation-consequence">${relation.consequence}</td>
        </tr>`,
    )
    .join("");

  panel.innerHTML = `
    <div class="related-panel" data-state="related-long">
      <section class="related-list" aria-labelledby="related-title">
        <div class="related-heading">
          <div>
            <h3 id="related-title">Related records</h3>
            <span class="section-subtitle">Forward and reverse exact-revision links</span>
          </div>
          <span class="section-context">2 relations</span>
        </div>
        <div class="related-table-scroll">
          <table class="related-table">
            <caption class="sr-only">Related records for DP780 synthetic demo steel</caption>
            <colgroup>
              <col class="relation-direction-column">
              <col class="relation-record-column">
              <col class="relation-type-column">
              <col class="relation-revision-column">
              <col class="relation-consequence-column">
            </colgroup>
            <thead>
              <tr>
                <th scope="col">Relationship</th>
                <th scope="col">Related Record</th>
                <th scope="col">Record type</th>
                <th scope="col">Exact revision</th>
                <th scope="col">Task consequence</th>
              </tr>
            </thead>
            <tbody>${relationRows}</tbody>
          </table>
        </div>
      </section>
      <aside id="related-context" class="related-context" aria-labelledby="related-context-title">
        <div class="related-context-heading">
          <h3 id="related-context-title">Selected relation</h3>
          <span id="related-context-direction" class="section-subtitle"></span>
        </div>
        <p id="related-context-record" class="related-context-record"></p>
        <dl class="related-context-facts">
          <div><dt>Record type</dt><dd id="related-context-type"></dd></div>
          <div><dt>Exact revision</dt><dd id="related-context-revision"></dd></div>
        </dl>
        <p id="related-context-detail" class="related-context-detail"></p>
        <button id="open-related-record" class="button primary-action" type="button">Open related Record</button>
        <p class="related-context-note">The current DP780 Record and navigator selection stay intact.</p>
      </aside>
    </div>`;

  const rows = [...panel.querySelectorAll(".relation-row")];
  const contextDirection = panel.querySelector("#related-context-direction");
  const contextRecord = panel.querySelector("#related-context-record");
  const contextType = panel.querySelector("#related-context-type");
  const contextRevision = panel.querySelector("#related-context-revision");
  const contextDetail = panel.querySelector("#related-context-detail");
  const openButton = panel.querySelector("#open-related-record");

  const activateTab = () => {
    tabButtons.forEach((candidate) => {
      const selected = candidate === relatedTab;
      candidate.classList.toggle("active", selected);
      candidate.setAttribute("aria-selected", String(selected));
      candidate.tabIndex = selected ? 0 : -1;
    });
    body.dataset.activeTab = "Related";
  };

  const selectRelation = (index, focus = false) => {
    const relation = relationships[index];
    if (!relation) return;
    rows.forEach((row, rowIndex) => {
      const selected = rowIndex === index;
      row.classList.toggle("selected", selected);
      row.setAttribute("aria-selected", String(selected));
      row.tabIndex = selected ? 0 : -1;
    });
    contextDirection.textContent = relation.direction;
    contextRecord.textContent = relation.record;
    contextType.textContent = relation.type;
    contextRevision.textContent = relation.revision;
    contextDetail.textContent = relation.detail;
    body.dataset.relatedSelection = relation.key;
    body.dataset.relatedRecordRevision = relation.revision;
    if (focus) rows[index].querySelector(".relation-select")?.focus();
  };

  rows.forEach((row, index) => {
    const selectButton = row.querySelector(".relation-select");
    selectButton?.addEventListener("click", () => selectRelation(index));
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectRelation(index, true);
      }
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const next = event.key === "ArrowDown" ? Math.min(rows.length - 1, index + 1) : Math.max(0, index - 1);
        rows[next].focus();
      }
    });
  });

  openButton?.addEventListener("click", () => {
    const key = body.dataset.relatedSelection || relationships[0].key;
    const revision = body.dataset.relatedRecordRevision || relationships[0].revision;
    body.dataset.relatedRecordOpen = key;
    body.dataset.relatedOpenRevision = revision;
    history.replaceState(null, "", `#related=${encodeURIComponent(key)}`);
    const status = document.querySelector("#interaction-status");
    if (status) status.textContent = `Opened exact related Record · ${key} · ${revision}`;
  });

  relatedTab.addEventListener("click", activateTab);
  relatedTab.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      activateTab();
    }
  });

  selectRelation(0);
  activateTab();

  if (window.innerWidth === 1366) {
    document.documentElement.style.setProperty("--navigator-width", "244px");
    const divider = document.querySelector("[data-region='navigator-divider']");
    const navigator = document.querySelector("[data-region='navigator']");
    divider?.setAttribute("aria-valuemin", "200");
    divider?.setAttribute("aria-valuemax", "345");
    if (divider && navigator) divider.setAttribute("aria-valuenow", String(Math.round(navigator.getBoundingClientRect().width)));
  }
})();
