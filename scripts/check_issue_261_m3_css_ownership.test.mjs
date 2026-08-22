import assert from "node:assert/strict";
import test from "node:test";

import { evaluate } from "./check_issue_261_m3_css_ownership.mjs";

test("M3 administration and expanded Activity ownership passes the frozen roster gate", () => {
  const result = evaluate();
  assert.deepEqual(result.errors, []);
  assert.equal(result.report.status, "PASS");
  assert.deepEqual(result.report.roster, {
    targetRows: 506,
    targetGroups: 377,
    fullyRemovedGroups: 356,
    partiallyShrunkGroups: 21,
    administrationRows: 381,
    activityRows: 124,
  });
  assert.deepEqual(result.report.ownerFiles.administration, {
    path: "apps/web/src/features/administration/ui/administration.css",
    rows: 381,
    groups: 275,
  });
  assert.deepEqual(result.report.ownerFiles.activity, {
    path: "apps/web/src/features/activity/ui/activity.css",
    rows: 124,
    groups: 102,
  });
  assert.deepEqual(result.report.legacyPostState.bySourceFile, {
    "apps/web/src/styles.css": { rows: 1121, groups: 983 },
    "apps/web/src/design/layout.css": { rows: 985, groups: 794 },
  });
  assert.equal(result.report.legacyPostState.acceptedHandoffRows, 1268);
  assert.equal(result.report.legacyPostState.m2ResidualRows, 0);
  assert.equal(result.report.legacyPostState.holdResidualRows, 504);
  assert.equal(result.report.legacyPostState.m4ResidualRows, 314);
  assert.deepEqual(result.report.cascadeOracle, {
    targetSelectorIds: 506,
    targetPropertyCount: 1638,
    targetPropertyRows: 302,
    targetPropertyGroups: 245,
    exactSelectorRows: 152,
    exactSelectorGroups: 66,
    unknownIds: 0,
  });
});
