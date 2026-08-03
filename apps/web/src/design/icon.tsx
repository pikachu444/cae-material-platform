import type { SVGProps } from "react";

export type EngineeringIconName =
  | "back"
  | "chevron-down"
  | "chevron-left"
  | "chevron-right"
  | "database"
  | "profile"
  | "table"
  | "folder"
  | "record"
  | "sort-ascending"
  | "sort-descending";

interface Props extends SVGProps<SVGSVGElement> {
  name: EngineeringIconName;
}

/** Small code-native icon grammar shared by the desktop shell and Materials panes. */
export function EngineeringIcon({ name, ...props }: Props) {
  const common = {
    width: 14,
    height: 14,
    viewBox: "0 0 14 14",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.35,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    focusable: "false" as const,
    "aria-hidden": true as const,
    ...props,
  };
  switch (name) {
    case "back":
      return <svg {...common}><path d="M8.8 2.5 4.3 7l4.5 4.5"/><path d="M4.7 7h6"/></svg>;
    case "chevron-down":
      return <svg {...common}><path d="m3.2 5 3.8 4 3.8-4"/></svg>;
    case "chevron-left":
      return <svg {...common}><path d="m9 3.2L5.2 7 9 10.8"/></svg>;
    case "chevron-right":
      return <svg {...common}><path d="m5 3.2 3.8 3.8L5 10.8"/></svg>;
    case "database":
      return <svg {...common}><ellipse cx="7" cy="3.2" rx="4" ry="1.7"/><path d="M3 3.2v3.8c0 .95 1.8 1.7 4 1.7s4-.75 4-1.7V3.2"/><path d="M3 7v3.8c0 .95 1.8 1.7 4 1.7s4-.75 4-1.7V7"/></svg>;
    case "profile":
      return <svg {...common}><circle cx="7" cy="4.3" r="2"/><path d="M3.3 11.3c.35-2 1.6-3 3.7-3s3.35 1 3.7 3"/></svg>;
    case "table":
      return <svg {...common}><rect x="2.3" y="2.3" width="9.4" height="9.4" rx=".7"/><path d="M2.5 5.3h9M5.3 5.5v6M8.7 5.5v6"/></svg>;
    case "folder":
      return <svg {...common}><path d="M1.8 4.1h3.4l1.1 1.2h5.9v4.9a1.5 1.5 0 0 1-1.5 1.5H3.3a1.5 1.5 0 0 1-1.5-1.5z"/><path d="M1.8 4.2V3.1h3l1 1"/></svg>;
    case "record":
      return <svg {...common}><rect x="3" y="1.8" width="8" height="10.4" rx=".8"/><path d="M5.2 4.8h3.6M5.2 7h3.6M5.2 9.2h2.3"/></svg>;
    case "sort-ascending":
      return <svg {...common}><path d="M7 11.8V2.2"/><path d="m3.4 5.8 3.6-3.6 3.6 3.6"/></svg>;
    case "sort-descending":
      return <svg {...common}><path d="M7 2.2v9.6"/><path d="m3.4 8.2 3.6 3.6 3.6-3.6"/></svg>;
  }
}
