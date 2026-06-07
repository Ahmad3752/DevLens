import assert from "node:assert/strict";
import test from "node:test";

import {
  calculateRawTotalScore,
  buildScoreReportTabs,
  buildTabs,
  moduleNormalizedScore,
  moduleScoreLabel,
  normalizeWorkspace,
  scoreBand,
} from "./workspaceUtils.mjs";

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

test("calculateRawTotalScore uses raw module score totals", () => {
  const score = calculateRawTotalScore([
    { key: "cv_quality", score: 1.5, max_score: 2, normalized_score: 75 },
    { key: "education_certifications", score: 2.5, max_score: 3, normalized_score: 83.33 },
    { key: "technical_skill", score: 14, max_score: 22, normalized_score: 63.64 },
  ]);

  assert.equal(Number(score.toFixed(1)), 66.7);
});

test("moduleNormalizedScore prefers module score and max score", () => {
  const score = moduleNormalizedScore({
    score: 11.2,
    max_score: 18,
    normalized_score: 62.2,
    sub_scores: {
      duration: { score: 9, max: 12 },
      relevance: { score: 2.2, max: 2.9 },
    },
  });

  assert.equal(Number(score.toFixed(1)), 62.2);
});

test("moduleScoreLabel ignores mismatched sub-score totals when official module score exists", () => {
  const category = {
    score: 6,
    max_score: 12,
    normalized_score: 50,
    sub_scores: {
      testing: { score: 0, max: 2 },
      version_control: { score: 0.5, max: 2 },
      ci_cd: { score: 1, max: 2 },
      architecture: { score: 1.5, max: 2 },
      security_performance: { score: 0.5, max: 2 },
      deployment: { score: 2, max: 2 },
    },
  };

  assert.equal(moduleNormalizedScore(category), 50);
  assert.equal(moduleScoreLabel(category), "6/12");
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
