export function scoreBand(score) {
  const value = Number(score || 0);
  if (value >= 90) return { className: "tone-purple", label: "Excellent", matchLabel: "Elite Match" };
  if (value >= 80) return { className: "tone-blue", label: "Strong", matchLabel: "Strong Match" };
  if (value >= 70) return { className: "tone-green", label: "Good", matchLabel: "Good Match" };
  if (value >= 55) return { className: "tone-yellow", label: "Moderate", matchLabel: "Partial Match" };
  return { className: "tone-red", label: "Critical", matchLabel: "Weak Match" };
}

export function moduleNormalizedScore(category) {
  const score = Number(category?.score);
  const max = Number(category?.max_score);
  if (Number.isFinite(score) && Number.isFinite(max) && max > 0) {
    return (score / max) * 100;
  }

  return Number(category?.normalized_score || 0);
}

export function moduleScoreLabel(category) {
  const score = Number(category?.score);
  const max = Number(category?.max_score);
  if (Number.isFinite(score) && Number.isFinite(max) && max > 0) {
    return `${formatScore(score)}/${formatScore(max)}`;
  }

  const normalized = moduleNormalizedScore(category);
  return `${formatScore(normalized)}/100`;
}

export function clampSubScoreForDisplay(name, value, warn = console.warn) {
  const data = value && typeof value === "object" ? value : {};
  const rawScore = Number(data.score || 0);
  const max = Number(data.max || 0);
  const score = max > 0 ? Math.max(0, Math.min(rawScore, max)) : rawScore;

  if (max > 0 && rawScore > max && typeof warn === "function") {
    warn(`Sub-score "${name}" exceeded max and was clamped for display.`, {
      score: rawScore,
      max,
    });
  }

  const percent = max > 0 ? Math.max(0, Math.min(100, (score / max) * 100)) : 0;
  const scoreLabel = max ? `${formatScore(score)}/${formatScore(max)}` : formatDetail(value);
  return { data, score, max, percent, scoreLabel };
}

export function normalizeWorkspace(result) {
  const categories = normalizeCategories(result);
  const roleFit = categories.find((category) => category.key === "role_fit");
  const totalScore = Number(result.total_score ?? result.summary?.overall_score ?? 0);
  const rawTotalScore = calculateRawTotalScore(categories);
  const roleFitScore = Number(result.role_fit_score ?? (roleFit ? moduleNormalizedScore(roleFit) : 0));
  const sorted = [...categories].sort((a, b) => moduleNormalizedScore(b) - moduleNormalizedScore(a));
  const strongest = sorted.slice(0, 2).map((category) => category.name).join(" and ");
  const weakest = sorted.slice(-2).map((category) => category.name).join(" and ");
  const baseSummary = result.overall_summary || result.summary?.summary_narrative || "";
  const overviewVerdict = [
    baseSummary,
    strongest ? `Particular strength appears in ${strongest}.` : "",
    weakest ? `The main areas holding the score back are ${weakest}.` : "",
  ].filter(Boolean).join(" ");
  const roleFitSummary = roleFit
    ? [
      roleFit.score_narrative,
      roleFit.evidence?.length ? `Alignment signals include ${roleFit.evidence.slice(0, 2).join("; ")}.` : "",
      roleFit.missing_evidence?.length ? `Fit gaps include ${roleFit.missing_evidence.slice(0, 2).join("; ")}.` : "",
    ].filter(Boolean).join(" ")
    : "Role-fit evidence was not returned in the score response.";

  return {
    candidateName: result.candidate_name || result.profile?.name || "Candidate",
    targetRole: result.target_role || result.summary?.target_role || result.profile?.target_role || "Selected role",
    totalScore,
    rawTotalScore,
    roleFitScore,
    tier: result.tier || result.summary?.overall_grade || scoreBand(totalScore).label,
    roleMatchLabel: result.role_match_label || scoreBand(roleFitScore).matchLabel,
    overallSummary: baseSummary,
    categories,
    overviewVerdict,
    roleFitSummary,
  };
}

export function calculateRawTotalScore(categories) {
  const totals = categories.reduce((acc, category) => {
    const score = Number(category.score);
    const max = Number(category.max_score);
    if (Number.isFinite(score) && Number.isFinite(max) && max > 0) {
      return { score: acc.score + score, max: acc.max + max };
    }

    const subTotals = Object.values(category.sub_scores || {}).reduce((subAcc, item) => {
      if (!item || typeof item !== "object") return subAcc;
      const itemScore = Number(item.score);
      const itemMax = Number(item.max);
      if (!Number.isFinite(itemScore) || !Number.isFinite(itemMax) || itemMax <= 0) return subAcc;
      return {
        score: subAcc.score + itemScore,
        max: subAcc.max + itemMax,
      };
    }, { score: 0, max: 0 });

    if (subTotals.max > 0) {
      return { score: acc.score + subTotals.score, max: acc.max + subTotals.max };
    }

    const normalized = Number(category.normalized_score);
    if (Number.isFinite(normalized)) {
      return { score: acc.score + normalized, max: acc.max + 100 };
    }

    return acc;
  }, { score: 0, max: 0 });

  return totals.max > 0 ? (totals.score / totals.max) * 100 : 0;
}

export function normalizeCategories(result) {
  if (Array.isArray(result.categories) && result.categories.length) {
    return result.categories.map((category) => ({
      ...category,
      name: category.name || category.label,
      score: Number(category.score || 0),
      max_score: Number(category.max_score || 0),
      evidence: category.evidence || category.evidence_found || [],
      missing_evidence: category.missing_evidence || [],
      recommendations: category.recommendations || [],
      extracted_items: category.extracted_items || [],
      verdict_sentence: category.verdict_sentence || category.verdict || category.score_narrative,
      grade_label: scoreBand(moduleNormalizedScore(category)).label,
      sub_scores: category.sub_scores || {},
    }));
  }

  const categoryViews = Array.isArray(result.category_views) && result.category_views.length
    ? result.category_views
    : (result.modules || []);
  return categoryViews.map((category) => ({
    key: category.key || category.module_key,
    name: category.name || category.label || category.module_label,
    score: Number(category.score || 0),
    max_score: Number(category.max_score || 0),
    normalized_score: Number(category.normalized_score || 0),
    weight: category.weight ?? ((category.max_score || 0) / 100),
    grade_label: scoreBand(moduleNormalizedScore(category)).label,
    verdict_sentence: category.verdict_sentence || category.verdict || category.llm_reasoning || "",
    extracted_items: category.extracted_items || [{ title: "Evidence used by scoring", body: (category.evidence_found || []).join(" ") }],
    evidence: category.evidence || category.evidence_found || [],
    missing_evidence: category.missing_evidence || [],
    recommendations: category.recommendations || [],
    score_narrative: category.score_narrative || category.llm_reasoning || "",
    sub_scores: category.sub_scores || {},
  }));
}

function formatScore(value) {
  const number = Number(value || 0);
  return Number.isInteger(number) ? String(number) : number.toFixed(1).replace(/\.0$/, "");
}

function formatDetail(value) {
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "object" && value !== null) return JSON.stringify(value);
  return String(value);
}

export function buildTabs(categories) {
  return [{ key: "overview", name: "Overview" }, ...categories];
}

export function buildScoreReportTabs(categories) {
  return [...buildTabs(categories), { key: "relevant_jobs", name: "Relevant Jobs" }];
}
