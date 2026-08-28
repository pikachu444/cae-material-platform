import {
  EngineeringPane,
  SemanticText,
  WorkbenchMessage,
} from "../../../design/semantic-ui";
import type { ApiConfig } from "../../../shared/api/http";
import { useJsonRegistrationController } from "./json-registration-controller";
import "./json-record-registration.css";

function diagnosticLocation(diagnostic: {
  filename: string;
  json_pointer?: string;
  line?: number | null;
  column?: number | null;
  byte_offset?: number | null;
}): string {
  const locations: string[] = [];
  if (diagnostic.json_pointer) locations.push(diagnostic.json_pointer);
  if (diagnostic.line != null && diagnostic.column != null) {
    locations.push(`line ${diagnostic.line}, column ${diagnostic.column}`);
  } else if (diagnostic.line != null) {
    locations.push(`line ${diagnostic.line}`);
  }
  if (diagnostic.byte_offset != null) locations.push(`byte ${diagnostic.byte_offset}`);
  return `${diagnostic.filename} ${locations.length ? locations.join(" · ") : "/"}`;
}

function stepClass(step: 1 | 2 | 3, currentStep: 1 | 2 | 3, saved: boolean): string {
  if (step === currentStep) return "is-current";
  if (saved || step < currentStep) return "is-complete";
  return "";
}

