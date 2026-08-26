import {
  Fragment,
  createElement,
  forwardRef,
  isValidElement,
  type HTMLAttributes,
  type ReactNode,
} from "react";

export type SemanticTextRole =
  | "workspaceTitle"
  | "sectionHeading"
  | "label"
  | "value"
  | "metadata"
  | "importantResult";

type SemanticTextElement = "h1" | "h2" | "h3" | "p" | "span" | "strong";

export interface SemanticTextProps
  extends Omit<HTMLAttributes<HTMLElement>, "children"> {
  semanticRole: SemanticTextRole;
  as?: SemanticTextElement;
  children: ReactNode;
}

const semanticTextElements: Record<SemanticTextRole, SemanticTextElement> = {
  workspaceTitle: "h1",
  sectionHeading: "h2",
  label: "span",
  value: "span",
  metadata: "span",
  importantResult: "strong",
};

const semanticTextClasses: Record<SemanticTextRole, string> = {
  workspaceTitle: "ux-text-workspace-title",
  sectionHeading: "ux-text-section-heading",
  label: "ux-text-label",
  value: "ux-text-value",
  metadata: "ux-text-metadata",
  importantResult: "ux-text-important-result",
};

function classes(...values: Array<string | undefined>): string {
  return values.filter(Boolean).join(" ");
}

function requireVisibleLabel(label: string, owner: string): string {
  const visibleLabel = label.trim();
  if (!visibleLabel) throw new Error(`${owner} requires a visible label.`);
  return visibleLabel;
}

function hasRenderableContent(content: ReactNode): boolean {
  if (content === undefined || content === null || typeof content === "boolean") {
    return false;
  }
  if (typeof content === "string") return content.trim().length > 0;
  if (Array.isArray(content)) return content.some(hasRenderableContent);
  if (isValidElement(content) && content.type === Fragment) {
    return hasRenderableContent(
      (content.props as { children?: ReactNode }).children,
    );
  }
  return true;
}

export function SemanticText({
  semanticRole,
  as,
  className,
  children,
  ...attributes
}: SemanticTextProps) {
  return createElement(
    as ?? semanticTextElements[semanticRole],
    {
      ...attributes,
      className: classes(
        "ux-semantic-text",
        semanticTextClasses[semanticRole],
        className,
      ),
      "data-semantic-text": semanticRole,
    },
    children,
  );
}

export type SemanticStatusKind = "success" | "warning" | "danger";

export interface SemanticStatusProps
  extends Omit<HTMLAttributes<HTMLSpanElement>, "children"> {
  status: SemanticStatusKind;
  label: string;
  detail?: ReactNode;
}

export function SemanticStatus({
  status,
  label,
  detail,
  className,
  ...attributes
}: SemanticStatusProps) {
  if (!(["success", "warning", "danger"] as const).includes(status)) {
    throw new Error(`SemanticStatus does not support status "${status}".`);
  }
  const visibleLabel = requireVisibleLabel(label, "SemanticStatus");
  return (
    <span
      {...attributes}
      className={classes("ux-semantic-status", className)}
      data-status={status}
      role="status"
      aria-atomic="true"
    >
      <span>{visibleLabel}</span>
      {hasRenderableContent(detail) ? (
        <span className="ux-semantic-status-detail">{detail}</span>
      ) : null}
    </span>
  );
}

export type WorkbenchMessageKind =
  | "loading"
  | "empty"
  | "blocked"
  | "error"
  | "recovery"
  | "engineeringCondition";

export interface WorkbenchMessageAction {
  label: string;
  onClick: () => void;
}

interface WorkbenchMessageBaseProps
  extends Omit<HTMLAttributes<HTMLDivElement>, "children" | "title"> {
  title: string;
  children: ReactNode;
}

type WorkbenchRecoveryMessageProps = WorkbenchMessageBaseProps & {
  kind: "recovery";
  action: WorkbenchMessageAction;
};

type WorkbenchInformationalMessageProps = WorkbenchMessageBaseProps & {
  kind: Exclude<WorkbenchMessageKind, "recovery">;
  action?: WorkbenchMessageAction;
};

export type WorkbenchMessageProps =
  | WorkbenchRecoveryMessageProps
  | WorkbenchInformationalMessageProps;

