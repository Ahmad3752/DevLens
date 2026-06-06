import assert from "node:assert/strict";
import test from "node:test";

import { buildScoreReportTabs, buildTabs, normalizeWorkspace, scoreBand } from "./workspaceUtils.mjs";

test("scoreBand uses the exact requested thresholds", () => {
  assert.equal(scoreBand(54).className, "tone-red");
  assert.equal(scoreBand(55).className, "tone-yellow");
  assert.equal(scoreBand(69).className, "tone-yellow");
  assert.equal(scoreBand(70).className, "tone-green");
  assert.equal(scoreBand(79).className, "tone-green");
  assert.equal(scoreBand(80).className, "tone-blue");
  assert.equal(scoreBand(89).className, "tone-blue");
  assert.equal(scoreBand(90).className, "tone-purple");
});

test("normalizeWorkspace finds role fit dynamically by key", () => {
  const workspace = normalizeWorkspace({
    candidate_name: "Asif Khan",
    target_role: "AI/ML Engineer",
    total_score: 74,
    tier: "Junior Developer",
    overall_summary: "Strong portfolio.",
    categories: [
      { key: "project_work", name: "Projects", normalized_score: 81, evidence: [], missing_evidence: [], recommendations: [] },
      {
        key: "role_fit",
        name: "Role Fit",
        normalized_score: 82,
        evidence: ["AI/ML overlap"],
        missing_evidence: ["Production scale"],
        recommendations: ["Add deployment metrics"],
        score_narrative: "Good AI/ML alignment.",
      },
    ],
  });

  assert.equal(workspace.roleFitScore, 82);
  assert.equal(workspace.roleMatchLabel, "Strong Match");
  assert.match(workspace.roleFitSummary, /AI\/ML overlap/);
});

test("buildTabs derives tabs from category array with overview first", () => {
  const categories = [
    { key: "technical_skill", name: "Technical Skills" },
    { key: "project_work", name: "Projects" },
  ];
  const tabs = buildTabs(categories);

  assert.deepEqual(tabs.map((tab) => tab.key), ["overview", "technical_skill", "project_work"]);
});

test("buildScoreReportTabs adds Relevant Jobs after score sections", () => {
  const tabs = buildScoreReportTabs([{ key: "role_fit", name: "Role Fit" }]);

  assert.deepEqual(tabs.map((tab) => tab.key), ["overview", "role_fit", "relevant_jobs"]);
});