export function JsonRecordRegistrationPanel({
  config,
  onClose,
  selectedTable,
  onTabularFiles,
  onChooseRecordType,
  onOpenRecords,
}: {
  config: ApiConfig;
  onClose: () => void;
  selectedTable?: { tableId: string; revisionId: string } | null;
  onTabularFiles?: (files: File[], table: { tableId: string; revisionId: string }) => void;
  onChooseRecordType?: () => void;
  onOpenRecords?: (input: {
    tableId: string;
    tableRevisionId: string;
  }) => void;
}) {
  const { view, commands } = useJsonRegistrationController({
    config,
    selectedTable,
    onClose,
    onTabularFiles,
    onChooseRecordType,
    onOpenRecords,
  });

  return (
    <EngineeringPane
      className={`json-registration-panel${view.error ? " has-message" : ""}`}
      label="Record import"
    >
      {view.error ? (
        <WorkbenchMessage className="record-workbench-message" kind="error" title="Import needs attention">
          {view.error}
        </WorkbenchMessage>
      ) : null}

      <div className="json-registration-workspace">
        <aside className="json-registration-region json-registration-steps" aria-label="Import steps">
          <div className="json-registration-steps-header">
            <SemanticText semanticRole="sectionHeading">Import records</SemanticText>
            <button className="ux-button tertiary" type="button" onClick={commands.cancel}>
              Close
            </button>
          </div>
          <ol className="json-registration-step-list">
            {([1, 2, 3] as const).map((step) => {
              const label = step === 1 ? "Files" : step === 2 ? "Preview" : "Save draft";
              const complete = view.saved !== null || step < view.currentStep;
              return (
                <li
                  className={`json-registration-step ${stepClass(step, view.currentStep, view.saved !== null)}`}
                  key={step}
                >
                  <span aria-hidden="true">{complete ? "✓" : step}</span>
                  <span>{label}</span>
                </li>
              );
            })}
          </ol>
        </aside>

        <section className="json-registration-region json-registration-files" aria-label="Import files">
          <div className="json-registration-section-heading">
            <SemanticText semanticRole="sectionHeading">Files</SemanticText>
            <label className="ux-button tertiary" htmlFor="json-record-files">
              Add files
            </label>
            <input
              id="json-record-files"
              aria-label="Add files"
              className="ux-input visually-hidden"
              type="file"
              accept="application/json,text/csv,.json,.csv,.tsv,.xlsx"
              multiple
              onChange={(event) => commands.addFiles(event.target.files)}
              disabled={view.uploading || view.phase === "previewing" || view.phase === "saving"}
            />
          </div>

          {view.rows.length ? (
            <div className="json-registration-file-table" role="table" aria-label="Selected source files">
              <div className="json-registration-file-heading" role="row">
                <span role="columnheader">File</span>
                <span role="columnheader">Record</span>
                <span role="columnheader">Status</span>
              </div>
              {view.rows.map((row) => (
                <button
                  className={`json-registration-file-row ${row.selected ? "is-selected" : ""}`}
                  key={`${row.file.name}-${row.file.size}-${row.file.lastModified}`}
                  type="button"
                  role="row"
                  aria-label={`${row.file.name}, ${row.record}, ${row.status}`}
                  aria-pressed={row.selected}
                  onClick={() => commands.selectFile(row.file.name)}
                >
                  <span role="cell" title={row.file.name} aria-label={row.file.name}>
                    {row.file.name}
                  </span>
                  <span role="cell" title={row.record} aria-label={row.record}>
                    {row.record}
                  </span>
                  <span role="cell">{row.status}</span>
                </button>
              ))}
            </div>
          ) : null}
          {view.batchSummary ? (
            <div className="json-registration-batch-summary" role="status">
              {view.batchSummary}
            </div>
          ) : null}

          {view.family === "tabular" && !selectedTable ? (
            <button className="ux-button tertiary" type="button" onClick={commands.chooseRecordType}>
              Choose Record type
            </button>
          ) : null}
          {view.tabularReady ? (
            <button className="ux-button tertiary" type="button" onClick={commands.continueTabular}>
              Continue
            </button>
          ) : null}
          {view.showPreviewCommand ? (
            <button
              className="ux-button tertiary"
              type="button"
              onClick={view.previewCommandLabel === "Retry" ? commands.retry : commands.preview}
              disabled={!view.canPreview || view.uploading || view.phase === "previewing" || view.phase === "saving"}
            >
              {view.phase === "previewing" ? "Previewing…" : view.previewCommandLabel}
            </button>
          ) : null}
        </section>

        <aside className="json-registration-region json-registration-preview" aria-label="Record preview">
          <SemanticText semanticRole="sectionHeading">Preview</SemanticText>
          {view.saved ? (
            <div className="json-registration-saved" role="status">
              <p>Draft records saved.</p>
              {onOpenRecords && view.preview?.format?.table ? (
                <button className="ux-button tertiary" type="button" onClick={commands.openRecords}>
                  Open records
                </button>
              ) : null}
            </div>
          ) : view.selectedResult ? (
            <>
              {view.selectedResult.valid ? (
                <>
                  {view.detectedContent ? (
                    <div className="json-registration-preview-field">
                      <SemanticText semanticRole="label">Detected content</SemanticText>
                      <SemanticText semanticRole="value">{view.detectedContent}</SemanticText>
                    </div>
                  ) : null}
                  <div className="json-registration-preview-fields">
                    {view.selectedResult.fields.map((field) => (
                      <div className="json-registration-preview-field" key={`${field.pointer}-${field.label}`}>
                        <span className="json-registration-preview-field-section">{field.section}</span>
                        <strong>{field.label}</strong>
                        <span>
                          {field.summary ?? field.value ?? "—"}
                          {field.unit ? ` ${field.unit}` : ""}
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="json-registration-diagnostics">
                  {view.selectedResult.errors.map((diagnostic, index) => (
                    <p key={`${diagnostic.code}-${index}`}>
                      <strong>{diagnostic.code}</strong>
                      <span>
                        {diagnosticLocation(diagnostic)} — Cause: {diagnostic.message} Recovery: {diagnostic.recovery}
                      </span>
                    </p>
                  ))}
                </div>
              )}
              {view.showSave ? (
                <div className="json-registration-save-row">
                  <div className="ux-field">
                    <label htmlFor="json-registration-reason">Reason for change</label>
                    <input
                      id="json-registration-reason"
                      className="ux-input"
                      value={view.reason}
                      onChange={(event) => commands.setReason(event.target.value)}
                      disabled={view.phase === "saving"}
                      required
                    />
                  </div>
                  <button
                    className="ux-button primary"
                    type="button"
                    onClick={commands.save}
                    disabled={!view.canSave}
                  >
                    Save
                  </button>
                </div>
              ) : null}
            </>
          ) : null}
        </aside>
      </div>
    </EngineeringPane>
  );
}
