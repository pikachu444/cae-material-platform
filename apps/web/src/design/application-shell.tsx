import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";

export interface WorkspaceStatusUpdate {
  selection?: string;
  revision?: string;
  jobs?: string;
  warnings?: string;
  connection?: "online" | "degraded" | "offline";
}

type WorkspaceStatus = Required<Omit<WorkspaceStatusUpdate, "connection">>;

interface ApplicationShellProps {
  path: string;
  navigate: (path: string) => void;
  children: ReactNode;
}

interface Command {
  label: string;
  action?: () => void;
  active?: boolean;
  disabledReason?: string;
}

const STATUS_EVENT = "cmp:workspace-status";
const COMMAND_EVENT = "cmp:workspace-command";

export function publishWorkspaceStatus(update: WorkspaceStatusUpdate): void {
  window.dispatchEvent(new CustomEvent<WorkspaceStatusUpdate>(STATUS_EVENT, { detail: update }));
}

function workspaceFor(path: string): "materials" | "modeling" | "activity" | "administration" | "other" {
  if (path.startsWith("/modeling") || path.startsWith("/datasets") || path.startsWith("/models")) return "modeling";
  if (path.startsWith("/activity") || path.startsWith("/jobs-reviews") || path.startsWith("/governance") || path.startsWith("/exports")) return "activity";
  if (path.startsWith("/administration") || path.startsWith("/access")) return "administration";
  if (path.startsWith("/materials") || path.startsWith("/database") || path.startsWith("/catalog")) return "materials";
  return "other";
}

function defaultStatus(path: string): WorkspaceStatus {
  const workspace = workspaceFor(path);
  if (workspace === "modeling") return { selection: "Modeling session", revision: "Draft", jobs: "No active job", warnings: "0 warnings" };
  if (workspace === "activity") return { selection: "Current work queue", revision: "Current user", jobs: "No active job", warnings: "0 warnings" };
  if (workspace === "administration") return { selection: "Administration", revision: "No shell draft", jobs: "No active job", warnings: "0 validation errors" };
  if (workspace === "other") return { selection: "Workspace", revision: "Current context", jobs: "No active job", warnings: "0 warnings" };
  if (/^\/materials\/[^/]+/.test(path)) return { selection: "Material record", revision: "Current revision", jobs: "No active job", warnings: "0 warnings" };
  return { selection: "No material selected", revision: "Current records", jobs: "No active job", warnings: "0 warnings" };
}

function emitWorkspaceCommand(command: string): void {
  window.dispatchEvent(new CustomEvent(COMMAND_EVENT, { detail: { command } }));
}

function initialActiveCommand(path: string): string {
  if (workspaceFor(path) === "modeling") return "modeling:fit";
  if (workspaceFor(path) === "materials" && path === "/materials") return `materials:${new URLSearchParams(window.location.search).get("mode") ?? "search"}`;
  return "";
}

function focusFirst(selector: string): void {
  const target = document.querySelector<HTMLElement>(selector);
  target?.focus();
}

function commandsFor(path: string, navigate: (path: string) => void, activeCommand: string): { title: string; commands: Command[] } {
  const material = path.match(/^\/materials\/([^/]+)(?:\/(overview|properties|curves|cards|evidence))?$/);
  if (material) {
    return {
      title: "Material Detail",
      commands: [
        { label: "Back to results", action: () => {
          const stored = window.sessionStorage.getItem("cmp.materials.return-path") ?? "";
          navigate(stored.startsWith("/materials") && !stored.startsWith("//") ? stored : "/materials");
        } },
      ],
    };
  }

  const workspace = workspaceFor(path);
  if (workspace === "modeling") {
    return {
      title: "Modeling",
      commands: [
        { label: "Data", active: activeCommand === "modeling:data", action: () => emitWorkspaceCommand("modeling:data") },
        { label: "Process", active: activeCommand === "modeling:process", action: () => emitWorkspaceCommand("modeling:process") },
        { label: "Fit", active: activeCommand === "modeling:fit", action: () => emitWorkspaceCommand("modeling:fit") },
        { label: "Export", active: activeCommand === "modeling:export", action: () => emitWorkspaceCommand("modeling:export") },
      ],
    };
  }
  if (workspace === "activity") {
    return { title: "Activity", commands: [] };
  }
  if (workspace === "administration") {
    return { title: "Administration", commands: [] };
  }
  if (workspace === "other") {
    return { title: "Workspace", commands: [{ label: "Materials", action: () => navigate("/materials") }, { label: "Modeling", action: () => navigate("/modeling") }] };
  }
  return {
    title: "Materials",
    commands: [
      { label: "Search", active: activeCommand === "materials:search", action: () => { emitWorkspaceCommand("materials:search"); focusFirst('[aria-label="Search materials"]'); } },
      { label: "Browse Tree", active: activeCommand === "materials:browse", action: () => emitWorkspaceCommand("materials:browse") },
      { label: "Subsets", active: activeCommand === "materials:subsets", action: () => emitWorkspaceCommand("materials:subsets") },
      { label: "Compare", disabledReason: "Select at least two material rows to compare." },
      { label: "New material", action: () => navigate("/materials/new") },
    ],
  };
}

