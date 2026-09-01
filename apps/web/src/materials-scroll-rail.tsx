import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
  type Ref,
  type UIEventHandler,
} from "react";

import { SCROLL_RAIL_METRICS } from "./design/metrics";
import "./materials-scroll-rail.css";

type ScrollAxis = "x" | "y";

interface ScrollMetrics {
  clientHeight: number;
  clientWidth: number;
  scrollHeight: number;
  scrollLeft: number;
  scrollTop: number;
  scrollWidth: number;
}

interface MaterialsScrollRailProps {
  axis: ScrollAxis;
  ariaLabel: string;
  labelledBy: string;
  metrics: ScrollMetrics;
  onScrollTo: (axis: ScrollAxis, value: number) => void;
}

interface MaterialsScrollRegionProps {
  children: ReactNode;
  className: string;
  id: string;
  "aria-label": string;
  ariaBusy?: boolean;
  onScroll?: UIEventHandler<HTMLDivElement>;
  role?: string;
  shellClassName?: string;
  tabIndex?: number;
}

const EMPTY_METRICS: ScrollMetrics = {
  clientHeight: 0,
  clientWidth: 0,
  scrollHeight: 0,
  scrollLeft: 0,
  scrollTop: 0,
  scrollWidth: 0,
};

function maxScroll(metrics: ScrollMetrics, axis: ScrollAxis): number {
  return Math.max(0, axis === "x"
    ? metrics.scrollWidth - metrics.clientWidth
    : metrics.scrollHeight - metrics.clientHeight);
}

function currentScroll(metrics: ScrollMetrics, axis: ScrollAxis): number {
  return axis === "x" ? metrics.scrollLeft : metrics.scrollTop;
}

function viewportSize(metrics: ScrollMetrics, axis: ScrollAxis): number {
  return axis === "x" ? metrics.clientWidth : metrics.clientHeight;
}

function trackSize(element: HTMLDivElement, axis: ScrollAxis): number {
  const bounds = element.getBoundingClientRect();
  return axis === "x" ? bounds.width : bounds.height;
}

function MaterialsScrollRail({ ariaLabel, axis, labelledBy, metrics, onScrollTo }: MaterialsScrollRailProps) {
  const railRef = useRef<HTMLDivElement | null>(null);
  const maximum = maxScroll(metrics, axis);
  const scroll = currentScroll(metrics, axis);
  const viewport = viewportSize(metrics, axis);
  const railPixels = railRef.current ? trackSize(railRef.current, axis) : 0;
  const thumbPixels = Math.min(
    Math.max(SCROLL_RAIL_METRICS.thumbMinimum, viewport > 0 && metrics[axis === "x" ? "scrollWidth" : "scrollHeight"] > 0
      ? (viewport / metrics[axis === "x" ? "scrollWidth" : "scrollHeight"]) * railPixels
      : SCROLL_RAIL_METRICS.thumbMinimum),
    Math.max(SCROLL_RAIL_METRICS.thumbMinimum, railPixels),
  );
  const available = Math.max(0, railPixels - thumbPixels);
  const offset = maximum > 0 ? (scroll / maximum) * available : 0;
  const thumbStyle: CSSProperties = axis === "x"
    ? { width: `${thumbPixels}px`, transform: `translateX(${offset}px)` }
    : { height: `${thumbPixels}px`, transform: `translateY(${offset}px)` };

  const scrollFromRail = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || maximum <= 0) return;
    const rail = railRef.current;
    const thumb = rail?.firstElementChild;
    if (!rail || !(thumb instanceof HTMLElement)) return;
    event.preventDefault();
    const railBounds = rail.getBoundingClientRect();
    const thumbBounds = thumb.getBoundingClientRect();
    const pointer = axis === "x" ? event.clientX : event.clientY;
    const startPointer = pointer;
    const startValue = scroll;
    const startThumb = axis === "x" ? thumbBounds.width : thumbBounds.height;
    const railStart = axis === "x" ? railBounds.left : railBounds.top;
    const clickedThumb = event.target === thumb;
    const availablePixels = Math.max(1, (axis === "x" ? railBounds.width : railBounds.height) - startThumb);

    if (!clickedThumb) {
      const clickOffset = pointer - railStart - startThumb / 2;
      onScrollTo(axis, (clickOffset / availablePixels) * maximum);
      return;
    }

    rail.setPointerCapture(event.pointerId);
    const move = (moveEvent: PointerEvent) => {
      const nextPointer = axis === "x" ? moveEvent.clientX : moveEvent.clientY;
      onScrollTo(axis, startValue + ((nextPointer - startPointer) / availablePixels) * maximum);
    };
    const end = (endEvent: PointerEvent) => {
      rail.releasePointerCapture?.(endEvent.pointerId);
      rail.removeEventListener("pointermove", move);
      rail.removeEventListener("pointerup", end);
      rail.removeEventListener("pointercancel", end);
    };
    rail.addEventListener("pointermove", move);
    rail.addEventListener("pointerup", end);
    rail.addEventListener("pointercancel", end);
  }, [axis, maximum, onScrollTo, scroll]);

  const handleKeyDown = useCallback((event: React.KeyboardEvent<HTMLDivElement>) => {
    if (maximum <= 0) return;
    const page = viewport * 0.8;
    const delta = axis === "x"
      ? event.key === "ArrowRight" ? SCROLL_RAIL_METRICS.keyboardStep : event.key === "ArrowLeft" ? -SCROLL_RAIL_METRICS.keyboardStep : null
      : event.key === "ArrowDown" ? SCROLL_RAIL_METRICS.keyboardStep : event.key === "ArrowUp" ? -SCROLL_RAIL_METRICS.keyboardStep : null;
    if (event.key === "Home") onScrollTo(axis, 0);
    else if (event.key === "End") onScrollTo(axis, maximum);
    else if (event.key === "PageDown") onScrollTo(axis, scroll + page);
    else if (event.key === "PageUp") onScrollTo(axis, scroll - page);
    else if (delta !== null) onScrollTo(axis, scroll + delta);
    else return;
    event.preventDefault();
  }, [axis, maximum, onScrollTo, scroll, viewport]);

  return (
    <div
      ref={railRef}
      className={`materials-scroll-rail materials-scroll-rail-${axis === "x" ? "x" : "y"}`}
      role="scrollbar"
      aria-label={axis === "x" ? `Scroll ${ariaLabel} horizontally` : `Scroll ${ariaLabel} vertically`}
      aria-controls={labelledBy}
      aria-orientation={axis === "x" ? "horizontal" : "vertical"}
      aria-valuemin={0}
      aria-valuemax={Math.round(maximum)}
      aria-valuenow={Math.round(scroll)}
      tabIndex={0}
      onKeyDown={handleKeyDown}
      onPointerDown={scrollFromRail}
    >
      <span className="materials-scroll-thumb" style={thumbStyle} />
    </div>
  );
}

