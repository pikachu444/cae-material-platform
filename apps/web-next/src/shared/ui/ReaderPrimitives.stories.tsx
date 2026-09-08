import type { Meta, StoryObj } from "@storybook/react-vite";
import { Button } from "./Button";
import { ConditionSummary, UnitValue } from "./EngineeringValue";
import { CurvePreview } from "./CurvePreview";
import { RenameDialog } from "./RenameDialog";
import { StatusTag } from "./StatusTag";
import { makeSelectedCurve } from "../../features/test-data/model/fixtures";

const curve = makeSelectedCurve();
const meta = { title: "Reader/Primitives", parameters: { layout: "padded" } } satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const Controls: Story = { render: () => <div style={{ display: "grid", gap: 16, maxWidth: 620 }}><div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><Button variant="primary">Primary action</Button><Button>Secondary action</Button><Button variant="quiet">Quiet action</Button><Button variant="danger">Blocked action</Button></div><StatusTag tone="success">exact</StatusTag><UnitValue value="210" unit="GPa" /><ConditionSummary condition={{ temperature: "23 °C", rate: "1 mm/min", environment: "Dry air" }} /><RenameDialog currentTitle="Example title" currentDescription="Prototype metadata" onApply={async () => undefined} /></div> };
export const Curve: Story = { render: () => <div style={{ maxWidth: 720 }}><CurvePreview definition={curve.definition} preview={curve.preview} /></div> };