const messageSemantics: Record<
  WorkbenchMessageKind,
  { role: "status" | "alert" | "note"; live: "polite" | "assertive" | "off" }
> = {
  loading: { role: "status", live: "polite" },
  empty: { role: "status", live: "polite" },
  blocked: { role: "alert", live: "assertive" },
  error: { role: "alert", live: "assertive" },
  recovery: { role: "status", live: "polite" },
  engineeringCondition: { role: "note", live: "off" },
};

export function WorkbenchMessage({
  kind,
  title,
  children,
  action,
  className,
  ...attributes
}: WorkbenchMessageProps) {
  const semantics = messageSemantics[kind];
  const visibleTitle = requireVisibleLabel(title, "WorkbenchMessage");
  if (kind === "recovery" && !action) {
    throw new Error("WorkbenchMessage recovery requires an action.");
  }
  if (action) requireVisibleLabel(action.label, "WorkbenchMessage action");

  return (
    <div
      {...attributes}
      className={classes("ux-workbench-message", className)}
      data-message-kind={kind}
      role={semantics.role}
      aria-live={semantics.live}
      aria-atomic="true"
    >
      <span className="ux-workbench-message-title">{visibleTitle}</span>
      <div className="ux-workbench-message-body">{children}</div>
      {action ? (
        <button
          className="ux-button ux-workbench-message-action"
          type="button"
          onClick={action.onClick}
        >
          {action.label}
        </button>
      ) : null}
    </div>
  );
}

export interface EngineeringPaneProps
  extends Omit<HTMLAttributes<HTMLElement>, "aria-label"> {
  label: string;
}

export const EngineeringPane = forwardRef<HTMLElement, EngineeringPaneProps>(
  function EngineeringPane(
    { label, className, children, ...attributes },
    ref,
  ) {
    return (
      <section
        {...attributes}
        ref={ref}
        className={classes("ux-engineering-pane", className)}
        aria-label={requireVisibleLabel(label, "EngineeringPane")}
      >
        {children}
      </section>
    );
  },
);

export interface EngineeringSectionProps
  extends Omit<HTMLAttributes<HTMLElement>, "aria-label"> {
  label: string;
}

export function EngineeringSection({
  label,
  className,
  children,
  ...attributes
}: EngineeringSectionProps) {
  return (
    <section
      {...attributes}
      className={classes("ux-engineering-section", className)}
      aria-label={requireVisibleLabel(label, "EngineeringSection")}
    >
      <div className="ux-engineering-section-content">{children}</div>
    </section>
  );
}

interface EngineeringPlotRegionBaseProps
  extends Omit<HTMLAttributes<HTMLElement>, "aria-label"> {
  label: string;
  plot: ReactNode;
}

type EngineeringPlotOnlyProps = EngineeringPlotRegionBaseProps & {
  companion?: never;
  companionLabel?: never;
};

type EngineeringPlotWithCompanionProps = EngineeringPlotRegionBaseProps & {
  companion: ReactNode;
  companionLabel: string;
};

export type EngineeringPlotRegionProps =
  | EngineeringPlotOnlyProps
  | EngineeringPlotWithCompanionProps;

export function EngineeringPlotRegion({
  label,
  plot,
  companion,
  companionLabel,
  className,
  ...attributes
}: EngineeringPlotRegionProps) {
  const visibleLabel = requireVisibleLabel(label, "EngineeringPlotRegion");
  if (!hasRenderableContent(plot)) {
    throw new Error("EngineeringPlotRegion requires plot content.");
  }
  const hasCompanion = hasRenderableContent(companion);
  const visibleCompanionLabel = hasCompanion
    ? requireVisibleLabel(companionLabel ?? "", "EngineeringPlotRegion companion")
    : undefined;

  return (
    <section
      {...attributes}
      className={classes("ux-engineering-plot-region", className)}
      data-has-companion={hasCompanion ? "true" : "false"}
      aria-label={visibleLabel}
    >
      <div
        className="ux-engineering-plot-frame"
        data-plot-frame
        role="group"
        aria-label={`${visibleLabel} plot`}
      >
        {plot}
      </div>
      {hasCompanion ? (
        <aside
          className="ux-engineering-plot-companion"
          data-plot-companion
          aria-label={visibleCompanionLabel}
        >
          {companion}
        </aside>
      ) : null}
    </section>
  );
}
