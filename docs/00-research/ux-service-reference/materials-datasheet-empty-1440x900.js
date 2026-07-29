(() => {
  const panel = document.querySelector("#overview-panel");
  const tabButtons = [...document.querySelectorAll("[role='tab']")];
  const overviewTab = document.querySelector("#tab-overview");
  const commandBack = document.querySelector("#back-to-results");
  const body = document.body;
  if (!panel || !overviewTab) return;

  // Empty removes only governed values and delivery, never the selected Record context.
  const recordHeader = document.querySelector(".record-header");
  recordHeader?.querySelector("#record-title")?.replaceChildren("DP780 synthetic demo steel");
  const recordMeta = recordHeader?.querySelector(".record-meta");
  if (recordMeta) {
    recordMeta.innerHTML =
      '<span>DP780-REF</span><span>Metal</span><span class="draft-state">Draft</span>';
  }
  recordHeader?.querySelector(".synthetic-note")?.replaceChildren(
    "Synthetic reference data · not validated engineering data",
  );
  const recordStatus = recordHeader?.querySelector(".record-status");
  if (recordStatus) {
    recordStatus.innerHTML =
      '<span class="status-label">Current revision</span><strong>r1 · Draft</strong>';
  }

  panel.innerHTML = `
    <div class="empty-panel" data-state="empty">
      <section class="empty-main" aria-labelledby="empty-title">
        <div class="empty-heading">
          <h3 id="empty-title">No governed data to display</h3>
          <span class="section-subtitle">Selected Record · DP780-REF</span>
        </div>
        <p class="empty-explanation">
          This selected Record has no displayable governed properties, curves or available solver card.
          Nothing has been inferred or substituted for the missing data.
        </p>
        <button id="empty-back-to-results" class="button primary-action" type="button">Back to results</button>
      </section>
      <aside class="empty-context" aria-labelledby="empty-context-title">
        <div class="empty-context-heading">
          <h3 id="empty-context-title">Delivery unavailable</h3>
          <span class="section-subtitle">Selected Record context</span>
        </div>
        <p>
          Native solver-card delivery is unavailable because this Record has no governed properties
          or representative response to support a card preview.
        </p>
        <p class="empty-context-note">Choose another Record from the catalog or return to the result set.</p>
      </aside>
    </div>`;

  const activateOverview = () => {
    tabButtons.forEach((candidate) => {
      const selected = candidate === overviewTab;
      candidate.classList.toggle("active", selected);
      candidate.setAttribute("aria-selected", String(selected));
      candidate.tabIndex = selected ? 0 : -1;
    });
    body.dataset.activeTab = "Overview";
  };

  const returnToResults = (event) => {
    event?.preventDefault();
    body.dataset.emptyReturn = "results";
    body.dataset.restoredSelection = "DP780-REF";
    history.replaceState(null, "", "#results?from=datasheet-empty");
    const status = document.querySelector("#interaction-status");
    if (status) status.textContent = "Returned to results · DP780-REF selection preserved";
  };

  commandBack?.addEventListener("click", returnToResults);
  document.querySelector("#empty-back-to-results")?.addEventListener("click", returnToResults);
  overviewTab.addEventListener("click", activateOverview);
  overviewTab.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      activateOverview();
    }
  });

  commandBack?.setAttribute("aria-hidden", "true");
  activateOverview();

  if (window.innerWidth === 1366) {
    document.documentElement.style.setProperty("--navigator-width", "244px");
    const divider = document.querySelector("[data-region='navigator-divider']");
    const navigator = document.querySelector("[data-region='navigator']");
    divider?.setAttribute("aria-valuemin", "200");
    divider?.setAttribute("aria-valuemax", "345");
    if (divider && navigator) divider.setAttribute("aria-valuenow", String(Math.round(navigator.getBoundingClientRect().width)));
  }
})();
