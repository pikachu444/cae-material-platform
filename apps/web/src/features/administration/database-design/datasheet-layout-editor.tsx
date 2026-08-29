import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";

import type { ConfigurableAttributeResponse } from "../../catalog/contracts";
import { SemanticText } from "../../../design/semantic-ui";

const valueTypeLabels: Record<string, string> = {
  number: "Number with unit",
  integer: "Integer",
  text: "Text",
  boolean: "Boolean",
  date: "Date",
  discrete: "Choice",
  file: "File",
  curve: "Curve or table",
  record_reference: "Record reference",
};

export interface DatasheetLayoutValue {
  name: string;
  description: string;
  attributeIds: string[];
}

export function DatasheetLayoutEditor({
  mode,
  title,
  attributes,
  initialValue,
  saving,
  canEdit,
  canPreview = false,
  cancelDisabled = false,
  deleteDisabled = false,
  deleteReason,
  onSave,
  onCancel,
  onPreview,
  onDuplicate,
  onDelete,
}: {
  mode: "new" | "duplicate" | "edit";
  title: string;
  attributes: ConfigurableAttributeResponse[];
  initialValue: DatasheetLayoutValue;
  saving: boolean;
  canEdit: boolean;
  canPreview?: boolean;
  cancelDisabled?: boolean;
  deleteDisabled?: boolean;
  deleteReason?: string | null;
  onSave: (value: DatasheetLayoutValue) => void;
  onCancel?: () => void;
  onPreview?: (value: DatasheetLayoutValue) => void;
  onDuplicate?: () => void;
  onDelete?: () => void;
}) {
  const availableIds = useMemo(
    () => new Set(attributes.map((attribute) => attribute.attribute_definition_id)),
    [attributes],
  );
  const [name, setName] = useState(initialValue.name);
  const [description, setDescription] = useState(initialValue.description);
  const [attributeIds, setAttributeIds] = useState(() =>
    initialValue.attributeIds.filter((attributeId) => availableIds.has(attributeId)),
  );
  const attributeIdsRef = useRef(attributeIds);
  attributeIdsRef.current = attributeIds;
  const draggingAttributeIdRef = useRef<string | null>(null);
  const fieldScrollRef = useRef<HTMLDivElement>(null);
  const pointerPositionRef = useRef<{ x: number; y: number } | null>(null);
  const autoScrollFrameRef = useRef<number | null>(null);
  const dragCleanupRef = useRef<(() => void) | null>(null);
  const [draggingAttributeId, setDraggingAttributeId] = useState<string | null>(null);
  const [reorderStatus, setReorderStatus] = useState("");
  const selectedIds = new Set(attributeIds);
  const orderedAttributes = [
    ...attributeIds
      .map((attributeId) =>
        attributes.find(
          (attribute) => attribute.attribute_definition_id === attributeId,
        ),
      )
      .filter((attribute): attribute is ConfigurableAttributeResponse => Boolean(attribute)),
    ...attributes.filter(
      (attribute) => !selectedIds.has(attribute.attribute_definition_id),
    ),
  ];

  useEffect(() => () => {
    dragCleanupRef.current?.();
    if (autoScrollFrameRef.current !== null) {
      window.cancelAnimationFrame(autoScrollFrameRef.current);
    }
  }, []);

  function toggleAttribute(attributeId: string, included: boolean) {
    const current = attributeIdsRef.current;
    const next = included
      ? current.includes(attributeId)
        ? current
        : [...current, attributeId]
      : current.filter((currentId) => currentId !== attributeId);
    attributeIdsRef.current = next;
    setAttributeIds(next);
  }

  function moveAttribute(attributeId: string, direction: -1 | 1) {
    const current = attributeIdsRef.current;
    const from = current.indexOf(attributeId);
    const to = from + direction;
    if (from < 0 || to < 0 || to >= current.length) return;
    const next = [...current];
    [next[from], next[to]] = [next[to]!, next[from]!];
    attributeIdsRef.current = next;
    setAttributeIds(next);
    const attribute = attributes.find(
      (candidate) => candidate.attribute_definition_id === attributeId,
    );
    setReorderStatus(
      `Moved ${attribute?.current_revision.content.name ?? "field"} to position ${to + 1} of ${current.length}.`,
    );
  }

  function moveDraggedAttribute(targetAttributeId: string) {
    const draggedAttributeId = draggingAttributeIdRef.current;
    if (!draggedAttributeId || draggedAttributeId === targetAttributeId) return;
    const current = attributeIdsRef.current;
    const from = current.indexOf(draggedAttributeId);
    const to = current.indexOf(targetAttributeId);
    if (from < 0 || to < 0 || from === to) return;
    const next = [...current];
    [next[from], next[to]] = [next[to]!, next[from]!];
    attributeIdsRef.current = next;
    setAttributeIds(next);
    const attribute = attributes.find(
      (candidate) => candidate.attribute_definition_id === draggedAttributeId,
    );
    setReorderStatus(
      `Moved ${attribute?.current_revision.content.name ?? "field"} to position ${to + 1} of ${current.length}.`,
    );
  }

  function reorderAtPointer(x: number, y: number) {
    const target = document
      .elementFromPoint(x, y)
      ?.closest<HTMLElement>("[data-layout-field-id]");
    const targetAttributeId = target?.dataset.layoutFieldId;
    if (targetAttributeId) moveDraggedAttribute(targetAttributeId);
  }

  function stopAutoScroll() {
    if (autoScrollFrameRef.current !== null) {
      window.cancelAnimationFrame(autoScrollFrameRef.current);
      autoScrollFrameRef.current = null;
    }
    pointerPositionRef.current = null;
  }

  function autoScrollStep() {
    autoScrollFrameRef.current = null;
    const region = fieldScrollRef.current;
    const pointer = pointerPositionRef.current;
    if (!region || !pointer || !draggingAttributeIdRef.current) return;

    const bounds = region.getBoundingClientRect();
    const edgeSize = Math.min(48, bounds.height / 4);
    let direction = 0;
    let proximity = 0;
    if (pointer.y >= bounds.top && pointer.y < bounds.top + edgeSize) {
      direction = -1;
      proximity = (bounds.top + edgeSize - pointer.y) / edgeSize;
    } else if (pointer.y <= bounds.bottom && pointer.y > bounds.bottom - edgeSize) {
      direction = 1;
      proximity = (pointer.y - (bounds.bottom - edgeSize)) / edgeSize;
    }
    if (!direction) return;

    const maximumScrollTop = Math.max(0, region.scrollHeight - region.clientHeight);
    const previousScrollTop = region.scrollTop;
    const boundedStep = direction * Math.max(2, Math.ceil(12 * proximity));
    region.scrollTop = Math.min(
      maximumScrollTop,
      Math.max(0, previousScrollTop + boundedStep),
    );
    reorderAtPointer(pointer.x, pointer.y);

    if (region.scrollTop !== previousScrollTop) {
      autoScrollFrameRef.current = window.requestAnimationFrame(autoScrollStep);
    }
  }

  function queueAutoScroll(x: number, y: number) {
    pointerPositionRef.current = { x, y };
    if (autoScrollFrameRef.current === null) {
      autoScrollFrameRef.current = window.requestAnimationFrame(autoScrollStep);
    }
  }

  function startPointerDrag(
    event: ReactPointerEvent<HTMLButtonElement>,
    attributeId: string,
  ) {
    dragCleanupRef.current?.();
    stopAutoScroll();
    const handle = event.currentTarget;
    const pointerId = event.pointerId;
    handle.focus();
    handle.setPointerCapture?.(pointerId);
    draggingAttributeIdRef.current = attributeId;
    setDraggingAttributeId(attributeId);
    queueAutoScroll(event.clientX, event.clientY);

    const cleanup = () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", finishPointerDrag);
      window.removeEventListener("pointercancel", finishPointerDrag);
      if (dragCleanupRef.current === cleanup) dragCleanupRef.current = null;
    };
    const handlePointerMove = (pointerEvent: PointerEvent) => {
      if (pointerEvent.pointerId !== pointerId) return;
      pointerEvent.preventDefault();
      reorderAtPointer(pointerEvent.clientX, pointerEvent.clientY);
      queueAutoScroll(pointerEvent.clientX, pointerEvent.clientY);
    };
    const finishPointerDrag = (pointerEvent: PointerEvent) => {
      if (pointerEvent.pointerId !== pointerId) return;
      if (handle.hasPointerCapture?.(pointerId)) handle.releasePointerCapture(pointerId);
      cleanup();
      stopAutoScroll();
      draggingAttributeIdRef.current = null;
      setDraggingAttributeId(null);
    };
    dragCleanupRef.current = cleanup;
    window.addEventListener("pointermove", handlePointerMove, { passive: false });
    window.addEventListener("pointerup", finishPointerDrag);
    window.addEventListener("pointercancel", finishPointerDrag);
    event.preventDefault();
  }

  function currentValue(): DatasheetLayoutValue {
    return {
      name: name.trim(),
      description: description.trim(),
      attributeIds,
    };
  }

  return (
    <form
      className="property-sheet ux-form datasheet-layout-editor"
      onSubmit={(event) => {
        event.preventDefault();
        onSave({ name: name.trim(), description: description.trim(), attributeIds });
      }}
    >
      <header>
        <SemanticText semanticRole="sectionHeading" as="h3">{title}</SemanticText>
        {mode === "edit" ? (
          <details className="layout-actions-menu">
            <summary className="ux-button local-action" aria-label={`More actions for ${title}`}>More</summary>
            <div>
              <button type="button" disabled={!canEdit || saving} onClick={onDuplicate}>
                Duplicate layout
              </button>
              <button
                className="danger"
                type="button"
                title={deleteReason ?? undefined}
                disabled={deleteDisabled || saving}
                onClick={onDelete}
              >
                Delete layout
              </button>
            </div>
          </details>
        ) : (
          <button className="ux-button tertiary" type="button" disabled={cancelDisabled} onClick={onCancel}>
            Cancel
          </button>
        )}
      </header>
      <div className="ux-field-grid property-fields">
        <label className="ux-field">
          Layout name
          <input className="ux-input" value={name} onChange={(event) => setName(event.target.value)} required />
        </label>
        <label className="ux-field wide">
          Description (optional)
          <textarea
            className="ux-textarea"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </label>
      </div>
      <section className="layout-field-section">
        <SemanticText semanticRole="label" as="h3">Datasheet fields</SemanticText>
        <div
          ref={fieldScrollRef}
          className="layout-field-scroll"
          role="region"
          aria-label="Datasheet fields"
          tabIndex={0}
        >
          {orderedAttributes.map((attribute) => {
          const attributeId = attribute.attribute_definition_id;
          const included = selectedIds.has(attributeId);
          const order = attributeIds.indexOf(attributeId);
          return (
            <div
              className={`${included ? "included" : ""}${draggingAttributeId === attributeId ? " dragging" : ""}`.trim() || undefined}
              data-layout-field-id={included ? attributeId : undefined}
              key={attributeId}
            >
              <label className="ux-checkbox layout-field-choice">
                <input
                  type="checkbox"
                  checked={included}
                  onChange={(event) => toggleAttribute(attributeId, event.target.checked)}
                />
                <span>{attribute.current_revision.content.name}</span>
                <small>
                  {valueTypeLabels[attribute.current_revision.content.data_type]
                    ?? attribute.current_revision.content.data_type}
                  {attribute.current_revision.content.normalized_unit
                    ? ` · ${attribute.current_revision.content.normalized_unit}`
                    : ""}
                </small>
              </label>
              {included ? (
                <button
                  className="layout-drag-handle"
                  type="button"
                  aria-keyshortcuts="Alt+ArrowUp Alt+ArrowDown"
                  aria-label={`Reorder ${attribute.current_revision.content.name}, position ${order + 1} of ${attributeIds.length}`}
                  onKeyDown={(event) => {
                    if (!event.altKey || (event.key !== "ArrowUp" && event.key !== "ArrowDown")) return;
                    event.preventDefault();
                    moveAttribute(attributeId, event.key === "ArrowUp" ? -1 : 1);
                  }}
                  onPointerDown={(event) => startPointerDrag(event, attributeId)}
                >
                  <span className="layout-drag-glyph" aria-hidden="true" />
                </button>
              ) : null}
            </div>
          );
          })}
        </div>
      </section>
      <p className="sr-only" aria-live="polite">{reorderStatus}</p>
      <footer className="ux-action-row">
        {onPreview ? (
          <button
            className="ux-button local-action"
            type="button"
            disabled={!canPreview || !name.trim()}
            onClick={() => onPreview(currentValue())}
          >
            Preview
          </button>
        ) : null}
        <button
          className="ux-button primary"
          type="submit"
          disabled={saving || !canEdit || !name.trim()}
        >
          Save
        </button>
      </footer>
    </form>
  );
}
