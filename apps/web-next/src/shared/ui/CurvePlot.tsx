import { quantityLabel } from "../model/engineering-labels";
import { readerCurveDisplay } from "../model/reader-curve-display";
import { useEffect, useRef, useState } from "react";
import {
  channelAxisLabel,
  curveChannelPair,
  curveSegments,
  type CurveDefinitionContract,
  type CurveSeriesPreviewContract,
} from "../model/curve-contracts";
import styles from "./ConnectedReaderPrimitives.module.css";

const FALLBACK_WIDTH = 520;
const FALLBACK_HEIGHT = 290;

export function plotScale(min: number, max: number) {
  if (min === max) {
    const padding = Math.abs(min) * 0.05 || 1;
    min -= padding;
    max += padding;
  }
  const rawStep = (max - min) / 5;
  const power = 10 ** Math.floor(Math.log10(rawStep));
  const fraction = rawStep / power;
  const step = (fraction < 1.5 ? 1 : fraction < 3 ? 2 : fraction < 7 ? 5 : 10) * power;
  const start = Math.floor(min / step);
  const end = Math.ceil(max / step);
  return {
    min: start * step,
    max: end * step,
    ticks: Array.from({ length: end - start + 1 }, (_, index) => Number(((start + index) * step).toPrecision(12))),
  };
}

function tickLabel(value: number): string {
  const magnitude = Math.abs(value);
  if ((magnitude > 0 && magnitude < 0.001) || magnitude >= 10_000) {
    return value.toExponential(2).replace("e+", "e");
  }
  return new Intl.NumberFormat("en-US", { maximumSignificantDigits: 4 }).format(value);
}

function dimensionsForWidth(width: number): { width: number; height: number; fontSize: number } {
  const actualWidth = Math.max(280, Math.round(width || FALLBACK_WIDTH));
  const bodySize = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--cmp-body-size")) || 14;
  return { width: actualWidth, height: Math.max(260, Math.min(window.innerHeight * 0.65, Math.round(actualWidth * 0.6))), fontSize: Math.max(12, bodySize * 0.9) };
}

export function CurvePlot({
  definition,
  series,
  dependentKey,
}: {
  definition: CurveDefinitionContract | null | undefined;
  series: CurveSeriesPreviewContract | null | undefined;
  dependentKey?: string;
}) {
  const frameRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: FALLBACK_WIDTH, height: FALLBACK_HEIGHT, fontSize: 12 });
  const pair = curveChannelPair(readerCurveDisplay(definition), series, dependentKey);

  useEffect(() => {
    const frame = frameRef.current;
    if (!frame) return undefined;
    const update = () => {
      const width = frame.getBoundingClientRect().width || frame.clientWidth;
      if (width) setDimensions((current) => {
        const next = dimensionsForWidth(width);
        return current.width === next.width && current.height === next.height && current.fontSize === next.fontSize ? current : next;
      });
    };
    update();
    if (typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver(update);
    observer.observe(frame);
    return () => observer.disconnect();
  }, []);

  if (!pair) {
    const dependentCount = definition?.channels.filter((channel) => channel.axis_role === "dependent").length ?? 0;
    return <div ref={frameRef} className={styles.curveFrame}><div className={styles.empty}>{dependentCount > 1 && !dependentKey ? "표시할 물리량을 선택하세요." : "축과 단위 정보를 확인할 수 없어 곡선을 표시하지 못했습니다."}</div></div>;
  }
  const points = curveSegments(pair.xValues, pair.yValues);
  const finite = points.flat();
  if (finite.length < 2) return <div ref={frameRef} className={styles.curveFrame}><div className={styles.empty}>곡선을 표시할 유효한 데이터 점이 부족합니다.</div></div>;

  const { width, height, fontSize } = dimensions;
  const left = Math.max(46, fontSize * 4.5);
  const right = Math.max(14, width * 0.04);
  const top = fontSize * 3;
  const bottom = Math.max(52, fontSize * 4);
  const plotWidth = Math.max(80, width - left - right);
  const plotHeight = Math.max(100, height - top - bottom);
  const bounds = finite.reduce((b, p) => ({
    xMin: Math.min(b.xMin, p.x), xMax: Math.max(b.xMax, p.x),
    yMin: Math.min(b.yMin, p.y), yMax: Math.max(b.yMax, p.y),
  }), { xMin: Infinity, xMax: -Infinity, yMin: Infinity, yMax: -Infinity });
  const { min: xMin, max: xMax, ticks: xTicks } = plotScale(bounds.xMin, bounds.xMax);
  const { min: yMin, max: yMax, ticks: yTicks } = plotScale(bounds.yMin, bounds.yMax);
  const xSpan = xMax - xMin || 1;
  const ySpan = yMax - yMin || 1;
  const toSvg = (point: { x: number; y: number }) => ({
    x: left + ((point.x - xMin) / xSpan) * plotWidth,
    y: top + (1 - (point.y - yMin) / ySpan) * plotHeight,
  });
  return (
    <div ref={frameRef} className={styles.curveFrame}>
      <svg className={styles.curve} width="100%" height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${channelAxisLabel(pair.independent)} 대비 ${channelAxisLabel(pair.dependent)}`}>
        <rect x={left} y={top} width={plotWidth} height={plotHeight} className={styles.curvePlotArea} />
        {xTicks.map((value) => {
          const x = left + ((value - xMin) / xSpan) * plotWidth;
          return <g key={`x-${value}`}><line x1={x} x2={x} y1={top} y2={top + plotHeight} className={styles.curveGrid} /><text x={x} y={top + plotHeight + fontSize + 8} textAnchor="middle" className={styles.curveTick} fontSize={fontSize}>{tickLabel(value)}</text></g>;
        })}
        {yTicks.map((value) => {
          const y = top + (1 - (value - yMin) / ySpan) * plotHeight;
          return <g key={`y-${value}`}><line x1={left} x2={left + plotWidth} y1={y} y2={y} className={styles.curveGrid} /><text x={left - 8} y={y + fontSize * 0.35} textAnchor="end" className={styles.curveTick} fontSize={fontSize}>{tickLabel(value)}</text></g>;
        })}
        <line x1={left} x2={left + plotWidth} y1={top + plotHeight} y2={top + plotHeight} className={styles.curveAxis} />
        <line x1={left} x2={left} y1={top} y2={top + plotHeight} className={styles.curveAxis} />
        {points.map((segment, index) => <polyline key={`segment-${index}`} points={segment.map((point) => { const svg = toSvg(point); return `${svg.x},${svg.y}`; }).join(" ")} className={styles.curveLine} />)}
        <text x={left + plotWidth / 2} y={height - 9} textAnchor="middle" className={styles.curveAxisLabel} fontSize={fontSize}>{channelAxisLabel(pair.independent)}</text>
        <text x={left} y={fontSize + 3} className={styles.curveAxisLabel} fontSize={fontSize}>{channelAxisLabel(pair.dependent)}</text>
      </svg>
      <div className={styles.curveCaption}><span>{quantityLabel(pair.dependent.quantity_semantics)}</span><span>{series?.sampled ? `전체 ${series.point_count.toLocaleString()}개 점의 미리보기` : `${pair.xValues.length.toLocaleString()}개 점`}</span>{points.length > 1 ? <span>결측 구간 {points.length - 1}개</span> : null}</div>
    </div>
  );
}
