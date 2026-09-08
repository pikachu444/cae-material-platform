import type { CurveDefinitionContract } from "./curve-contracts";
/** Display-only scaling for the approved tensile reader. Explicit/other units stay declared. */
export function readerCurveDisplay(definition: CurveDefinitionContract | null | undefined): CurveDefinitionContract | null {
  if (!definition) return null;
  return { ...definition, channels: definition.channels.map(channel => {
    if (channel.unit_contract !== "common") return channel;
    const stress = ["mechanics.stress.engineering", "stress.engineering", "stress.hardening.selected"].includes(channel.quantity_semantics);
    const strain = ["mechanics.strain.engineering", "strain.engineering"].includes(channel.quantity_semantics);
    const factor = stress && channel.display_unit === "Pa" ? 1e-6 : strain && channel.display_unit === "1" ? 100 : null;
    return factor === null ? channel : { ...channel, display_unit: stress ? "MPa" : "%", display_scale: String(Number(channel.display_scale) * factor), display_offset: String(Number(channel.display_offset) * factor) };
  }) };
}