export const MaterialsScrollRegion = forwardRef<HTMLDivElement, MaterialsScrollRegionProps>(function MaterialsScrollRegion(
  { ariaBusy, children, className, id, "aria-label": ariaLabel, onScroll, role, shellClassName = "", tabIndex = 0 },
  forwardedRef: Ref<HTMLDivElement>,
) {
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const [metrics, setMetrics] = useState<ScrollMetrics>(EMPTY_METRICS);
  const [hasVerticalOverflow, setHasVerticalOverflow] = useState(false);
  const [hasHorizontalOverflow, setHasHorizontalOverflow] = useState(false);

  useImperativeHandle(forwardedRef, () => viewportRef.current as HTMLDivElement, []);

  const measure = useCallback(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const next: ScrollMetrics = {
      clientHeight: viewport.clientHeight,
      clientWidth: viewport.clientWidth,
      scrollHeight: viewport.scrollHeight,
      scrollLeft: viewport.scrollLeft,
      scrollTop: viewport.scrollTop,
      scrollWidth: viewport.scrollWidth,
    };
    setMetrics(next);
    setHasVerticalOverflow(next.scrollHeight > next.clientHeight + 1);
    setHasHorizontalOverflow(next.scrollWidth > next.clientWidth + 1);
  }, []);

  useLayoutEffect(() => {
    measure();
    const viewport = viewportRef.current;
    if (!viewport) return undefined;
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    observer?.observe(viewport);
    if (viewport.firstElementChild) observer?.observe(viewport.firstElementChild);
    window.addEventListener("resize", measure);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [measure]);

  useEffect(() => {
    measure();
  }, [children, measure]);

  const handleScroll = useCallback(() => measure(), [measure]);
  const onScrollTo = useCallback((axis: ScrollAxis, value: number) => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const maximum = maxScroll(metrics, axis);
    const next = Math.max(0, Math.min(maximum, value));
    if (axis === "x") viewport.scrollLeft = next;
    else viewport.scrollTop = next;
    measure();
  }, [measure, metrics]);
  const scrollName = ariaLabel.replace(/^Scrollable\s+/i, "");

  return (
    <div
      className={`materials-scroll-shell ${shellClassName}`.trim()}
      data-scroll-x={hasHorizontalOverflow ? "true" : "false"}
      data-scroll-y={hasVerticalOverflow ? "true" : "false"}
    >
      <div
        ref={viewportRef}
        id={id}
        className={className}
        role={role}
        aria-busy={ariaBusy}
        tabIndex={tabIndex}
        aria-label={ariaLabel}
        onScroll={(event) => {
          handleScroll();
          onScroll?.(event);
        }}
      >
        {children}
      </div>
      {hasVerticalOverflow ? <MaterialsScrollRail axis="y" ariaLabel={scrollName} labelledBy={id} metrics={metrics} onScrollTo={onScrollTo} /> : null}
      {hasHorizontalOverflow ? <MaterialsScrollRail axis="x" ariaLabel={scrollName} labelledBy={id} metrics={metrics} onScrollTo={onScrollTo} /> : null}
      {hasVerticalOverflow && hasHorizontalOverflow ? <span className="materials-scroll-corner" aria-hidden="true" /> : null}
    </div>
  );
});
