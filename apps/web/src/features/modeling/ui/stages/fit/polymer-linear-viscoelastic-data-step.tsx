import { WorkbenchMessage } from "../../../../../design/semantic-ui";
import {
  POLYMER_AVAILABILITY_FIELDS,
  polymerSnapshotChannel,
  type PolymerDraftAvailability,
} from "../../../model/linear-viscoelastic-calibration-draft";
import { formatPolymerFitNumber } from "./polymer-linear-viscoelastic-format";
import type {
  PolymerFitSetupActions,
  PolymerFitSetupViewModel,
} from "./polymer-linear-viscoelastic-setup-types";
import "./polymer-linear-viscoelastic-data-step.css";

const AVAILABILITY_LABELS: Record<typeof POLYMER_AVAILABILITY_FIELDS[number], string> = {
  ramp: "Loading ramp",
  sweep: "Frequency sweep",
  preconditioning: "Preconditioning",
  linear_range: "Linear viscoelastic range",
};

interface PolymerLinearViscoelasticDataStepProps {
  view: PolymerFitSetupViewModel;
  actions: PolymerFitSetupActions;
}

export function PolymerLinearViscoelasticDataStep({
  view,
  actions,
}: PolymerLinearViscoelasticDataStepProps) {
  const {
    sourceChoice,
    processedAvailable,
    processedInputStatus,
    processedInputError,
    processedFitInput,
    sourceDisplayLabel,
    testData,
    testDataRef,
    processingOutput,
    activeDirectMode,
    snapshot,
    selectedTemperature,
    availableTemperatures,
    availability,
    partitions,
    directBlockers,
  } = view;
  const coordinateChannel = activeDirectMode === "dma"
    ? polymerSnapshotChannel(snapshot, "frequency.cyclic")
    : polymerSnapshotChannel(snapshot, "time.elapsed");
  const temperatureChannel = activeDirectMode === "dma"
    ? polymerSnapshotChannel(snapshot, "physics.temperature")
    : undefined;
  const responseChannels = activeDirectMode === "dma"
    ? [
        polymerSnapshotChannel(snapshot, "modulus.shear.storage") ?? polymerSnapshotChannel(snapshot, "modulus.storage"),
        polymerSnapshotChannel(snapshot, "modulus.shear.loss") ?? polymerSnapshotChannel(snapshot, "modulus.loss"),
      ].filter((value): value is NonNullable<typeof value> => Boolean(value))
    : [polymerSnapshotChannel(snapshot, "modulus.shear.relaxation")].filter((value): value is NonNullable<typeof value> => Boolean(value));
  const inputLabel = sourceDisplayLabel ?? testDataRef?.label ?? (testData ? "Test Data" : "Test Data not loaded");
  const modeLabel = activeDirectMode === "dma" ? "DMA frequency sweep" : activeDirectMode === "relaxation" ? "Shear relaxation" : "Unsupported curve";

  return (
    <section className="polymer-fit-work-step polymer-data-step" aria-labelledby="polymer-data-step-heading">
      <header className="polymer-work-step-heading">
        <h2 id="polymer-data-step-heading">Input and point use</h2>
      </header>
      <div className={`polymer-data-step-grid${sourceChoice === "processing-output" ? " source-processing-output" : ""}`}>
        <section className="polymer-data-source" aria-label="Fit source">
          <div className="polymer-source-tabs" role="tablist" aria-label="Polymer Fit source">
            <button
              type="button"
              role="tab"
              aria-selected={sourceChoice === "test-data"}
              className={sourceChoice === "test-data" ? "active" : undefined}
              onClick={() => actions.chooseSource("test-data")}
            >Test Data</button>
            <button
              type="button"
              role="tab"
              aria-selected={sourceChoice === "processing-output"}
              className={sourceChoice === "processing-output" ? "active" : undefined}
              disabled={!processedAvailable}
              onClick={() => actions.chooseSource("processing-output")}
            >Shifted DMA response</button>
          </div>

          {sourceChoice === "test-data" ? testData && testDataRef ? (
            <>
              <dl className="polymer-input-summary">
                <div><dt>Input</dt><dd>{inputLabel}</dd></div>
                <div><dt>Curve</dt><dd>{modeLabel}</dd></div>
                <div><dt>Points</dt><dd>{snapshot.pointCount}</dd></div>
              </dl>
              <label className="polymer-temperature-control">Temperature
                <select
                  name="selected-temperature-k"
                  value={selectedTemperature}
                  disabled={activeDirectMode === "unknown"}
                  onChange={(event) => actions.setSelectedTemperature(event.target.value)}
                >
                  <option value="">Choose temperature</option>
                  {(activeDirectMode === "relaxation" && snapshot.conditionTemperature !== null
                    ? [snapshot.conditionTemperature]
                    : availableTemperatures).map((value) => <option key={value} value={String(value)}>{value} K</option>)}
                </select>
              </label>
            </>
          ) : (
            <WorkbenchMessage kind="blocked" title="Test Data is not ready">
              Choose the relaxation or DMA Test Data in Data before calculating.
            </WorkbenchMessage>
          ) : processedFitInput && processingOutput ? (
            <dl className="polymer-input-summary polymer-processed-input-summary">
              <div><dt>Input</dt><dd>{processingOutput.label}</dd></div>
              <div><dt>Curve</dt><dd>Shifted DMA response</dd></div>
              <div><dt>Reference temperature</dt><dd>{processedFitInput.reference_temperature_k} K</dd></div>
              <div><dt>Points</dt><dd>{processedFitInput.rows.length}</dd></div>
            </dl>
          ) : processedInputStatus === "loading" ? (
            <p className="polymer-processed-input-status" role="status">Loading the saved DMA / TTS Fit input…</p>
          ) : processedInputStatus === "error" ? (
            <WorkbenchMessage kind="blocked" title="DMA / TTS Fit input is unavailable">
              {processedInputError ?? "The exact saved result could not be read."}
            </WorkbenchMessage>
          ) : (
            <WorkbenchMessage kind="blocked" title="Shifted DMA response is not ready">
              Save the shifted DMA response in Process before choosing it here.
            </WorkbenchMessage>
          )}

          {(sourceChoice === "test-data" ? Boolean(testData && testDataRef) : Boolean(processingOutput)) ? (
            <fieldset className="polymer-availability">
              <legend>Recorded test conditions</legend>
              {POLYMER_AVAILABILITY_FIELDS.map((key) => (
                <label key={key}>{AVAILABILITY_LABELS[key]}
                  <select
                    name={`availability-${key}`}
                    value={availability[key]}
                    onChange={(event) => actions.setAvailability(key, event.target.value as PolymerDraftAvailability)}
                  >
                    <option value="">Choose</option>
                    <option value="PROVIDED">Available</option>
                    <option value="NOT_PROVIDED">Not available</option>
                  </select>
                </label>
              ))}
            </fieldset>
          ) : null}

        </section>

        {sourceChoice === "test-data" ? <section className="polymer-point-use" aria-label="Measured value use">
          <div className="polymer-partition-toolbar">
            <strong>Measured values</strong>
            <button type="button" className="button secondary" onClick={actions.markAllCalibration} disabled={!snapshot.pointCount}>Use all to calculate</button>
            {activeDirectMode === "dma" ? <button type="button" className="button secondary" onClick={actions.excludeOtherTemperatures} disabled={!selectedTemperature}>Keep selected temperature</button> : null}
          </div>
          {snapshot.pointCount ? (
            <div className="polymer-partition-table-wrap">
              <table className="polymer-partition-table">
                <caption>Measured values and how each value is used</caption>
                <thead><tr><th scope="col">Point</th>{temperatureChannel ? <th scope="col">Temperature [K]</th> : null}<th scope="col">{coordinateChannel?.quantity.includes("frequency") ? "Frequency" : "Elapsed time"} [{coordinateChannel?.unit ?? "—"}]</th>{responseChannels.map((channel) => <th scope="col" key={channel.key}>{channel.quantity.includes("loss") ? "Loss modulus" : channel.quantity.includes("storage") ? "Storage modulus" : "Shear modulus"} [{channel.unit}]</th>)}<th scope="col">Use</th></tr></thead>
                <tbody>{Array.from({ length: snapshot.pointCount }, (_, ordinal) => (
                  <tr key={ordinal}>
                    <th scope="row">{ordinal + 1}</th>
                    {temperatureChannel ? <td>{formatPolymerFitNumber(temperatureChannel.values[ordinal])}</td> : null}
                    <td>{formatPolymerFitNumber(coordinateChannel?.values[ordinal])}</td>
                    {responseChannels.map((channel) => <td key={channel.key}>{formatPolymerFitNumber(channel.values[ordinal])}</td>)}
                    <td><select
                      name={`partition-${ordinal}`}
                      aria-label={`Use for measured value ${ordinal + 1}`}
                      value={partitions[ordinal] ?? ""}
                      onChange={(event) => actions.setPartition(ordinal, event.target.value as "CALIBRATION" | "HOLDOUT" | "EXCLUDED")}
                    ><option value="">Choose</option><option value="CALIBRATION">Calculate model</option><option value="HOLDOUT">Verification only</option><option value="EXCLUDED">Do not use</option></select></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          ) : null}
        </section> : processedFitInput ? <section className="polymer-point-use" aria-label="Saved DMA TTS Fit input">
          <div className="polymer-partition-toolbar">
            <strong>Shifted response points</strong>
          </div>
          <div className="polymer-partition-table-wrap">
            <table className="polymer-partition-table polymer-processed-point-table">
              <caption>Saved shifted DMA values used to calculate the model</caption>
              <thead><tr><th scope="col">Point</th><th scope="col">Reduced angular frequency [{processedFitInput.coordinate_unit}]</th><th scope="col">Storage modulus [Pa]</th><th scope="col">Loss modulus [Pa]</th><th scope="col">Use</th></tr></thead>
              <tbody>{processedFitInput.rows.map((row) => (
                <tr key={row.ordinal} className={row.partition === "EXCLUDED" ? "excluded" : undefined} title={row.exclusion_reason ?? undefined}>
                  <th scope="row">{row.ordinal + 1}</th>
                  <td>{formatPolymerFitNumber(row.coordinate)}</td>
                  <td>{formatPolymerFitNumber(row.storage_modulus_pa)}</td>
                  <td>{formatPolymerFitNumber(row.loss_modulus_pa)}</td>
                  <td>{row.partition === "CALIBRATION" ? "Calculate model" : row.partition === "HOLDOUT" ? "Verification only" : "Not used"}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </section> : null}
      </div>
      {directBlockers.length ? <div className="polymer-validation-summary" role="alert"><strong>Input data needs review</strong><ul>{directBlockers.map((blocker) => <li key={blocker}>{blocker}</li>)}</ul></div> : null}
    </section>
  );
}
