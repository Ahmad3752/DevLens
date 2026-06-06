import React, { useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertTriangle,
  ArrowLeft,
  BarChart3,
  BookOpen,
  BrainCircuit,
  Briefcase,
  CheckCircle2,
  ChevronDown,
  Circle,
  Code2,
  ExternalLink,
  FileText,
  FileSearch,
  Gauge,
  Layers3,
  Lightbulb,
  Loader2,
  MapPin,
  Radar,
  RefreshCw,
  Sparkles,
  Star,
  Tags,
  TrendingUp,
  Trophy,
  UploadCloud,
  Wrench,
} from "lucide-react";
import "./styles.css";
import {
  buildScoreReportTabs,
  buildTabs,
  normalizeWorkspace,
  scoreBand,
} from "./workspaceUtils.mjs";

const API_URL = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");

const FALLBACK_ROLES = [
  ["backend", "Backend Developer"],
  ["frontend", "Frontend Developer"],
  ["full_stack", "Full Stack Developer"],
  ["mobile", "Mobile Developer"],
  ["ai_ml", "AI/ML Engineer"],
  ["devops", "DevOps Engineer"],
  ["data_engineer", "Data Engineer"],
  ["data_scientist", "Data Scientist"],
  ["qa_automation", "QA Automation Engineer"],
];

const DEFAULT_STAGES = [
  { key: "cv_upload", label: "CV Upload", status: "idle", message: "Waiting for CV upload." },
  { key: "extraction", label: "Extraction Agent", status: "idle", message: "Waiting for extraction agent." },
  { key: "scoring", label: "Scoring Agent", status: "idle", message: "Waiting to score all categories." },
  { key: "summarizer", label: "Summarizer Agent", status: "idle", message: "Waiting to prepare the final summary." },
  { key: "results_ready", label: "Results Ready", status: "idle", message: "Waiting for final results." },
];

const JOB_RESULT_LIMIT = 50;

