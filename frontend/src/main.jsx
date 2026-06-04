import React, { useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertTriangle,
  BarChart3,
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  Circle,
  Code2,
  FileSearch,
  Layers3,
  Loader2,
  Radar,
  Sparkles,
  Trophy,
  UploadCloud,
} from "lucide-react";
import "./styles.css";
import { buildTabs, normalizeWorkspace, scoreBand } from "./workspaceUtils.mjs";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

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
  { key: "scoring", label: "Scoring Agent", status: "idle", message: "Waiting for scoring agent." },
  { key: "summarizer", label: "Summarizer Agent", status: "idle", message: "Waiting for summarizer agent." },
  { key: "results_ready", label: "Results Ready", status: "idle", message: "Waiting for final results." },
];

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
      <h2>{active ? active.label : "Your scoring workspace is ready."}</h2>
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
  return (
    <div className="subscore">
      <div>
        <strong>{titleize(name)}</strong>
        {data.reasoning && <p>{data.reasoning}</p>}
      </div>
      <span>{max ? `${formatScore(score)}/${formatScore(max)}` : formatDetail(value)}</span>
      <i><b style={{ width: `${percent}%` }} /></i>
    </div>
  );
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
