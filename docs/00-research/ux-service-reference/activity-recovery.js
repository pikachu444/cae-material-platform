(() => {
  "use strict";

  const params = new URLSearchParams(window.location.search);
  const requestedState = params.get("state");
  const state = requestedState || "not-configured";
  const SUPPORTED_STATES = new Set(["not-configured", "recovery-empty", "recovery-loading", "recovery-action-error"]);
  const effectiveState = SUPPORTED_STATES.has(state) ? state : "not-configured";
  const NORMAL_PENDING_COUNT = 40;

  document.body.dataset.role = "user";
  document.body.dataset.state = effectiveState;

  const localSession = {
    id: "modeling-session-local",
    task: "Resume Modeling session",
    reason: "DP780 Dual-Phase Steel · selected model needs review",
    state: "Saved in this browser",
    time: "Today · 09:18",
    action: "resume",
    local: true,
  };

  const requestTemplates = [
    { task: "Material review", reason: "Confirm material details" },
    { task: "Test Data review", reason: "Confirm the Test Data units and test condition" },
    { task: "Selected model review", reason: "Confirm the selected model" },
    { task: "Solver card review", reason: "Confirm the solver card" },
  ];

  const reasonDetails = [
    "for the first specimen set",
    "for the repeat curve set",
    "before the next modeling session",
    "against the submitted source file",
  ];

  const refs = {
    queue: document.querySelector("[data-region='queue-scroll']"),
    region: document.querySelector("[data-region='queue-region']"),
    status: document.querySelector("[data-queue-status]"),
    refresh: document.querySelector("[data-action='refresh']"),
    main: document.querySelector("#activity-main"),
    announcement: document.querySelector("[data-recovery-announcement]"),
    thumb: document.querySelector(".queue-scroll-thumb"),
  };

  const interaction = { retryReady: false };

  function createElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function setText(selector, value) {
    const element = document.querySelector(selector);
    if (element) element.textContent = value;
  }

  function countLabel(count) {
    return `${count} ${count === 1 ? "item" : "items"}`;
  }

  function pendingRequests() {
    return Array.from({ length: NORMAL_PENDING_COUNT }, (_, index) => {
      const template = requestTemplates[index % requestTemplates.length];
      const day = index < 3 ? "Today" : `${27 - Math.floor((index - 3) / 3)} Jul`;
      const hour = String(8 + (index % 10)).padStart(2, "0");
      const minute = String((index * 7) % 60).padStart(2, "0");
      return {
        id: `review-request-${String(index + 1).padStart(2, "0")}`,
        task: template.task,
        reason: `${template.reason} ${reasonDetails[Math.floor(index / requestTemplates.length) % reasonDetails.length]}`,
        state: "Needs a decision",
        time: `${day} · ${hour}:${minute}`,
        action: "state",
        server: true,
      };
    });
  }

  function rowsFor(section) {
    if (section !== "in-progress") return [];
    if (effectiveState === "recovery-empty") return pendingRequests();
    return [localSession, ...pendingRequests()];
  }

  function makeActionButton(label, action, item, quiet = false) {
    const button = createElement("button", `queue-button${quiet ? " quiet" : " primary"}`, label);
    button.type = "button";
    button.dataset.action = action;
    if (item) button.dataset.rowId = item.id;
    button.setAttribute("aria-label", `${label}: ${item?.task || "Modeling"}`);
    return button;
  }

  function makePassiveAction() {
    const passive = createElement("span", "row-state", "—");
    passive.dataset.passiveAction = "true";
    passive.setAttribute("role", "img");
    passive.setAttribute("aria-label", "No available action");
    return passive;
  }

  function renderRow(item, section) {
    const row = createElement("tr", "queue-row");
    row.dataset.rowId = item.id;
    row.dataset.section = section;
    row.dataset.actionKind = item.action;
    row.dataset.source = item.local ? "browser-local" : "server";

    const task = createElement("td", "row-main");
    task.append(createElement("strong", "row-task", item.task));
    const reason = createElement("td", "row-reason", item.reason);
    const status = createElement("td", "row-status");
    status.append(createElement("strong", "row-state-label", item.state));
    const updated = createElement("td", "row-time");
    updated.append(createElement("time", "", item.time));
    const action = createElement("td", "row-action");
    if (item.action === "resume") {
      action.append(makeActionButton("Resume Modeling", "resume", item));
    } else {
      action.append(makePassiveAction());
    }
    row.append(task, reason, status, updated, action);
    return row;
  }

  function renderSection(section) {
    const list = document.querySelector(`[data-list="${section}"]`);
    const table = document.querySelector(`[data-table="${section}"]`);
    const empty = document.querySelector(`[data-empty="${section}"]`);
    const loading = document.querySelector(`[data-loading="${section}"]`);
    if (!list || !table || !empty || !loading) return;
    list.replaceChildren();
    const rows = rowsFor(section);
    rows.forEach((item) => list.append(renderRow(item, section)));
    table.hidden = rows.length === 0;
    empty.hidden = rows.length !== 0;
    loading.classList.remove("is-visible");
    loading.setAttribute("aria-busy", "false");
    const count = document.querySelector(`[data-section-count="${section}"]`);
    if (count) count.textContent = countLabel(rows.length);
    if (effectiveState === "recovery-empty" && section === "in-progress") {
      empty.hidden = false;
    }
  }

  function setStatus(text) {
    if (refs.status) refs.status.textContent = text;
  }

  function announce(text) {
    if (refs.announcement) refs.announcement.textContent = text;
  }

  function updateBoundary() {
    setText("[data-recovery-status]", "Not available in Activity");
    setText("[data-recovery-consequence]", "Resume the saved Modeling session to inspect the current step.");
  }

  function updateStateChrome() {
    updateBoundary();
    if (effectiveState === "recovery-loading") {
      if (refs.refresh) {
        refs.refresh.textContent = "Refreshing…";
        refs.refresh.disabled = true;
        refs.refresh.setAttribute("aria-busy", "true");
      }
      setStatus("Refreshing available Activity work…");
      announce("Available Activity work is being refreshed.");
    } else if (refs.refresh) {
      refs.refresh.textContent = "Refresh";
      refs.refresh.disabled = false;
      refs.refresh.removeAttribute("aria-busy");
    }
    if (effectiveState === "recovery-empty") {
      const command = document.querySelector("[data-recovery-command]");
      if (command) {
        command.hidden = false;
        command.replaceChildren(makeActionButton("Open Modeling", "open-modeling", null, true));
      }
      setStatus("No saved Modeling session");
      announce("No saved Modeling session is present. Open Modeling to continue.");
    }
  }

  function syncOverflowRail() {
    const queue = refs.queue;
    const thumb = refs.thumb;
    const region = refs.region;
    if (!queue || !thumb || !region) return;
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
    setStatus(`${selected.textContent} view`);
    syncOverflowRail();
    if (focus) selected.focus();
  }

  function removeFeedback(row) {
    const next = row.nextElementSibling;
    if (next?.classList.contains("row-feedback") && next.dataset.rowId === row.dataset.rowId) next.remove();
  }

  function appendActionError(row) {
    removeFeedback(row);
    const feedback = createElement("tr", "row-feedback");
    feedback.dataset.rowId = row.dataset.rowId;
    const cell = createElement("td", "", "");
    cell.colSpan = 5;
    const inline = createElement("div", "row-inline-error");
    inline.setAttribute("role", "alert");
    inline.append(
      createElement("span", "", "Modeling session could not be opened."),
      makeActionButton("Try again", "try-again", localSession, true),
    );
    cell.append(inline);
    feedback.append(cell);
    row.after(feedback);
  }

  function openModeling(row, force = false) {
    row.classList.add("is-selected");
    if (row.dataset.rowId === localSession.id && refs.queue) {
      refs.queue.scrollTop = 0;
      window.setTimeout(() => {
        if (refs.queue) refs.queue.scrollTop = 0;
        syncOverflowRail();
      }, 0);
    }
    else row.scrollIntoView({ block: "nearest" });
    if (effectiveState === "recovery-action-error" && !force && !interaction.retryReady) {
      interaction.retryReady = true;
      appendActionError(row);
      setStatus("Modeling session not opened");
      announce("Modeling session could not be opened. Try again.");
      syncOverflowRail();
      return;
    }
    removeFeedback(row);
    refs.main.dataset.destination = "modeling-session-local";
    refs.main.dataset.openedDestination = "Modeling · DP780 Dual-Phase Steel · selected model needs review";
    setStatus("Modeling session opened");
    announce("Modeling session opened for DP780 Dual-Phase Steel · selected model needs review.");
    syncOverflowRail();
  }

  function openModelingBlank() {
    refs.main.dataset.destination = "modeling-new";
    setStatus("Modeling opened");
    announce("Modeling opened.");
  }

  function setContractMetadata() {
    if (!refs.region) return;
    refs.region.dataset.serverRequestCount = String(NORMAL_PENDING_COUNT);
    refs.region.dataset.pendingCount = String(NORMAL_PENDING_COUNT);
    refs.region.dataset.localHistoryCount = effectiveState === "recovery-empty" ? "0" : "1";
    refs.region.dataset.roleDefaultView = "in-progress";
  }

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const view = target.closest("[data-view]");
    if (view instanceof HTMLButtonElement) {
      activateView(view.dataset.view || "in-progress");
      return;
    }
    const action = target.closest("[data-action]");
    if (!(action instanceof HTMLButtonElement)) return;
    const actionName = action.dataset.action;
    if (actionName === "refresh") {
      setStatus("Activity work refreshed");
      announce("Available Activity work refreshed.");
      return;
    }
    if (actionName === "resume" || actionName === "try-again") {
      const row = document.querySelector(`[data-row-id="${action.dataset.rowId || localSession.id}"]`);
      if (row) openModeling(row, actionName === "try-again");
      return;
    }
    if (actionName === "open-modeling") openModelingBlank();
  });

  document.addEventListener("keydown", (event) => {
    const target = event.target;
    if (target instanceof HTMLButtonElement && target.matches("[data-view]")) {
      const tabs = [...document.querySelectorAll("[data-view]")];
      const current = tabs.indexOf(target);
      let next = current;
      if (event.key === "ArrowRight") next = (current + 1) % tabs.length;
      if (event.key === "ArrowLeft") next = (current - 1 + tabs.length) % tabs.length;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = tabs.length - 1;
      if (next !== current) {
        event.preventDefault();
        activateView(tabs[next].dataset.view || "in-progress", true);
      }
    }
  });

  refs.queue?.addEventListener("scroll", syncOverflowRail, { passive: true });
  refs.queue?.addEventListener("keydown", (event) => {
    if (!refs.queue) return;
    if (event.key === "End") {
      event.preventDefault();
      refs.queue.scrollTop = refs.queue.scrollHeight - refs.queue.clientHeight;
      syncOverflowRail();
    } else if (event.key === "Home") {
      event.preventDefault();
      refs.queue.scrollTop = 0;
      syncOverflowRail();
    }
  });
  window.addEventListener("resize", syncOverflowRail);

  updateStateChrome();
  ["needs-attention", "in-progress", "recent-outcomes"].forEach(renderSection);
  setContractMetadata();
  activateView("in-progress");
  if (effectiveState === "recovery-action-error") {
    const row = document.querySelector(".queue-row[data-row-id='modeling-session-local']");
    if (row) {
      row.classList.add("is-selected");
      appendActionError(row);
      interaction.retryReady = true;
      setStatus("Modeling session not opened");
      announce("Modeling session could not be opened. Try again.");
    }
  }
  setText("[data-status-role]", "User context");
  setText("[data-status-scroll]", "Local queue scroll");
  syncOverflowRail();
})();