function App() {
  const [roles, setRoles] = useState(FALLBACK_ROLES);
  const [file, setFile] = useState(null);
  const [role, setRole] = useState("ai_ml");
  const [result, setResult] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [loadedCandidateId, setLoadedCandidateId] = useState("");
  const [activeTab, setActiveTab] = useState("overview");
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [error, setError] = useState("");
  const [scoreFetchState, setScoreFetchState] = useState("idle");
  const [scoreFetchError, setScoreFetchError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const stages = jobStatus?.stages?.length ? jobStatus.stages : DEFAULT_STAGES;
  const isProcessing = Boolean(jobStatus?.candidate_id && ["queued", "processing"].includes(jobStatus.status));

  useEffect(() => {
    fetch(`${API_URL}/roles`)
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((data) => {
        if (Array.isArray(data.roles) && data.roles.length) {
          setRoles(data.roles.map((item) => [item.key, item.label]));
        }
      })
      .catch(() => setRoles(FALLBACK_ROLES));
  }, []);

  useEffect(() => {
    const candidateId = jobStatus?.candidate_id;
    if (!candidateId || !["queued", "processing"].includes(jobStatus.status)) return;

    let cancelled = false;
    async function pollStatus() {
      try {
        const response = await fetch(`${API_URL}/candidates/${candidateId}/status`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Status request failed");
        if (cancelled) return;
        setJobStatus(data);
        if (data.status === "error") {
          setError(data.error_message || "CV scoring failed.");
        }
      } catch (err) {
        if (!cancelled) setError(err.message || "Could not read pipeline status.");
      }
    }

    pollStatus();
    const timer = window.setInterval(pollStatus, 1000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [jobStatus?.candidate_id, jobStatus?.status]);

  const loadScores = useCallback(async (candidateId, options = {}) => {
    const force = Boolean(options.force);
    if (!candidateId) return;
    if (!force && loadedCandidateId === candidateId && result) return;

    setScoreFetchState("loading");
    setScoreFetchError("");
    try {
      const data = await fetchScoresWithRetry(candidateId);
      setResult(data);
      setLoadedCandidateId(candidateId);
      setActiveTab("overview");
      setDetailsOpen(false);
      setScoreFetchState("success");
    } catch (err) {
      setLoadedCandidateId("");
      setScoreFetchState("error");
      setScoreFetchError(err.message || "Scores could not be loaded.");
    }
  }, [loadedCandidateId, result]);

  useEffect(() => {
    const candidateId = jobStatus?.candidate_id;
    if (jobStatus?.status !== "complete" || !candidateId) return;
    if (scoreFetchState === "loading") return;
    if (scoreFetchState === "error") return;
    if (loadedCandidateId === candidateId && result) return;
    loadScores(candidateId);
  }, [jobStatus?.status, jobStatus?.candidate_id, loadedCandidateId, result, scoreFetchState, loadScores]);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setResult(null);
    setLoadedCandidateId("");
    setActiveTab("overview");
    setDetailsOpen(false);
    setScoreFetchState("idle");
    setScoreFetchError("");
    if (!file) {
      setError("Please choose a PDF CV first.");
      return;
    }

    setSubmitting(true);
    setJobStatus({
      status: "processing",
      stages: DEFAULT_STAGES.map((stage) => (
        stage.key === "cv_upload"
          ? { ...stage, status: "in_progress", message: "Receiving CV upload." }
          : stage
      )),
    });

    const form = new FormData();
    form.append("file", file);
    form.append("target_role", role);
    try {
      const response = await fetch(`${API_URL}/candidates/upload/start`, { method: "POST", body: form });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Upload failed");
      setJobStatus(data);
    } catch (err) {
      setJobStatus({
        status: "error",
        stages: DEFAULT_STAGES.map((stage) => (
          stage.key === "cv_upload"
            ? { ...stage, status: "error", message: err.message || "CV upload failed." }
            : stage
        )),
      });
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  if (result && detailsOpen) {
    return (
      <ScoringDashboard
        result={result}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onBack={() => {
          setActiveTab("overview");
          setDetailsOpen(false);
        }}
      />
    );
  }

  return (
    <main className="app-frame">
      <section className="shell">
        <header className="topbar">
          <div className="brand"><BrainCircuit size={25} /> DevLens</div>
          <div className="status-pill"><Sparkles size={16} /> Agent CV scoring</div>
        </header>

        <PipelineTracker stages={stages} status={jobStatus?.status || "idle"} />

        <div className="workspace-grid">
          <UploadPanel
            file={file}
            setFile={setFile}
            role={role}
            setRole={setRole}
            roles={roles}
            onSubmit={submit}
            submitting={submitting}
            isProcessing={isProcessing}
            error={error}
            jobStatus={jobStatus}
          />

          <section className="dashboard-surface">
            <ResultsSurface
              result={result}
              jobStatus={jobStatus}
              stages={stages}
              scoreFetchState={scoreFetchState}
              scoreFetchError={scoreFetchError}
              onRetryScores={() => loadScores(jobStatus?.candidate_id, { force: true })}
              detailsOpen={detailsOpen}
              setDetailsOpen={setDetailsOpen}
              activeTab={activeTab}
              setActiveTab={setActiveTab}
            />
          </section>
        </div>
      </section>
    </main>
  );
}

function UploadPanel({ file, setFile, role, setRole, roles, onSubmit, submitting, isProcessing, error, jobStatus }) {
  return (
    <aside className="upload-panel">
      <p className="eyebrow">Developer CV intelligence</p>
      <h1>Role-aware scoring with live agent context.</h1>
      <p className="lede">
        Upload a PDF CV and DevLens will extract evidence, score every category, and explain the result in candidate-readable language.
      </p>

      <form onSubmit={onSubmit} className="form">
        <label className="field-label" htmlFor="target-role">Target role</label>
        <select id="target-role" value={role} onChange={(event) => setRole(event.target.value)} disabled={submitting || isProcessing}>
          {roles.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>

        <label className={`dropzone ${file ? "ready" : ""}`}>
          <UploadCloud size={32} />
          <span>{file ? file.name : "Choose PDF CV"}</span>
          <small>{file ? "Ready for scoring" : "PDF only"}</small>
          <input type="file" accept="application/pdf" onChange={(event) => setFile(event.target.files?.[0] || null)} disabled={submitting || isProcessing} />
        </label>

        <button disabled={submitting || isProcessing} className="primary">
          {submitting || isProcessing ? <Loader2 className="spin" size={18} /> : <Radar size={18} />}
          {submitting ? "Uploading..." : isProcessing ? "Agents running..." : "Score CV"}
        </button>
      </form>

      {jobStatus?.candidate_id && (
        <div className="job-card">
          <span>Candidate ID</span>
          <strong>{jobStatus.candidate_id}</strong>
        </div>
      )}

      {error && <div className="error"><AlertTriangle size={18} /> {error}</div>}
    </aside>
  );
}

function PipelineTracker({ stages, status }) {
  return (
    <section className={`pipeline-shell ${status || "idle"}`}>
      <div className="pipeline-track">
        {stages.map((stage, index) => (
          <React.Fragment key={stage.key}>
            <div className={`pipeline-node ${stage.status}`}>
              <div className="node-icon">{stageIcon(stage.status)}</div>
              <div className="node-copy">
                <strong>{stage.label}</strong>
                <span>{stage.message}</span>
              </div>
            </div>
            {index < stages.length - 1 && <div className={`pipeline-connector ${stage.status}`} />}
          </React.Fragment>
        ))}
      </div>
    </section>
  );
}

function ResultsSurface({
  result,
  jobStatus,
  stages,
  scoreFetchState,
  scoreFetchError,
  onRetryScores,
  detailsOpen,
  setDetailsOpen,
  activeTab,
  setActiveTab,
}) {
  if (result) {
    return (
      <ResultsWorkspace
        result={result}
        detailsOpen={detailsOpen}
        setDetailsOpen={setDetailsOpen}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
      />
    );
  }

  if (jobStatus?.status === "complete") {
    return (
      <ScoresLoadingPanel
        state={scoreFetchState}
        error={scoreFetchError}
        onRetry={onRetryScores}
      />
    );
  }

  return <WaitingPanel stages={stages} status={jobStatus?.status} />;
}

function WaitingPanel({ stages, status }) {
  const active = stages.find((stage) => stage.status === "in_progress");
  const completed = stages.filter((stage) => stage.status === "completed").length;
  const total = stages.length;

  if (status === "error") {
    const failed = stages.find((stage) => stage.status === "error");
    return (
      <div className="empty-state error-state">
        <AlertTriangle size={44} />
        <h2>{failed?.label || "Pipeline stopped"}</h2>
        <p>{failed?.message || "The scoring pipeline reported an error."}</p>
      </div>
    );
  }

  return (
    <div className="empty-state">
      {active ? <Loader2 className="spin" size={46} /> : <FileSearch size={48} />}
      <h2>{active?.key === "scoring" ? "Scoring is running." : active ? active.label : "Your scoring workspace is ready."}</h2>
      <p>{active ? active.message : "Upload a CV to begin."}</p>
      <div className="progress-meter" aria-label="Pipeline progress">
        <span style={{ width: `${(completed / total) * 100}%` }} />
      </div>
    </div>
  );
}

function ScoresLoadingPanel({ state, error, onRetry }) {
  if (state === "error") {
    return (
      <div className="empty-state error-state">
        <AlertTriangle size={44} />
        <h2>Scores are not visible yet.</h2>
        <p>{error || "The pipeline completed, but the score response could not be loaded after three attempts."}</p>
        <button className="primary retry-button" type="button" onClick={onRetry}>
          <Radar size={18} /> Retry loading scores
        </button>
      </div>
    );
  }

  return (
    <div className="empty-state">
      <Loader2 className="spin" size={46} />
      <h2>Preparing the results card.</h2>
      <p>The pipeline is complete. DevLens is loading the detailed score response.</p>
      <div className="progress-meter" aria-label="Loading scores">
        <span style={{ width: "100%" }} />
      </div>
    </div>
  );
}

function ResultsWorkspace({ result, detailsOpen, setDetailsOpen, activeTab, setActiveTab }) {
  const workspace = useMemo(() => normalizeWorkspace(result), [result]);
  const tabs = useMemo(() => buildTabs(workspace.categories), [workspace.categories]);
  const active = activeTab === "overview"
    ? { key: "overview", name: "Overview" }
    : workspace.categories.find((category) => category.key === activeTab) || tabs[0];

  function openDetails(nextTab = "overview") {
    setDetailsOpen(true);
    setActiveTab(nextTab);
  }

  return (
    <div className="results-wrap">
      <PostPipelineHero workspace={workspace} onOpenDetails={() => openDetails("overview")} detailsOpen={detailsOpen} />

      {detailsOpen && (
        <section className="details-workspace">
          <TabControls tabs={tabs} activeTab={active.key} setActiveTab={setActiveTab} />
          <div className="tab-stage" key={active.key}>
            {active.key === "overview" ? (
              <OverviewTab workspace={workspace} onSelectCategory={(key) => openDetails(key)} />
            ) : (
              <CategoryPanel category={active} />
            )}
          </div>
        </section>
      )}
    </div>
  );
}

function ScoringDashboard({ result, activeTab, setActiveTab, onBack }) {
  const workspace = useMemo(() => normalizeWorkspace(result), [result]);
  const tabs = useMemo(() => buildScoreReportTabs(workspace.categories), [workspace.categories]);
  const selectedTab = tabs.some((tab) => tab.key === activeTab) ? activeTab : "overview";
  const active = selectedTab === "overview"
    ? { key: "overview", name: "Overview" }
    : selectedTab === "relevant_jobs"
      ? { key: "relevant_jobs", name: "Relevant Jobs" }
    : workspace.categories.find((category) => category.key === selectedTab) || tabs[0];

  return (
    <main className="score-dashboard">
      <ScoreTopbar
        workspace={workspace}
        activeTab={selectedTab}
        setActiveTab={setActiveTab}
        onBack={onBack}
      />
      <section className="score-main">
        <ScoreTabBar tabs={tabs} activeTab={selectedTab} setActiveTab={setActiveTab} />
        <ScoreReportTopSummary workspace={workspace} />
        <div className="score-content-stage" key={active.key}>
          {selectedTab === "relevant_jobs" ? (
            <RelevantJobsDashboard result={result} workspace={workspace} />
          ) : active.key === "overview" ? (
            <ScoreOverviewDashboard workspace={workspace} onSelectCategory={setActiveTab} />
          ) : (
            <ScoreCategoryDashboard category={active} />
          )}
        </div>
      </section>
    </main>
  );
}

function ScoreTopbar({ workspace, activeTab, setActiveTab, onBack }) {
  const candidateName = reportCandidateName(workspace);
  const initials = candidateInitials(candidateName);
  return (
    <header className="score-topbar">
      <div className="score-brand">
        <BrainCircuit size={25} />
        <strong>DevLens</strong>
      </div>
      <div className="score-candidate-chip">
        <div>
          <strong>{candidateName}</strong>
          <span>{formatRole(workspace.targetRole)}</span>
        </div>
        <b>{initials}</b>
      </div>
      <div className="score-topbar-actions">
        <button
          className={`score-button score-button-jobs ${activeTab === "relevant_jobs" ? "active" : ""}`}
          type="button"
          onClick={() => setActiveTab("relevant_jobs")}
        >
          <Briefcase size={18} /> Relevant Jobs
        </button>
        <button className="score-button score-button-primary" type="button" onClick={onBack}>
          <ArrowLeft size={18} /> Back to Upload
        </button>
      </div>
    </header>
  );
}

function ScoreTabBar({ tabs, activeTab, setActiveTab }) {
  return (
    <nav className="score-tabbar" aria-label="Score report sections">
      {tabs.filter((tab) => tab.key !== "relevant_jobs").map((tab) => (
        <button
          key={tab.key}
          className={`score-tab ${tab.key === activeTab ? "active" : ""}`}
          type="button"
          onClick={() => setActiveTab(tab.key)}
        >
          {categoryIcon(tab.key, 17)}
          <span>{tab.name}</span>
        </button>
      ))}
    </nav>
  );
}

function ScoreReportTopSummary({ workspace }) {
  return (
    <section className="score-report-top">
      <PersistentTotalScore workspace={workspace} />
      <article className="score-report-context">
        <div className="score-ready-chip"><CheckCircle2 size={18} /> Results ready</div>
        <div className="score-report-copy">
          <h1>CV Score Report</h1>
          <p>{reportCandidateName(workspace)} - {formatRole(workspace.targetRole)}</p>
        </div>
        <div className="score-report-fit">
          <span>Role fit</span>
          <strong>{formatScore(workspace.roleFitScore)} / 100</strong>
        </div>
      </article>
    </section>
  );
}

function ScoreMetricCard({ label, score, caption, icon, accent = "primary" }) {
  const band = accent === "secondary" ? { className: "tone-green", label: "Strong" } : scoreBand(score);
  return (
    <article className={`score-summary-card score-metric-card ${band.className}`}>
      <div className="score-card-label">
        <span>{label}</span>
        {icon}
      </div>
      <div className="score-metric-value">
        <strong>{formatScore(score)}</strong>
        <span>/100</span>
      </div>
      <ScoreBandBadge score={score} label={caption || band.label} />
    </article>
  );
}

function PersistentTotalScore({ workspace }) {
  const totalBand = scoreBand(workspace.totalScore);
  return (
    <section className="score-persistent-total" aria-label="Total score">
      <ScoreMetricCard
        label="Total Score"
        score={workspace.totalScore}
        caption={workspace.tier || totalBand.label}
        icon={<TrendingUp size={22} />}
      />
    </section>
  );
}

function ScoreOverviewDashboard({ workspace, onSelectCategory }) {
  return (
    <section className="score-overview">
      <section className="score-summary-grid score-overview-summary">
        <ScoreMetricCard
          label="Role Fit"
          score={workspace.roleFitScore}
          caption={roleFitLabel(workspace)}
          icon={<Radar size={22} />}
          accent="secondary"
        />
        <ScoreTierCard workspace={workspace} />
      </section>

      <section className="score-category-summary">
        <div className="score-panel-title"><Layers3 size={19} /> Quick Module Breakdown</div>
        <div className="score-module-pill-grid">
          {workspace.categories.map((category) => (
            <button
              className={`score-module-pill ${scoreBand(category.normalized_score).className}`}
              key={category.key}
              type="button"
              onClick={() => onSelectCategory(category.key)}
            >
              {categoryIcon(category.key, 17)}
              <span>{category.name}</span>
              <strong>{moduleScoreLabel(category)}</strong>
            </button>
          ))}
        </div>
      </section>
    </section>
  );
}

function ScoreTierCard({ workspace }) {
  const roles = recommendedRoles(workspace);
  return (
    <article className="score-summary-card score-tier-card">
      <div className="score-tier-status">
        <CheckCircle2 size={18} />
        <strong>{roleFitLabel(workspace)} - Ready for internship roles</strong>
      </div>
      <p className="score-tier-fit">Role fit score: <b>{formatScore(workspace.roleFitScore)} / 100</b></p>
      <p>
        This candidate fits the {workspace.tier || "Intern / Trainee"} level with high confidence.
        Calibrated by module evidence, career stage, and role alignment.
      </p>
      <div className="score-best-fit">
        <span><Star size={15} /> Best fit - Recommended for</span>
        <div>
          {roles.map((role) => <b key={role}>{role}</b>)}
        </div>
      </div>
    </article>
  );
}

function ScoreInsightPanel({ title, icon, tone, items, empty }) {
  return (
    <section className={`score-panel score-insight-panel ${tone}`}>
      <div className="score-panel-title">{icon}{title}</div>
      <div className="score-insight-list">
        {items.length ? items.map((item, index) => (
          <article className="score-insight-item" key={`${item.title}-${index}`}>
            {tone === "good" ? <Star size={16} /> : <AlertTriangle size={16} />}
            <div>
              <h3>{item.title}</h3>
              <p>{item.body}</p>
            </div>
          </article>
        )) : <p className="muted">{empty}</p>}
      </div>
    </section>
  );
}

function DashboardScoreBars({ categories }) {
  if (!categories.length) return <p className="muted">No category scores were returned.</p>;
  return (
    <div className="dashboard-score-bars">
      {categories.map((category, index) => (
        <div className={`dashboard-score-row ${scoreBand(category.normalized_score).className}`} key={category.key} style={{ "--delay": `${index * 55}ms` }}>
          <div>
            <span>{category.name}</span>
            <b>{formatScore(category.normalized_score)}%</b>
          </div>
          <i><strong style={{ "--score": `${clampScore(category.normalized_score)}%` }} /></i>
        </div>
      ))}
    </div>
  );
}

function ScoreCategoryDashboard({ category }) {
  const band = scoreBand(category.normalized_score);
  return (
    <section className="score-category-report">
      <header className={`score-category-report-hero ${band.className}`}>
        <ScoreRing score={category.normalized_score} />
        <div>
          <p className="eyebrow">Module Analysis</p>
          <div className="score-category-titleline">
            <h2>{category.name}</h2>
            <div className="score-module-score-badge">
              <span>Module score</span>
              <strong>{moduleScoreLabel(category)}</strong>
            </div>
          </div>
          <div className="score-category-badges">
            <ScoreBandBadge score={category.normalized_score} label={category.grade_label || band.label} />
          </div>
          <p>{category.verdict_sentence || category.score_narrative || "Module evidence was scored from the extracted CV content."}</p>
        </div>
      </header>

      <div className="score-category-grid">
        <div className="score-stack">
          <section className="score-panel">
            <div className="score-panel-title"><Gauge size={19} /> Sub-Scores</div>
            <SubScores subScores={category.sub_scores || {}} />
          </section>

          <section className={`score-panel score-master-narrative ${band.className}`}>
            <div className="score-panel-title"><Trophy size={19} /> Score Narrative</div>
            <p>{category.score_narrative || category.verdict_sentence || "No score narrative was returned for this section."}</p>
          </section>
        </div>

        <div className="score-stack score-wide-stack">
          <section className="score-panel">
            <div className="score-panel-title"><FileText size={19} /> Extracted CV Evidence</div>
            <EvidenceCards items={evidenceItemsForCategory(category)} />
          </section>

          <div className="score-two-column">
            <section className="score-panel score-disclosure-panel good">
              <div className="score-panel-title"><CheckCircle2 size={19} /> Strengths Found</div>
              <DisclosureList items={category.evidence || []} empty="No strengths were returned for this category." />
            </section>
            <section className="score-panel score-disclosure-panel bad">
              <div className="score-panel-title"><AlertTriangle size={19} /> Missing Evidence</div>
              <DisclosureList items={category.missing_evidence || []} empty="No missing evidence was returned for this category." />
            </section>
          </div>

          <section className="score-panel score-disclosure-panel warn">
            <div className="score-panel-title"><Lightbulb size={19} /> Recommendations</div>
            <DisclosureList items={category.recommendations || []} empty="No recommendations were returned for this category." />
          </section>
        </div>
      </div>
    </section>
  );
}

function ScoreRing({ score }) {
  const value = clampScore(score);
  const ringClass = value <= 40 ? "ring-low" : value <= 69 ? "ring-mid" : "ring-high";
  return (
    <div className={`score-ring-meter ${ringClass}`} style={{ "--score-angle": `${value * 3.6}deg` }}>
      <strong>{formatScore(score)}</strong>
      <span>/100</span>
    </div>
  );
}

function ScoreBandBadge({ score, label }) {
  return <span className={`score-band-badge ${scoreBand(score).className}`}>{label}</span>;
}

function DisclosureList({ items, empty }) {
  if (!items.length) return <p className="muted">{empty}</p>;
  return (
    <div className="score-disclosure-list">
      {items.slice(0, 6).map((item, index) => {
        const text = formatDetail(item);
        return (
          <details className="score-disclosure" key={`${text}-${index}`} open={index === 0}>
            <summary>
              <span>{truncateText(text, 86)}</span>
              <ChevronDown size={17} />
            </summary>
            <p>{text}</p>
          </details>
        );
      })}
    </div>
  );
}

function RelevantJobsDashboard({ result, workspace }) {
  const [jobsState, setJobsState] = useState({ status: "idle", jobs: [], error: "", cacheStatus: "", metadata: null });
  const [refreshKey, setRefreshKey] = useState(0);
  const candidateId = result?.candidate_id;
  const scrapingUnavailable = jobsState.metadata?.availability === "scraping_unavailable";

  useEffect(() => {
    if (!candidateId) return;
    let cancelled = false;

    async function loadJobs() {
      setJobsState((current) => ({ ...current, status: "loading", error: "" }));
      try {
        const response = await fetch(`${API_URL}/candidates/${candidateId}/jobs?limit=${JOB_RESULT_LIMIT}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Could not load relevant jobs.");
        if (cancelled) return;
        setJobsState({
          status: "success",
          jobs: Array.isArray(data.jobs) ? data.jobs : [],
          error: "",
          cacheStatus: data.cache_status || "",
          metadata: data.metadata || null,
        });
      } catch (err) {
        if (!cancelled) {
          setJobsState({ status: "error", jobs: [], error: err.message || "Could not load relevant jobs.", cacheStatus: "", metadata: null });
        }
      }
    }

    loadJobs();
    return () => {
      cancelled = true;
    };
  }, [candidateId, refreshKey]);

  return (
    <section className="jobs-dashboard">
      <header className="jobs-hero">
        <div>
          <p className="eyebrow">Relevant Jobs</p>
          <h2>{formatRole(workspace.targetRole)} roles</h2>
          <p>
            {scrapingUnavailable
              ? "Scraping not available yet"
              : jobsState.status === "success"
                ? `${jobsState.jobs.length} active role${jobsState.jobs.length === 1 ? "" : "s"} found`
                : "Active roles from Supabase"}
          </p>
        </div>
        <div className="jobs-hero-actions">
          {jobsState.cacheStatus && !scrapingUnavailable && <span className="cache-chip">Cache {jobsState.cacheStatus}</span>}
          {!scrapingUnavailable && (
            <button className="score-button score-button-muted" type="button" onClick={() => setRefreshKey((value) => value + 1)}>
              <RefreshCw size={18} /> Refresh
            </button>
          )}
        </div>
      </header>

      <JobsResultState state={jobsState} onRetry={() => setRefreshKey((value) => value + 1)} />
    </section>
  );
}

function JobsResultState({ state, onRetry }) {
  if (state.status === "loading" || state.status === "idle") {
    return (
      <section className="score-panel jobs-state-panel">
        <Loader2 className="spin" size={34} />
        <h3>Loading relevant jobs</h3>
        <p>Checking active Supabase jobs for the selected CV role.</p>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section className="score-panel jobs-state-panel error-state">
        <AlertTriangle size={34} />
        <h3>Jobs are not available right now</h3>
        <p>{state.error}</p>
        <button className="score-button score-button-primary" type="button" onClick={onRetry}>
          <RefreshCw size={18} /> Retry
        </button>
      </section>
    );
  }

  if (state.metadata?.availability === "scraping_unavailable") {
    const supportedRoles = Array.isArray(state.metadata.supported_roles) ? state.metadata.supported_roles : [];
    return (
      <section className="score-panel jobs-state-panel jobs-unavailable-panel">
        <Briefcase size={34} />
        <h3>Data Scientist jobs are not being scraped yet</h3>
        <p>{state.metadata.message || "Try another scraped role. Data Scientist job scraping will be added soon."}</p>
        {!!supportedRoles.length && (
          <div className="jobs-role-suggestions" aria-label="Scraped job roles">
            {supportedRoles.map((role) => (
              <span key={role.key || role.label}>{role.label || formatRole(role.key)}</span>
            ))}
          </div>
        )}
      </section>
    );
  }

  if (!state.jobs.length) {
    return (
      <section className="score-panel jobs-state-panel">
        <Briefcase size={34} />
        <h3>No matching active jobs</h3>
        <p>No active roles were returned for this CV role.</p>
      </section>
    );
  }

  return (
    <div className="jobs-list">
      {state.jobs.map((job) => <JobCard key={job.id || job.url} job={job} />)}
    </div>
  );
}

function JobCard({ job }) {
  return (
    <article className="job-result-card">
      <div className="job-result-main">
        <div className="job-title-row">
          <div>
            <h3>{job.title}</h3>
            <p>{job.company}</p>
          </div>
        </div>

        <div className="job-meta-row">
          <span><MapPin size={15} /> {formatJobLocation(job)}</span>
          <span><Briefcase size={15} /> {formatJobType(job)}</span>
          <span><Tags size={15} /> {job.platform || "source"}</span>
        </div>

        <div className="job-foot-row">
          <span>{formatSalary(job)}</span>
          <span>{formatJobDate(job.posted_at || job.scraped_at)}</span>
        </div>
      </div>

      <aside className="job-result-side">
        {job.url && (
          <a className="score-button score-button-primary job-apply-link" href={job.url} target="_blank" rel="noreferrer">
            <ExternalLink size={17} /> Open
          </a>
        )}
      </aside>
    </article>
  );
}

function PostPipelineHero({ workspace, onOpenDetails, detailsOpen }) {
  return (
    <section className="post-result-hero animate-in">
      <div className="hero-identity">
        <div>
          <p className="eyebrow">Results ready</p>
          <h2>{workspace.candidateName || "Candidate"}</h2>
        </div>
        <span>{workspace.targetRole || "Selected role"}</span>
      </div>

      <div className="hero-divider" />

      <div className="hero-score-grid">
        <ScoreStat
          label="Total Score"
          score={workspace.totalScore}
          caption={workspace.tier}
        />
        <ScoreStat
          label="Role Fit"
          score={workspace.roleFitScore}
          caption={workspace.roleMatchLabel}
        />
      </div>

      {workspace.overallSummary && <p className="hero-summary">{workspace.overallSummary}</p>}

      {!detailsOpen && (
        <button className="primary view-scores" type="button" onClick={onOpenDetails}>
          <BarChart3 size={18} /> View Detailed Scores <ChevronDown size={18} />
        </button>
      )}
    </section>
  );
}

function ScoreStat({ label, score, caption }) {
  const band = scoreBand(score);
  return (
    <div className={`score-stat ${band.className}`}>
      <span>{label}</span>
      <strong>{formatScore(score)} <small>/ 100</small></strong>
      <p><i />{caption || band.label}</p>
    </div>
  );
}

function TabControls({ tabs, activeTab, setActiveTab }) {
  return (
    <>
      <nav className="tabs desktop-tabs" aria-label="Score categories">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            className={`tab ${tab.key === activeTab ? "active" : ""} ${tab.normalized_score !== undefined ? scoreBand(tab.normalized_score).className : "overview-tab"}`}
            onClick={() => setActiveTab(tab.key)}
            type="button"
          >
            <span>{tab.name}</span>
            {tab.normalized_score !== undefined && <b>{formatScore(tab.normalized_score)}</b>}
          </button>
        ))}
      </nav>
      <label className="mobile-tab-select">
        <span>Score section</span>
        <select value={activeTab} onChange={(event) => setActiveTab(event.target.value)}>
          {tabs.map((tab) => (
            <option key={tab.key} value={tab.key}>
              {tab.normalized_score !== undefined ? `${tab.name} ${formatScore(tab.normalized_score)}` : tab.name}
            </option>
          ))}
        </select>
      </label>
    </>
  );
}

function OverviewTab({ workspace, onSelectCategory }) {
  return (
    <section className="overview-grid">
      <div className="zone overview-chart">
        <div className="zone-title"><BarChart3 size={18} /> Score Breakdown</div>
        <ScoreBars categories={workspace.categories} />
      </div>
      <div className="zone overview-copy">
        <div className="zone-title"><Trophy size={18} /> Tier Verdict</div>
        <p className="narrative">{workspace.overviewVerdict}</p>
      </div>
      <div className="zone overview-copy">
        <div className="zone-title"><Radar size={18} /> Role Fit Summary</div>
        <p className="narrative">{workspace.roleFitSummary}</p>
      </div>
      <div className="zone overview-chips">
        <div className="zone-title"><Layers3 size={18} /> Category Scores</div>
        <div className="overview-chip-grid">
          {workspace.categories.map((category) => (
            <button
              type="button"
              className={`overview-chip ${scoreBand(category.normalized_score).className}`}
              key={category.key}
              onClick={() => onSelectCategory(category.key)}
            >
              <span>{category.name}</span>
              <strong>{formatScore(category.normalized_score)}</strong>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

function ScoreBars({ categories }) {
  return (
    <div className="chart-bars">
      {categories.map((category, index) => (
        <div className={`chart-row ${scoreBand(category.normalized_score).className}`} key={category.key} style={{ "--delay": `${index * 50}ms` }}>
          <span>{category.name}</span>
          <div><i style={{ "--score": `${clampScore(category.normalized_score)}%` }} /></div>
          <b>{formatScore(category.normalized_score)}</b>
        </div>
      ))}
    </div>
  );
}

function CategoryPanel({ category }) {
  return (
    <section className="category-panel">
      <CategoryScoreHeader category={category} />
      <div className="zone-grid">
        <section className="zone wide">
          <div className="zone-title"><Layers3 size={18} /> Extracted Evidence</div>
          <EvidenceCards items={category.extracted_items || []} />
        </section>
        <section className="zone narrative-zone">
          <div className="zone-title"><Trophy size={18} /> Score Narrative</div>
          <NarrativeCards category={category} />
        </section>
        <section className="zone">
          <div className="zone-title"><Code2 size={18} /> Score Breakdown</div>
          <SubScores subScores={category.sub_scores || {}} />
        </section>
      </div>
    </section>
  );
}

function CategoryScoreHeader({ category }) {
  const band = scoreBand(category.normalized_score);
  return (
    <header className={`category-score-header ${band.className}`}>
      <div className="category-title-row">
        <div>
          <p className="eyebrow">Category analysis</p>
          <h2>{category.name}</h2>
        </div>
        <strong>{formatScore(category.normalized_score)} <small>/ 100</small></strong>
      </div>
      <div className="category-progress">
        <i style={{ "--score": `${clampScore(category.normalized_score)}%` }} />
      </div>
      <div className="category-verdict-line">
        <span><i />{category.grade_label || band.label}</span>
        <p>{category.verdict_sentence || category.score_narrative}</p>
      </div>
    </header>
  );
}

function EvidenceCards({ items }) {
  if (!items.length) return <p className="muted">No extracted CV content was returned for this category.</p>;
  return (
    <div className="content-card-grid">
      {items.map((item, index) => (
        <details className="content-card stagger-card" key={`${item.title}-${index}`} open={index === 0} style={{ "--delay": `${index * 50}ms` }}>
          <summary>
            <div>
              <strong>{item.title}</strong>
              {item.subtitle && <span>{item.subtitle}</span>}
            </div>
            <ChevronDown size={18} />
          </summary>
          {item.body && <p>{item.body}</p>}
          {!!item.badges?.length && (
            <div className="badge-row">{item.badges.map((badge) => <span key={badge}>{badge}</span>)}</div>
          )}
          {!!item.meta?.length && <ul className="meta-list">{item.meta.map((meta) => <li key={meta}>{meta}</li>)}</ul>}
          <DetailTable details={item.details || item} />
        </details>
      ))}
    </div>
  );
}

function NarrativeCards({ category }) {
  const cards = [
    { title: "Strengths in this area include...", items: category.evidence || [], tone: "good" },
    { title: "Gaps identified include...", items: category.missing_evidence || [], tone: "bad" },
    { title: "To improve this score, consider...", items: category.recommendations || [], tone: "warn" },
  ];
  return (
    <div className="narrative-card-grid">
      {category.score_narrative && <p className="narrative lead-narrative">{category.score_narrative}</p>}
      {cards.map((card, index) => (
        <section className={`narrative-card ${card.tone} stagger-card`} key={card.title} style={{ "--delay": `${index * 50}ms` }}>
          <h3>{card.title}</h3>
          {card.items.length ? card.items.slice(0, 6).map((item) => <p key={item}>{item}</p>) : <p>No items returned for this section.</p>}
        </section>
      ))}
    </div>
  );
}

function SubScores({ subScores }) {
  const entries = Object.entries(subScores || {});
  if (!entries.length) return <p className="muted">No sub-score breakdown was returned for this category.</p>;
  return (
    <div className="subscore-list">
      {entries.map(([key, value]) => <SubScore key={key} name={key} value={value} />)}
    </div>
  );
}

function SubScore({ name, value }) {
  const data = value && typeof value === "object" ? value : {};
  const score = Number(data.score || 0);
  const max = Number(data.max || 0);
  const percent = max > 0 ? Math.max(0, Math.min(100, (score / max) * 100)) : 0;
  const scoreLabel = max ? `${formatScore(score)}/${formatScore(max)}` : formatDetail(value);
  return (
    <details className={`subscore ${scoreBand(percent).className}`}>
      <summary>
        <strong>{titleize(name)}{" \u2014 "}{scoreLabel}</strong>
        <ChevronDown size={18} />
      </summary>
      <div className="subscore-body">
        {data.reasoning && <p>{data.reasoning}</p>}
        {max > 0 && <i><b style={{ width: `${percent}%` }} /></i>}
      </div>
    </details>
  );
}

function categoryIcon(key, size = 18) {
  const icons = {
    overview: <BarChart3 size={size} />,
    role_fit: <Radar size={size} />,
    technical_skill: <Code2 size={size} />,
    technical_skills: <Code2 size={size} />,
    project_work: <Layers3 size={size} />,
    professional_experience: <Briefcase size={size} />,
    engineering_practices: <Wrench size={size} />,
    education_certifications: <BookOpen size={size} />,
    research: <FileSearch size={size} />,
    cv_quality: <FileText size={size} />,
    relevant_jobs: <Briefcase size={size} />,
  };
  return icons[key] || <Circle size={size} />;
}

function reportCandidateName(workspace) {
  const name = String(workspace.candidateName || "").trim();
  return name && name.toLowerCase() !== "candidate" ? name : "Abdul Moiz";
}

function candidateInitials(name) {
  const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
  return parts.length ? parts.slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") : "AM";
}

function roleFitLabel(workspace) {
  const score = Number(workspace.roleFitScore || 0);
  if (score >= 70) return "Strong match";
  if (score >= 41) return "Developing match";
  return "Needs support";
}

function recommendedRoles(workspace) {
  const role = formatRole(workspace.targetRole).toLowerCase();
  if (role.includes("ai") || role.includes("ml") || role.includes("data")) {
    return ["Junior ML Engineer", "AI Research Intern", "Data Science Trainee"];
  }
  const formatted = formatRole(workspace.targetRole);
  return [`Junior ${formatted}`, `${formatted} Intern`, `${formatted} Trainee`];
}

function moduleScoreLabel(category) {
  const score = Number(category.score);
  const max = Number(category.max_score);
  if (Number.isFinite(score) && Number.isFinite(max) && max > 0) {
    return `${formatScore(score)}/${formatScore(max)}`;
  }

  const totals = Object.values(category.sub_scores || {}).reduce((acc, item) => {
    if (!item || typeof item !== "object") return acc;
    const itemScore = Number(item.score);
    const itemMax = Number(item.max);
    if (!Number.isFinite(itemScore) || !Number.isFinite(itemMax) || itemMax <= 0) return acc;
    return {
      score: acc.score + itemScore,
      max: acc.max + itemMax,
    };
  }, { score: 0, max: 0 });

  if (totals.max > 0) {
    return `${formatScore(totals.score)}/${formatScore(totals.max)}`;
  }

  return `${formatScore(category.normalized_score)}/100`;
}

function formatRole(role) {
  const value = String(role || "").trim();
  if (!value) return "Selected Role";
  return titleize(value)
    .replace(/\bAi Ml\b/g, "AI/ML")
    .replace(/\bQa\b/g, "QA")
    .replace(/\bCv\b/g, "CV");
}

function formatJobLocation(job) {
  return job.city || job.location_raw || job.country || "Pakistan";
}

function formatJobType(job) {
  const parts = [
    job.employment_type && job.employment_type !== "unknown" ? titleize(job.employment_type) : "",
    job.experience_level && job.experience_level !== "unknown" ? titleize(job.experience_level) : "",
    job.workplace_type && job.workplace_type !== "unknown" ? titleize(job.workplace_type) : "",
  ].filter(Boolean);
  if (job.is_internship && !parts.some((part) => part.toLowerCase().includes("intern"))) {
    parts.unshift("Internship");
  }
  return parts.length ? parts.join(" / ") : "Job";
}

function formatSalary(job) {
  if (job.salary_raw) return job.salary_raw;
  if (job.salary_min || job.salary_max) {
    const currency = job.salary_currency || "PKR";
    const min = job.salary_min ? Number(job.salary_min).toLocaleString() : "";
    const max = job.salary_max ? Number(job.salary_max).toLocaleString() : "";
    const range = min && max ? `${min} - ${max}` : min || max;
    const period = job.salary_period && job.salary_period !== "unknown" ? ` / ${job.salary_period}` : "";
    return `${currency} ${range}${period}`;
  }
  return "Salary not listed";
}

function formatJobDate(value) {
  if (!value) return "Freshness unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Freshness unknown";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function buildStrengthItems(categories) {
  return [...categories]
    .sort((a, b) => Number(b.normalized_score || 0) - Number(a.normalized_score || 0))
    .filter((category) => category.evidence?.length || category.score_narrative || category.verdict_sentence)
    .slice(0, 4)
    .map((category) => ({
      title: category.name,
      body: truncateText(category.evidence?.[0] || category.score_narrative || category.verdict_sentence, 150),
    }));
}

function buildImprovementItems(categories) {
  return [...categories]
    .sort((a, b) => Number(a.normalized_score || 0) - Number(b.normalized_score || 0))
    .map((category) => {
      const body = category.missing_evidence?.[0] || category.recommendations?.[0] || (
        Number(category.normalized_score || 0) < 70 ? category.verdict_sentence || category.score_narrative : ""
      );
      return body ? { title: category.name, body: truncateText(body, 150) } : null;
    })
    .filter(Boolean)
    .slice(0, 4);
}

function categorySnippet(category) {
  return truncateText(
    category.verdict_sentence
      || category.score_narrative
      || category.evidence?.[0]
      || `${scoreBand(category.normalized_score).label} score in this section.`,
    82,
  );
}

function evidenceItemsForCategory(category) {
  if (category.extracted_items?.length) return category.extracted_items;
  if (category.evidence?.length) {
    return category.evidence.map((item, index) => ({
      title: `Evidence ${index + 1}`,
      body: item,
    }));
  }
  return [];
}

function truncateText(value, maxLength) {
  const text = String(value || "").trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, Math.max(0, maxLength - 3)).trim()}...`;
}

function DetailTable({ details }) {
  const blocked = new Set(["title", "subtitle", "body", "badges", "meta", "details"]);
  const entries = Object.entries(details || {}).filter(([key, value]) => {
    if (blocked.has(key)) return false;
    if (value === null || value === undefined || value === false) return false;
    if (Array.isArray(value) && value.length === 0) return false;
    return value !== "";
  });
  if (!entries.length) return null;
  return (
    <dl className="detail-table">
      {entries.map(([key, value]) => (
        <React.Fragment key={key}>
          <dt>{titleize(key)}</dt>
          <dd>{formatDetail(value)}</dd>
        </React.Fragment>
      ))}
    </dl>
  );
}

async function fetchScoresWithRetry(candidateId) {
  let lastError = null;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      const response = await fetch(`${API_URL}/candidates/${candidateId}/scores`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load scores");
      return data;
    } catch (err) {
      lastError = err;
      if (attempt < 3) await delay(350 * (2 ** (attempt - 1)));
    }
  }
  throw new Error(`${lastError?.message || "Could not load scores"} Try again from the results panel.`);
}

function delay(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function stageIcon(status) {
  if (status === "completed") return <CheckCircle2 size={19} />;
  if (status === "in_progress") return <Loader2 className="spin" size={19} />;
  if (status === "error") return <AlertTriangle size={19} />;
  return <Circle size={15} />;
}

function clampScore(value) {
  return Math.max(0, Math.min(100, Number(value || 0)));
}

function formatScore(value) {
  const number = Number(value || 0);
  return Number.isInteger(number) ? String(number) : number.toFixed(1).replace(/\.0$/, "");
}

function titleize(value) {
  return String(value).replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatDetail(value) {
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "object" && value !== null) return JSON.stringify(value);
  return String(value);
}

createRoot(document.getElementById("root")).render(<App />);
