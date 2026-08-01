(() => {
  "use strict";

  const params = new URLSearchParams(window.location.search);
  const requestedRole = params.get("role");
  const requestedState = params.get("state");
  const role = requestedRole === "reviewer" ? "reviewer" : "user";
  const state = requestedState || "normal";
  const NORMAL_REQUEST_COUNT = 50;
  const NORMAL_PENDING_COUNT = 40;
  const NORMAL_DECIDED_COUNT = 10;
  const LOCAL_HISTORY_COUNT = 2;

  document.body.dataset.role = role;
  document.body.dataset.state = state;

  const sharedSession = {
    id: "modeling-session-local",
    task: "Resume Modeling session",
    reason: "metal · Fit · DP780 tensile r3 · 2 selected curves",
    state: "Local session",
    time: "Today · 09:18",
    action: "resume",
    local: true,
  };

  const sharedCard = {
    id: "solver-card-local",
    task: "Downloaded solver card",
    reason: "DP780 · OpenRadioss .rad",
    state: "Delivered",
    time: "27 Jul · 16:42",
    action: "open-card",
    local: true,
  };

  const taskTypes = [
    "Material data review",
    "Test data review",
    "Model selection review",
    "Processing output review",
    "Solver card review",
    "Import provenance review",
    "Curve selection review",
    "Fit result review",
    "Mapping review",
    "Evidence review",
  ];

  const reasonFamilies = [
    "Check the uploaded tensile data",
    "Confirm units and test condition",
    "Verify the selected model context",
    "Confirm processing output before review",
    "Check solver mapping before delivery",
    "Keep source provenance with the request",
    "Confirm the included curves and scope",
    "Review the fit result against source data",
    "Check exact field mappings and exceptions",
    "Keep evidence attached to the immutable revision",
  ];

  const reasonDetails = [
    "for the first specimen set",
    "for the repeat curve set",
    "before the next modeling session",
    "against the submitted source file",
    "before a reviewer decision",
  ];

  const longReasons = [
    "Confirm the submitted tensile data keeps the original unit text, records the test condition, and uses the selected exact Test Data revision before the review decision is recorded.",
    "Check that the normalized stress and strain quantities preserve their source semantics and that no hidden conversion or manual curve edit was applied.",
    "Verify the selected model context is still current for this request and that the saved result remains separate from the recommendation and review decision.",
    "Confirm the solver mapping report identifies exact, transformed, approximated, and unsupported fields before any delivery action is considered.",
    "Review the provenance context and the reason supplied by the requestor; retain the immutable revision when asking for a correction.",
    "Check that the selected Test Data revision, processing output, and material state remain aligned after the upstream change.",
    "Confirm the request is still authorized for this Reviewer and that the expected manifest has not become stale.",
    "Review the condition-aware property evidence and keep technical identifiers available only in Advanced or Evidence.",
    "Verify that the request reason is actionable and does not silently imply release, publish, or delivery.",
  ];

  const labels = {
    user: { context: "User queue", description: "Your pending requests and browser-local work.", statusRole: "User context", topbar: "Signed-in user" },
    reviewer: { context: "Reviewer queue", description: "Requests awaiting a decision, plus local work and outcomes.", statusRole: "Reviewer context", topbar: "Reviewer context" },
  };

  const refs = {
    queue: document.querySelector("[data-region='queue-scroll']"),
    status: document.querySelector("[data-queue-status]"),
    activityMain: document.querySelector("#activity-main"),
    region: document.querySelector("[data-region='queue-region']"),
    thumb: document.querySelector(".queue-scroll-thumb"),
  };

  function setText(selector, value) {
    const element = document.querySelector(selector);
    if (element) element.textContent = value;
  }

  function createElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function countLabel(count) {
    return `${count} ${count === 1 ? "item" : "items"}`;
  }

  function normalRequests() {
    return Array.from({ length: NORMAL_REQUEST_COUNT }, (_, index) => {
      const pending = index < NORMAL_PENDING_COUNT;
      const decision = index % 4 === 0 ? "Changes requested" : "Approved";
      const day = index < 3 ? "Today" : `${27 - Math.floor((index - 3) / 3)} Jul`;
      const hour = String(8 + (index % 10)).padStart(2, "0");
      const minute = String((index * 7) % 60).padStart(2, "0");
      return {
        id: role === "reviewer" && pending ? `review-${index + 1}` : `review-request-${String(index + 1).padStart(2, "0")}`,
        task: taskTypes[index % taskTypes.length],
        reason: `${reasonFamilies[index % reasonFamilies.length]} ${reasonDetails[Math.floor(index / reasonFamilies.length)]}`,
        state: pending ? "Needs a decision" : decision,
        time: `${day} · ${hour}:${minute}`,
        action: pending ? (role === "reviewer" ? "review" : "state") : "state",
        pending,
        server: true,
      };
    });
  }

  function requestFixturesForState(section) {
    if (state === "empty") return [];
    if (state === "loading") {
      if (section === "in-progress") return [sharedSession];
      if (section === "recent-outcomes") return [sharedCard];
      return [];
    }
    if (state === "long-row") {
      if (section === "needs-attention") {
        return [
          { id: "long-request-1", task: "Material data review", reason: longReasons[0], state: "Waiting for review", time: "Today · 09:24", action: "state", server: true },
          { id: "long-request-2", task: "Test data review", reason: longReasons[1], state: "Waiting for review", time: "Yesterday · 15:02", action: "state", server: true },
        ];
      }
      if (section === "in-progress") return [sharedSession];
      if (section === "recent-outcomes") return [sharedCard];
      return [];
    }
    if (state === "queue-error") {
      if (section === "in-progress") return [{ id: "queue-error-current", task: "Material data review", reason: "Current request remains available while the queue retries", state: "Waiting for review", time: "Today · 09:24", action: "state", server: true }, sharedSession];
      if (section === "recent-outcomes") return [sharedCard];
      return [];
    }
    if (state === "decision-blocked") {
      if (section === "needs-attention") return [{ id: "blocked-request", task: "Material data review", reason: "Review access is governed by the Reviewer or Administrator role", state: "Waiting for review", time: "Today · 09:24", action: "state", server: true }];
      return section === "in-progress" ? [sharedSession] : section === "recent-outcomes" ? [sharedCard] : [];
    }
    if (state === "decision-error" || state === "stale-unauthorized") {
      if (section === "needs-attention") return [{ id: "review-1", task: "Material data review", reason: "Check the uploaded tensile data", state: "Needs a decision", time: "Today · 09:24", action: "review", server: true }];
      return section === "in-progress" ? [sharedSession] : section === "recent-outcomes" ? [sharedCard] : [];
    }
    if (state === "long-decision-error") {
      if (section !== "needs-attention") return section === "in-progress" ? [sharedSession] : section === "recent-outcomes" ? [sharedCard] : [];
      const rows = [
        { id: "review-1", task: "Material data review", reason: "Check the uploaded tensile data", state: "Needs a decision", time: "Today · 09:24", action: "review", server: true },
        { id: "review-2", task: "Test data review", reason: "Confirm units and test condition", state: "Needs a decision", time: "Yesterday · 14:10", action: "review", server: true },
        { id: "review-3", task: "Solver card review", reason: "Confirm solver mapping before delivery", state: "Needs a decision", time: "27 Jul · 11:06", action: "review", server: true },
        { id: "review-4", task: "Material data review", reason: "Verify the selected model context", state: "Needs a decision", time: "26 Jul · 17:32", action: "review", server: true },
      ];
      longReasons.forEach((reason, index) => rows.push({ id: `review-long-${index + 1}`, task: taskTypes[(index + 4) % taskTypes.length], reason, state: "Needs a decision", time: `${25 - index} Jul · ${String(8 + index).padStart(2, "0")}:2${index}`, action: "review", server: true }));
      return rows;
    }
    return [];
  }

  function requestsFor(section) {
    if (state !== "normal") return requestFixturesForState(section);
    const requests = normalRequests();
    if (section === "needs-attention") return role === "reviewer" ? requests.filter((item) => item.pending) : [];
    if (section === "in-progress") return role === "user" ? [...requests.filter((item) => item.pending), sharedSession] : [sharedSession];
    if (section === "recent-outcomes") return [...requests.filter((item) => !item.pending), sharedCard];
    return [];
  }

  function allFixtureRows() {
    return ["needs-attention", "in-progress", "recent-outcomes"].flatMap((section) => requestsFor(section));
  }

  function makeActionButton(label, action, row) {
    const button = createElement("button", `queue-button ${action === "review" ? "primary" : ""}`, label);
    button.type = "button";
    button.dataset.action = action;
    if (row) button.dataset.rowId = row.id;
    button.setAttribute("aria-label", `${label}: ${row?.task || "Activity"}`);
    return button;
  }

  function makePassiveAction() {
    const passiveAction = createElement("span", "row-state", "—");
    passiveAction.dataset.passiveAction = "true";
    passiveAction.setAttribute("role", "img");
    passiveAction.setAttribute("aria-label", "No available action");
    return passiveAction;
  }

  function renderRow(item, section) {
    const row = createElement("tr", "queue-row");
    row.dataset.rowId = item.id;
    row.dataset.section = section;
    row.dataset.actionKind = item.action;
    if (item.server) row.dataset.source = "server";
    if (item.local) row.dataset.source = "browser-local";

    const task = createElement("td", "row-main");
    task.append(createElement("strong", "row-task", item.task));
    const reason = createElement("td", "row-reason", item.reason);
    const status = createElement("td", "row-status");
    status.append(createElement("strong", "row-state-label", item.state));
    const updated = createElement("td", "row-time");
    const time = createElement("time", "", item.time);
    updated.append(time);
    const action = createElement("td", "row-action");
    if (item.action === "review" && role === "reviewer") {
      const button = makeActionButton("Review", "review", item);
      if (item.id !== "review-1") button.classList.remove("primary");
      button.setAttribute("aria-expanded", "false");
      action.append(button);
    } else if (item.action === "resume") {
      action.append(makeActionButton("Resume Modeling", "resume", item));
    } else if (item.action === "open-card") {
      action.append(makeActionButton("Open card", "open-card", item));
    } else {
      action.append(makePassiveAction());
    }
    row.append(task, reason, status, updated, action);
    return row;
  }

  function sectionList(section) {
    return document.querySelector(`[data-list="${section}"]`);
  }

  function renderSection(section) {
    const list = sectionList(section);
    const table = document.querySelector(`[data-table="${section}"]`);
    const empty = document.querySelector(`[data-empty="${section}"]`);
    const loading = document.querySelector(`[data-loading="${section}"]`);
    if (!list || !table || !empty || !loading) return;
    list.replaceChildren();
    const rows = requestsFor(section);
    rows.forEach((item) => list.append(renderRow(item, section)));
    const count = document.querySelector(`[data-section-count="${section}"]`);
    if (count) count.textContent = state === "loading" ? "Loading…" : countLabel(rows.length);
    table.hidden = rows.length === 0;
    empty.hidden = rows.length !== 0 || (section === "in-progress" && state === "loading");
    loading.classList.toggle("is-visible", state === "loading" && section === defaultViewForState());
    loading.setAttribute("aria-busy", String(state === "loading" && section === defaultViewForState()));
    if (section === "in-progress" && state === "empty") empty.hidden = false;
  }

  function showQueueError(message) {
    let banner = document.querySelector(".activity-error");
    if (!banner) {
      banner = createElement("div", "activity-error");
      banner.setAttribute("role", "alert");
      banner.setAttribute("aria-live", "polite");
      const main = document.querySelector(".activity-heading");
      main?.after(banner);
    }
    banner.replaceChildren(createElement("span", "", message));
    const retry = createElement("button", "queue-button", "Retry");
    retry.type = "button";
    retry.dataset.action = "retry-queue";
    retry.setAttribute("aria-label", "Retry activity queue");
    banner.append(retry);
  }

  function hideQueueError() {
    document.querySelector(".activity-error")?.remove();
    if (refs.status) refs.status.textContent = "Queue refreshed";
  }

  function decisionMessage(text, visible = true) {
    const message = createElement("p", "decision-message", text);
    message.setAttribute("role", "alert");
    message.setAttribute("aria-live", "polite");
    message.hidden = !visible;
    return message;
  }

  function openDecision(row, item, initial = false) {
    if (role !== "reviewer" || row.nextElementSibling?.classList.contains("decision-row")) return;
    row.classList.add("is-selected");
    const reviewButton = row.querySelector("[data-action='review']");
    if (reviewButton) {
      reviewButton.setAttribute("aria-expanded", "true");
      reviewButton.classList.remove("primary");
    }

    const decisionRow = createElement("tr", "decision-row");
    decisionRow.dataset.rowId = item.id;
    const decisionCell = createElement("td", "decision-cell");
    decisionCell.colSpan = 5;
    const panel = createElement("div", "decision-panel");
    panel.dataset.rowId = item.id;
    panel.setAttribute("role", "region");
    panel.setAttribute("aria-label", "Review decision for selected request");
    const heading = createElement("div", "decision-heading");
    heading.append(createElement("strong", "", "Review decision"), createElement("span", "", "One request · one decision"));
    const close = createElement("button", "decision-close", "Close");
    close.type = "button";
    close.dataset.action = "close-review";
    close.setAttribute("aria-label", "Close review decision");
    heading.append(close);

    const context = createElement("p", "decision-context", `${item.task} · ${item.reason}`);
    const form = createElement("form", "decision-form");
    form.noValidate = true;
    const label = createElement("label", "", "Review reason");
    const textarea = createElement("textarea");
    textarea.id = `review-reason-${item.id}`;
    textarea.name = "review_reason";
    textarea.required = true;
    textarea.autocomplete = "off";
    textarea.placeholder = "Explain the approval or requested change…";
    textarea.value = initial && (state === "decision-error" || state === "stale-unauthorized" || state === "long-decision-error")
      ? "Units and source are complete; retain this request while the reviewer service recovers."
      : "";
    label.htmlFor = textarea.id;
    label.append(textarea);

    const choices = createElement("div", "decision-choice");
    choices.setAttribute("role", "group");
    choices.setAttribute("aria-label", "Decision choice");
    const approve = createElement("button", "queue-button", "Approve");
    approve.type = "button";
    approve.dataset.decision = "approved";
    const changes = createElement("button", "queue-button", "Request changes");
    changes.type = "button";
    changes.dataset.decision = "changes_requested";
    choices.append(approve, changes);
    let selectedDecision = state === "decision-error" || state === "stale-unauthorized" || state === "long-decision-error" ? "changes_requested" : "approved";
    const updateChoice = () => {
      approve.classList.toggle("is-chosen", selectedDecision === "approved");
      changes.classList.toggle("is-chosen", selectedDecision === "changes_requested");
      approve.setAttribute("aria-pressed", String(selectedDecision === "approved"));
      changes.setAttribute("aria-pressed", String(selectedDecision === "changes_requested"));
    };
    updateChoice();
    approve.addEventListener("click", () => { selectedDecision = "approved"; updateChoice(); });
    changes.addEventListener("click", () => { selectedDecision = "changes_requested"; updateChoice(); });

    const message = decisionMessage("", false);
    const footer = createElement("div", "decision-footer");
    const isServiceFailure = state === "decision-error" || state === "long-decision-error";
    const isAccessFailure = state === "stale-unauthorized";
    const record = createElement("button", "queue-button primary", "Record decision");
    record.type = "submit";
    record.dataset.action = "record-decision";
    const retry = createElement("button", "queue-button primary", "Retry decision");
    retry.type = "button";
    retry.dataset.action = "retry-decision";
    retry.hidden = !isServiceFailure;
    const refreshAccess = createElement("button", "queue-button primary", "Refresh access");
    refreshAccess.type = "button";
    refreshAccess.dataset.action = "refresh-access";
    refreshAccess.hidden = !isAccessFailure;
    record.hidden = isServiceFailure || isAccessFailure;
    const help = createElement(
      "span",
      "decision-help",
      isServiceFailure
        ? "Reason retained; retry will resubmit this decision."
        : isAccessFailure
          ? "Reason retained; refresh access before a new decision."
          : "Reason is required before submission.",
    );
    footer.append(record, retry, refreshAccess, help);

    form.append(label, choices, message, footer);
    panel.append(heading, context, form);
    decisionCell.append(panel);
    decisionRow.append(decisionCell);
    row.after(decisionRow);

    if (initial && (state === "decision-error" || state === "stale-unauthorized" || state === "long-decision-error")) {
      const failure = isAccessFailure
        ? "This review request is no longer current or you are not authorized. The selected request and reason remain available; refresh access before a new decision."
        : "Review service is unavailable. The selected request and reason remain available; retry this decision when the service is available.";
      message.textContent = failure;
      message.hidden = false;
      refs.status.textContent = isAccessFailure ? "Review access needs refresh" : "Decision not recorded";
    }

    let submitting = false;
    let attempts = 0;
    const setBusy = (busy) => {
      submitting = busy;
      panel.dataset.submitting = String(busy);
      panel.setAttribute("aria-busy", String(busy));
      [approve, changes, record, retry, refreshAccess, close, textarea].forEach((control) => { control.disabled = busy; });
      panel.dataset.submitAttempts = String(attempts);
    };
    const submit = () => {
      if (submitting) return;
      const reason = textarea.value.trim();
      if (!reason) {
        message.textContent = "Add a reason before recording this review decision.";
        message.hidden = false;
        textarea.setAttribute("aria-invalid", "true");
        textarea.focus();
        return;
      }
      attempts += 1;
      setBusy(true);
      refs.status.textContent = "Saving review decision…";
      if (isServiceFailure) {
        window.setTimeout(() => {
          setBusy(false);
          message.textContent = "Review service is unavailable. The selected request and reason remain available; retry this decision when the service is available.";
          message.hidden = false;
          retry.hidden = false;
          refs.status.textContent = "Decision not recorded";
        }, 80);
        return;
      }
      window.setTimeout(() => {
        const statusText = selectedDecision === "approved" ? "Approved" : "Changes requested";
        row.dataset.decision = selectedDecision;
        row.querySelector(".row-state-label").textContent = statusText;
        row.querySelector(".row-reason").textContent = `${statusText} · ${reason}`;
        row.dataset.actionKind = "state";
        row.querySelector(".row-action")?.replaceChildren(makePassiveAction());
        closeDecision(row);
        refs.status.textContent = "Decision recorded";
      }, 120);
    };
    form.addEventListener("submit", (event) => { event.preventDefault(); submit(); });
    retry.addEventListener("click", submit);
    refreshAccess.addEventListener("click", () => {
      if (submitting) return;
      message.textContent = "Access refresh requested. The selected request and reason remain available; no decision was sent.";
      message.hidden = false;
      refs.status.textContent = "Review access needs refresh";
    });
    close.addEventListener("click", () => closeDecision(row));
    textarea.addEventListener("input", () => { textarea.removeAttribute("aria-invalid"); });
    if (!initial) textarea.focus();
  }

  function closeDecision(row) {
    const button = row.querySelector("[data-action='review']");
    const decisionRow = row.nextElementSibling;
    if (decisionRow?.classList.contains("decision-row") && decisionRow.dataset.rowId === row.dataset.rowId) decisionRow.remove();
    row.classList.remove("is-selected");
    if (button) button.setAttribute("aria-expanded", "false");
    refs.status.textContent = "Activity queue";
    button?.focus();
    syncOverflowRail();
  }

  function defaultViewForState() {
    if (state === "normal") return role === "reviewer" ? "needs-attention" : "in-progress";
    if (state === "empty") return "in-progress";
    if (state === "loading" || state === "queue-error") return "in-progress";
    return "needs-attention";
  }

  function activateView(viewName, focus = false) {
    const selected = document.querySelector(`[data-view="${viewName}"]`);
    if (!selected) return;
    document.querySelectorAll("[data-view]").forEach((button) => {
      const active = button === selected;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-selected", String(active));
      button.tabIndex = active ? 0 : -1;
    });
    document.querySelectorAll("[data-section]").forEach((section) => {
      const active = section.dataset.section === viewName;
      section.hidden = !active;
      section.setAttribute("aria-hidden", String(!active));
    });
    if (refs.queue) refs.queue.scrollTop = 0;
    if (refs.status) refs.status.textContent = `${selected.textContent} view`;
    syncOverflowRail();
    if (focus) selected.focus();
  }

  function updateRoleChrome() {
    const copy = labels[role];
    setText("[data-role-label]", copy.context);
    setText("[data-role-description]", copy.description);
    setText("[data-role-context]", copy.topbar);
    setText("[data-status-role]", copy.statusRole);
    const sectionDescription = document.querySelector("[data-section='needs-attention'] [data-section-description]");
    if (sectionDescription) sectionDescription.textContent = role === "reviewer" ? "Submitted work waiting for your review." : "Requests you submitted that are still waiting for a decision.";
  }

  function setEmptyStateCopy() {
    if (state !== "empty") return;
    setText("[data-empty='needs-attention']", "Nothing needs your attention.");
    setText("[data-empty='recent-outcomes']", "No recent outcomes yet.");
  }

  function setContractMetadata() {
    if (!refs.region) return;
    const serverRows = allFixtureRows().filter((item) => item.server);
    const pendingRows = serverRows.filter((item) => item.pending || item.state === "Needs a decision" || item.state === "Waiting for review");
    const decidedRows = serverRows.filter((item) => item.state === "Approved" || item.state === "Changes requested");
    refs.region.dataset.serverRequestCount = String(state === "normal" ? NORMAL_REQUEST_COUNT : serverRows.length);
    refs.region.dataset.pendingCount = String(state === "normal" ? NORMAL_PENDING_COUNT : pendingRows.length);
    refs.region.dataset.decidedCount = String(state === "normal" ? NORMAL_DECIDED_COUNT : decidedRows.length);
    refs.region.dataset.localHistoryCount = String(LOCAL_HISTORY_COUNT);
    refs.region.dataset.roleDefaultView = defaultViewForState();
  }

  function render() {
    updateRoleChrome();
    setEmptyStateCopy();
    ["needs-attention", "in-progress", "recent-outcomes"].forEach(renderSection);
    setContractMetadata();
    activateView(defaultViewForState());
    if (state === "queue-error") showQueueError("Activity service is unavailable. Current and browser-local rows are preserved.");
    if (state === "decision-blocked") {
      const list = sectionList("needs-attention");
      const notice = createElement("tr", "queue-row queue-notice-row");
      notice.dataset.rowId = "decision-blocked-notice";
      notice.append(
        createElement("td", "row-main", "Decision access"),
        createElement("td", "row-reason", "Role-gated review command"),
        createElement("td", "row-status", "User role"),
        createElement("td", "row-time", "Now"),
        createElement("td", "row-action row-state", "Reviewer or Administrator required"),
      );
      list?.append(notice);
    }
    if (state === "empty") {
      document.querySelector("[data-action='start-modeling']")?.addEventListener("click", () => { refs.status.textContent = "Modeling start requested"; });
    }
    if (role === "reviewer" && (state === "decision-error" || state === "stale-unauthorized" || state === "long-decision-error")) {
      const row = document.querySelector("[data-row-id='review-1']") || document.querySelector(".queue-row[data-action-kind='review']");
      const item = { id: row?.dataset.rowId || "review-1", task: row?.querySelector(".row-task")?.textContent || "Material data review", reason: row?.querySelector(".row-reason")?.textContent || "Check the uploaded tensile data" };
      if (row) openDecision(row, item, true);
    }
    if (refs.status && state === "loading") refs.status.textContent = "Loading activity queue…";
    if (refs.status && state === "queue-error") refs.status.textContent = "Queue error";
    if (refs.status && state === "decision-blocked") refs.status.textContent = "Decision blocked by role";
    if (refs.status && (state === "decision-error" || state === "long-decision-error")) refs.status.textContent = "Decision not recorded";
    if (refs.status && state === "stale-unauthorized") refs.status.textContent = "Review access needs refresh";
    setText("[data-status-scroll]", "Local queue scroll");
    syncOverflowRail();
  }

  function syncOverflowRail() {
    const region = refs.region;
    const queue = refs.queue;
    const thumb = refs.thumb;
    if (!region || !queue || !thumb) return;
    const overflow = queue.scrollHeight > queue.clientHeight + 1;
    region.classList.toggle("has-overflow", overflow);
    if (!overflow) {
      thumb.style.height = "0px";
      thumb.style.transform = "translateY(0)";
      return;
    }
    const track = thumb.parentElement;
    const trackHeight = track?.clientHeight || queue.clientHeight;
    const ratio = Math.min(1, queue.clientHeight / Math.max(queue.scrollHeight, 1));
    const thumbHeight = Math.max(42, Math.round(trackHeight * ratio));
    const travel = Math.max(0, trackHeight - thumbHeight);
    const progress = queue.scrollTop / Math.max(queue.scrollHeight - queue.clientHeight, 1);
    thumb.style.height = `${thumbHeight}px`;
    thumb.style.transform = `translateY(${Math.round(travel * progress)}px)`;
  }

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const view = target.closest("[data-view]");
    if (view instanceof HTMLButtonElement) {
      activateView(view.dataset.view || defaultViewForState());
      return;
    }
    const action = target.closest("[data-action]");
    if (!(action instanceof HTMLButtonElement)) return;
    const actionName = action.dataset.action;
    if (actionName === "refresh") {
      hideQueueError();
      refs.status.textContent = "Queue refreshed";
      return;
    }
    if (actionName === "retry-queue") {
      hideQueueError();
      refs.status.textContent = "Queue retry requested";
      return;
    }
    if (actionName === "start-modeling") {
      refs.status.textContent = "Modeling start requested";
      return;
    }
    if (actionName === "resume") {
      refs.status.textContent = "Modeling resume requested";
      return;
    }
    if (actionName === "open-card") {
      refs.status.textContent = "Solver card opened";
      return;
    }
    if (actionName === "review") {
      const row = action.closest(".queue-row");
      if (!row) return;
      const item = { id: row.dataset.rowId, task: row.querySelector(".row-task")?.textContent || "Review request", reason: row.querySelector(".row-reason")?.textContent || "" };
      openDecision(row, item);
    }
  });

  document.addEventListener("keydown", (event) => {
    const target = event.target;
    if (target instanceof HTMLButtonElement && target.matches("[data-view]") && (event.key === "ArrowRight" || event.key === "ArrowLeft")) {
      const views = [...document.querySelectorAll("[data-view]")];
      const current = views.indexOf(target);
      const next = event.key === "ArrowRight" ? (current + 1) % views.length : (current - 1 + views.length) % views.length;
      event.preventDefault();
      activateView(views[next].dataset.view || defaultViewForState(), true);
      return;
    }
    if (event.key !== "Escape") return;
    const row = document.querySelector(".queue-row.is-selected");
    if (row) {
      event.preventDefault();
      closeDecision(row);
    }
  });

  refs.queue?.addEventListener("scroll", syncOverflowRail, { passive: true });
  window.addEventListener("resize", syncOverflowRail);

  render();
})();
