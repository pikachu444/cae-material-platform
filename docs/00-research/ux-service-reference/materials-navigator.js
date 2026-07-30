(() => {
  "use strict";

  if (
    document.documentElement.dataset.materialsNavigatorDisabled === "true" ||
    document.body?.dataset.materialsNavigator !== "normal"
  ) {
    return;
  }

  const controllers = [];
  const immediate = (value) => ({ left: value, top: value, behavior: "auto" });

  const axisFor = (rail) => rail?.getAttribute("aria-orientation") === "horizontal" ? "x" : "y";

  const syncRail = (scroller, rail) => {
    if (!scroller || !rail) return false;
    const axis = axisFor(rail);
    const range = Math.max(0, (axis === "x" ? scroller.scrollWidth - scroller.clientWidth : scroller.scrollHeight - scroller.clientHeight));
    const shell = scroller.closest("[data-scroll-shell]");
    const overflowing = range > 1;
    rail.hidden = !overflowing;
    if (shell) shell.dataset[axis === "x" ? "scrollX" : "scrollY"] = String(overflowing);
    rail.setAttribute("aria-valuemin", "0");
    rail.setAttribute("aria-valuemax", String(Math.round(range)));
    if (!overflowing) {
      rail.setAttribute("aria-valuenow", "0");
      return false;
    }
    const thumb = rail.querySelector(".app-scrollbar-thumb");
    if (!thumb) return true;
    const trackLength = axis === "x" ? rail.clientWidth : rail.clientHeight;
    const viewportLength = axis === "x" ? scroller.clientWidth : scroller.clientHeight;
    const contentLength = axis === "x" ? scroller.scrollWidth : scroller.scrollHeight;
    const thumbLength = Math.max(36, Math.round((viewportLength / contentLength) * Math.max(0, trackLength - 4)));
    const available = Math.max(0, trackLength - 4 - thumbLength);
    const position = axis === "x" ? scroller.scrollLeft : scroller.scrollTop;
    const offset = Math.round((position / range) * available);
    if (axis === "x") {
      thumb.style.width = `${thumbLength}px`;
      thumb.style.height = "auto";
      thumb.style.transform = `translateX(${offset}px)`;
    } else {
      thumb.style.height = `${thumbLength}px`;
      thumb.style.width = "auto";
      thumb.style.transform = `translateY(${offset}px)`;
    }
    rail.setAttribute("aria-valuenow", String(Math.round(position)));
    return true;
  };

  const syncController = (controller) => {
    const before = `${controller.shell.dataset.scrollX || "false"}:${controller.shell.dataset.scrollY || "false"}`;
    syncRail(controller.scroller, controller.vertical);
    syncRail(controller.scroller, controller.horizontal);
    const after = `${controller.shell.dataset.scrollX || "false"}:${controller.shell.dataset.scrollY || "false"}`;
    if (before !== after && !controller.pending) {
      controller.pending = true;
      requestAnimationFrame(() => {
        controller.pending = false;
        syncController(controller);
      });
    }
  };

  const setScroll = (controller, axis, value) => {
    const maximum = Math.max(0, axis === "x" ? controller.scroller.scrollWidth - controller.scroller.clientWidth : controller.scroller.scrollHeight - controller.scroller.clientHeight);
    const next = Math.max(0, Math.min(maximum, value));
    controller.scroller.scrollTo(axis === "x" ? { ...immediate(next), top: controller.scroller.scrollTop } : { ...immediate(controller.scroller.scrollLeft), top: next });
    syncController(controller);
  };

  const bindRail = (controller, rail) => {
    const axis = axisFor(rail);
    rail.addEventListener("keydown", (event) => {
      const current = axis === "x" ? controller.scroller.scrollLeft : controller.scroller.scrollTop;
      const viewport = axis === "x" ? controller.scroller.clientWidth : controller.scroller.clientHeight;
      const maximum = Math.max(0, axis === "x" ? controller.scroller.scrollWidth - controller.scroller.clientWidth : controller.scroller.scrollHeight - controller.scroller.clientHeight);
      let next = null;
      if ((axis === "x" && event.key === "ArrowRight") || (axis === "y" && event.key === "ArrowDown")) next = current + 36;
      else if ((axis === "x" && event.key === "ArrowLeft") || (axis === "y" && event.key === "ArrowUp")) next = current - 36;
      else if (event.key === "PageDown") next = current + viewport * 0.8;
      else if (event.key === "PageUp") next = current - viewport * 0.8;
      else if (event.key === "Home") next = 0;
      else if (event.key === "End") next = maximum;
      if (next === null) return;
      event.preventDefault();
      setScroll(controller, axis, next);
    });
    rail.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      event.preventDefault();
      const thumb = rail.querySelector(".app-scrollbar-thumb");
      if (!thumb) return;
      const railBox = rail.getBoundingClientRect();
      const thumbBox = thumb.getBoundingClientRect();
      const pointer = axis === "x" ? event.clientX : event.clientY;
      const startPointer = pointer;
      const startValue = axis === "x" ? controller.scroller.scrollLeft : controller.scroller.scrollTop;
      const maximum = Math.max(0, axis === "x" ? controller.scroller.scrollWidth - controller.scroller.clientWidth : controller.scroller.scrollHeight - controller.scroller.clientHeight);
      const available = Math.max(1, (axis === "x" ? railBox.width : railBox.height) - 4 - (axis === "x" ? thumbBox.width : thumbBox.height));
      if (event.target !== thumb) {
        const offset = (pointer - (axis === "x" ? railBox.left : railBox.top)) - 2;
        const thumbLength = axis === "x" ? thumbBox.width : thumbBox.height;
        setScroll(controller, axis, ((offset - thumbLength / 2) / available) * maximum);
        return;
      }
      rail.setPointerCapture?.(event.pointerId);
      const move = (moveEvent) => {
        const nextPointer = axis === "x" ? moveEvent.clientX : moveEvent.clientY;
        setScroll(controller, axis, startValue + ((nextPointer - startPointer) / available) * maximum);
      };
      const end = (endEvent) => {
        rail.releasePointerCapture?.(endEvent.pointerId);
        rail.removeEventListener("pointermove", move);
        rail.removeEventListener("pointerup", end);
        rail.removeEventListener("pointercancel", end);
      };
      rail.addEventListener("pointermove", move);
      rail.addEventListener("pointerup", end);
      rail.addEventListener("pointercancel", end);
    });
  };

  const bindScroller = (controller) => {
    const { scroller } = controller;
    scroller.addEventListener("scroll", () => syncController(controller), { passive: true });
    scroller.addEventListener("keydown", (event) => {
      if (event.target !== scroller) return;
      if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
        const current = scroller.scrollLeft;
        const delta = event.key === "ArrowRight" ? 40 : -40;
        if (scroller.scrollWidth > scroller.clientWidth) {
          event.preventDefault();
          setScroll(controller, "x", current + delta);
        }
      } else if (event.key === "PageDown" || event.key === "PageUp") {
        const current = scroller.scrollTop;
        const delta = event.key === "PageDown" ? scroller.clientHeight * 0.8 : -scroller.clientHeight * 0.8;
        if (scroller.scrollHeight > scroller.clientHeight) {
          event.preventDefault();
          setScroll(controller, "y", current + delta);
        }
      }
    });
    scroller.addEventListener("wheel", (event) => {
      const beforeTop = scroller.scrollTop;
      const beforeLeft = scroller.scrollLeft;
      if (event.deltaY && scroller.scrollHeight > scroller.clientHeight) scroller.scrollBy({ left: scroller.scrollLeft, top: event.deltaY, behavior: "auto" });
      if (event.deltaX && scroller.scrollWidth > scroller.clientWidth) scroller.scrollBy({ left: event.deltaX, top: scroller.scrollTop, behavior: "auto" });
      if (scroller.scrollTop !== beforeTop || scroller.scrollLeft !== beforeLeft) event.preventDefault();
    }, { passive: false });
  };

  const initialize = (shell) => {
    const scroller = shell.querySelector(".scroll-viewport");
    const vertical = shell.querySelector(".app-scrollbar-y");
    const horizontal = shell.querySelector(".app-scrollbar-x");
    if (!scroller || !vertical || !horizontal) return;
    const controller = { shell, scroller, vertical, horizontal, pending: false };
    controllers.push(controller);
    bindScroller(controller);
    bindRail(controller, vertical);
    bindRail(controller, horizontal);
    if ("ResizeObserver" in window) {
      const resizeObserver = new ResizeObserver(() => syncController(controller));
      resizeObserver.observe(shell);
      resizeObserver.observe(scroller);
      controller.resizeObserver = resizeObserver;
    }
    if ("MutationObserver" in window) {
      const mutationObserver = new MutationObserver(() => syncController(controller));
      mutationObserver.observe(scroller, { childList: true, subtree: true, characterData: true });
      controller.mutationObserver = mutationObserver;
    }
    scroller.__materialsNavigatorController = controller;
    syncController(controller);
  };

  document.querySelectorAll("[data-scroll-shell]").forEach(initialize);
  window.addEventListener("resize", () => controllers.forEach(syncController));
  window.MaterialsNavigator = {
    syncAll: () => controllers.forEach(syncController),
    controllers,
  };
})();