export function ApplicationShell({ path, navigate, children }: ApplicationShellProps) {
  const workspace = workspaceFor(path);
  const [activeCommand, setActiveCommand] = useState(() => initialActiveCommand(path));
  const commandModel = useMemo(() => commandsFor(path, navigate, activeCommand), [activeCommand, navigate, path]);
  const [status, setStatus] = useState<WorkspaceStatus>(() => defaultStatus(path));
  const [browserOnline, setBrowserOnline] = useState(() => navigator.onLine);
  const [serviceConnection, setServiceConnection] = useState<NonNullable<WorkspaceStatusUpdate["connection"]>>("online");
  const menuRef = useRef<HTMLElement>(null);
  const commandRef = useRef<HTMLElement>(null);
  const mainRef = useRef<HTMLElement>(null);
  const statusRef = useRef<HTMLElement>(null);

  useEffect(() => {
    setStatus(defaultStatus(path));
    setServiceConnection("online");
    setActiveCommand(initialActiveCommand(path));
  }, [path]);

  useEffect(() => {
    const update = (event: Event) => {
      const detail = (event as CustomEvent<WorkspaceStatusUpdate>).detail;
      const { connection, ...fields } = detail;
      setStatus((current) => ({ ...current, ...fields }));
      if (connection) setServiceConnection(connection);
    };
    window.addEventListener(STATUS_EVENT, update);
    return () => window.removeEventListener(STATUS_EVENT, update);
  }, []);

  useEffect(() => {
    const markOnline = () => setBrowserOnline(true);
    const markOffline = () => setBrowserOnline(false);
    window.addEventListener("online", markOnline);
    window.addEventListener("offline", markOffline);
    return () => {
      window.removeEventListener("online", markOnline);
      window.removeEventListener("offline", markOffline);
    };
  }, []);

  useEffect(() => {
    const updateActiveCommand = (event: Event) => {
      const command = (event as CustomEvent<{ command?: string }>).detail?.command;
      if (command?.startsWith("modeling:") || command?.startsWith("materials:")) setActiveCommand(command);
    };
    window.addEventListener(COMMAND_EVENT, updateActiveCommand);
    return () => window.removeEventListener(COMMAND_EVENT, updateActiveCommand);
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        const search = document.querySelector<HTMLElement>('[aria-label="Search materials"], [data-command-search]');
        (search ?? commandRef.current)?.focus();
        return;
      }
      if (event.key !== "F6") return;
      event.preventDefault();
      const workspaceRegions = [
        document.querySelector<HTMLElement>(".navigator-panel, .materials-left-pane, .modeling-workspace-rail, .administration-navigation"),
        document.querySelector<HTMLElement>(".main-panel, .materials-results, .material-tab-panel, .persistent-modeling-plot, .activity-content, .administration-content"),
        document.querySelector<HTMLElement>(".context-panel, .materials-selection, .step-option-panel"),
      ];
      const regions = [menuRef.current, commandRef.current, ...workspaceRegions, mainRef.current, statusRef.current]
        .filter((item, index, items): item is HTMLElement => Boolean(item) && items.indexOf(item) === index);
      if (!regions.length) return;
      const current = regions.findIndex((item) => item === document.activeElement || item.contains(document.activeElement));
      const direction = event.shiftKey ? -1 : 1;
      const next = regions[(current + direction + regions.length) % regions.length];
      if (!next.hasAttribute("tabindex")) next.tabIndex = -1;
      next.focus();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const navigation = [
    { label: "Materials", target: "/materials", active: workspace === "materials" },
    { label: "Modeling", target: "/modeling", active: workspace === "modeling" },
    { label: "Activity", target: "/activity", active: workspace === "activity" },
  ];
  const connection = browserOnline ? serviceConnection : "offline";
  const connectionLabel = connection === "online" ? "Online" : connection === "degraded" ? "Service unavailable" : "Offline";

  return (
    <div className="application-shell">
      <header className="application-menu-bar" data-focus-region="application" ref={menuRef} tabIndex={-1}>
        <button className="application-brand" type="button" onClick={() => navigate("/materials")} aria-label="CAE Material Platform home">
          <span className="application-mark" aria-hidden="true">CMP</span>
          <strong>CAE Material Platform</strong>
        </button>
        <nav aria-label="Primary navigation">
          {navigation.map((item) => <button key={item.target} className={item.active ? "application-nav active" : "application-nav"} type="button" aria-current={item.active ? "page" : undefined} onClick={() => navigate(item.target)}>{item.label}</button>)}
        </nav>
        <div className="application-session">
          <details className="application-user-menu"><summary>Demo user</summary><div><button type="button" onClick={() => navigate("/administration")}>Administration</button><button type="button" onClick={() => navigate("/database")}>Browse database</button></div></details>
        </div>
      </header>
      <section className="workspace-command-bar" aria-label={`${commandModel.title} commands`} data-focus-region="commands" ref={commandRef} tabIndex={-1}>
        <h1>{commandModel.title}</h1>
        <div className="workspace-command-group">
          {commandModel.commands.map((command) => <button key={command.label} className={command.active ? "workspace-command active" : "workspace-command"} type="button" disabled={Boolean(command.disabledReason)} title={command.disabledReason} aria-disabled={command.disabledReason ? "true" : undefined} onClick={command.action}>{command.label}</button>)}
        </div>
      </section>
      <main className="application-workspace" data-focus-region="workspace" ref={mainRef} tabIndex={-1}>{children}</main>
      <footer className="application-status-bar" role="status" aria-live="polite" data-focus-region="status" ref={statusRef} tabIndex={-1}>
        <span className="status-selection">{status.selection}</span>
        <span>{status.revision}</span>
        <span>{status.jobs}</span>
        <span>{status.warnings}</span>
        <span className={`status-connection ${connection}`}><i aria-hidden="true" />{connectionLabel}</span>
      </footer>
    </div>
  );
}
