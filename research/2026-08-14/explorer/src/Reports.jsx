import React, { useEffect, useMemo, useState } from "react";
import { api, formatNumber, stores } from "./api";
import ProductImage from "./Media";

const stageLabels = {
  queued: "等待开始", selecting_images: "确定报告图片范围",
  downloading_hd_images: "下载高清证据图片", analyzing_all_images: "逐张视觉分析",
  synthesizing_report_sections: "生成五个报告章节", report_analysis_complete: "专项分析完成",
  revising_section: "按修改建议重新分析Section", revision_complete: "Section修订完成",
  rendering_cover: "排版封面", rendering_sections: "排版报告章节",
  rendering_evidence_appendix: "排版逐图证据附录", publishing: "发布PDF",
  complete: "完成", failed: "失败",
};

function UsageRow({ label, usage }) {
  return <div><strong>{label}</strong><span>{formatNumber(usage?.total_tokens)} Token</span>
    <span>${Number(usage?.estimated_cost_usd || 0).toFixed(4)}</span>
    <span>{Number(usage?.wall_clock_seconds || 0).toFixed(1)} 秒</span></div>;
}

function UsageAudit({ analysis, generation }) {
  return <section className="generation-usage-audit">
    <UsageRow label="报告专项视觉分析" usage={analysis?.usage} />
    <UsageRow label="Section 修订（累计）" usage={analysis?.revision_usage} />
    <UsageRow label="最终 PDF 本地排版" usage={generation?.result?.usage} />
    <p>三部分独立计量；最终 PDF 排版不调用模型，Token 与费用均为 0。</p>
  </section>;
}

function ImageStrip({ ids, imageLookup }) {
  return <div className="evidence-images">{ids.map((id) => {
    const image = imageLookup.get(id);
    return image ? <article key={id}><ProductImage alt={image.title} src={image.resolved_url} />
      <span>{id}</span><small>{stores[image.store_id] || image.store_id}</small></article> : null;
  })}</div>;
}

function ClaimEvidence({ claim, imageLookup }) {
  const evidence = claim.evidence || {};
  const evidenceBrands = [...new Set([
    ...(evidence.support_image_ids || []), ...(evidence.example_image_ids || []),
  ].map((id) => imageLookup.get(id)?.store_id).filter(Boolean)
    .map((storeId) => stores[storeId] || storeId))];
  return <article className="report-claim">
    <span>结论</span><h4>{claim.conclusion}</h4>
    <div className="claim-derivation"><strong>怎么得到的</strong><p>{claim.derivation}</p></div>
    <dl className="claim-evidence-meta">
      <div><dt>分析覆盖</dt><dd>{formatNumber(evidence.sample_count)} 张</dd></div>
      <div><dt>筛选条件</dt><dd>{evidence.filters}</dd></div>
      <div><dt>观察字段</dt><dd>{(evidence.observation_fields || []).join("、")}</dd></div>
      <div><dt>支持 / 反例</dt><dd>{evidence.support_image_ids?.length || 0} / {evidence.counterexample_image_ids?.length || 0}</dd></div>
    </dl>
    {evidenceBrands.length ? <p className="evidence-brands"><b>证据店铺：</b>{evidenceBrands.join("、")}</p> : null}
    <strong className="evidence-subtitle">代表性证据图片</strong>
    <ImageStrip ids={evidence.example_image_ids || []} imageLookup={imageLookup} />
    <details className="source-record-list"><summary>查看全部支持与反例图片</summary>
      <strong>支持图片（{evidence.support_image_ids?.length || 0}）</strong>
      <ImageStrip ids={evidence.support_image_ids || []} imageLookup={imageLookup} />
      <strong>反例图片（{evidence.counterexample_image_ids?.length || 0}）</strong>
      {evidence.counterexample_image_ids?.length
        ? <ImageStrip ids={evidence.counterexample_image_ids} imageLookup={imageLookup} />
        : <p>无反例图片</p>}
    </details>
  </article>;
}

function SectionReview({ job, onReview, section }) {
  const current = job.review?.sections?.[section.section_id] || {};
  const revising = job.revision?.section_id === section.section_id
    && ["queued", "running"].includes(job.revision?.status || "");
  const [showSuggestion, setShowSuggestion] = useState(false);
  const [suggestion, setSuggestion] = useState("");
  return <div className={`section-review ${current.decision || "pending"}`}>
    <div><strong>这个 PDF Section 的分析与证据是否满意？</strong>
      <span>{revising ? "正在按建议重新分析" : current.decision === "up" ? "已通过" : "待审核"}</span></div>
    <div className="section-review-actions">
      <button disabled={revising} onClick={() => onReview(section.section_id, "up", "")} type="button">👍 满意</button>
      <button disabled={revising} onClick={() => setShowSuggestion(true)} type="button">👎 不满意</button>
    </div>
    {showSuggestion ? <div className="section-review-suggestion">
      <label htmlFor={`suggestion-${section.section_id}`}>修改建议（会触发该Section重新分析）</label>
      <textarea id={`suggestion-${section.section_id}`} maxLength="2000" value={suggestion}
        onChange={(event) => setSuggestion(event.target.value)} />
      <button disabled={!suggestion.trim() || revising}
        onClick={() => onReview(section.section_id, "down", suggestion).then(() => {
          setShowSuggestion(false); setSuggestion("");
        })} type="button">提交并重新分析</button>
    </div> : null}
    {revising ? <progress max="100" value={job.revision.progress || 0} /> : null}
    {job.revision?.section_id === section.section_id && job.revision?.status === "failed"
      ? <p className="error-banner">修订失败：{job.revision.error}</p> : null}
  </div>;
}

function ReportAnalysisDraft({ job, onReview }) {
  const result = job.result || {};
  const imageLookup = useMemo(() => new Map(
    (result.images || []).map((image) => [image.image_id, image]),
  ), [result.images]);
  const observationLookup = useMemo(() => new Map(
    (result.image_observations || []).map((row) => [row.image_id, row]),
  ), [result.image_observations]);
  return <div className="report-analysis-draft">
    {result.scope?.competitor_population_images == null ? <aside className="legacy-report-notice">
      这是旧版报告：三家竞品各最多 12 张分位选图，未按品牌拆分结论。新任务会使用竞品全量维度分布，
      再选择分层高清证据，并强制分别分析 Princess Polly、Motel Rocks、PrettyLittleThing。
    </aside> : null}
    <section className="report-summary"><div><span>REPORT-SPECIFIC ANALYSIS</span>
      <h2>报告专项分析草稿</h2><p>这是为最终视觉诊断 PDF 重新执行的分析，不是旧维度聚合结果。</p></div>
      <dl><div><dt>目标图片</dt><dd>{formatNumber(result.scope?.target_images)}</dd></div>
        <div><dt>竞品全量分母</dt><dd>{result.scope?.competitor_population_images == null
          ? "旧版未记录" : formatNumber(result.scope.competitor_population_images)}</dd></div>
        <div><dt>竞品高清证据</dt><dd>{formatNumber(result.scope?.competitor_images)}</dd></div>
        <div><dt>PDF Section</dt><dd>{result.sections?.length || 0}</dd></div></dl></section>
    <UsageAudit analysis={job} />
    <section className="report-executive-draft"><h3>执行摘要草稿</h3>
      <ul>{(result.executive_summary || []).map((item) => <li key={item}>{item}</li>)}</ul></section>
    <div className="report-sections">{(result.sections || []).map((section) =>
      <section className="report-section" key={section.section_id}>
        <header><span>PDF SECTION</span><h3>{section.title}</h3><p>{section.summary}</p>
          <small>方法：{section.methodology}</small></header>
        <div className="report-claims">{section.claims.map((claim) =>
          <ClaimEvidence claim={claim} imageLookup={imageLookup} key={claim.claim_id} />)}</div>
        <SectionReview job={job} onReview={onReview} section={section} />
      </section>)}</div>
    <details className="image-observation-appendix"><summary>
      查看全部逐图分析（{formatNumber(result.image_observations?.length)} 张）</summary>
      <div className="observation-grid">{(result.images || []).map((image) => {
        const observation = observationLookup.get(image.image_id) || {};
        return <article key={image.image_id}><ProductImage alt={image.title} src={image.resolved_url} />
          <div><code>{image.image_id}</code><strong>{stores[image.store_id] || image.store_id}</strong>
            <p>{observation.visual_role}</p>
            <details><summary>肉眼可见事实与证据线索</summary>
              <dl>{Object.entries(observation.observable || {}).map(([key, value]) =>
                <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl>
              <ul>{(observation.evidence_cues || []).map((cue) => <li key={cue}>{cue}</li>)}</ul>
            </details></div></article>;
      })}</div>
    </details>
  </div>;
}

function StartAnalysis({ disabled, onStart }) {
  return <section className="report-analysis-start">
    <span>ON-DEMAND REPORT ANALYSIS</span><h2>主动生成报告专项分析</h2>
    <p>点击后才会开始：下载 Aloruh 上衣与半身裙全部首图高清版本，逐图使用 GPT-5.6 Sol 分析；
      三家竞品的全部封面图先作为维度分布分母，再按店铺、品类和六个视觉维度选择高频典型图、
      覆盖率至少约 0.5% 的低频边界图，并按六维组合视觉簇补充代表图。不会随机抽图，
      也不会直接复用旧的维度结论。</p>
    <dl><div><dt>目标范围</dt><dd>Aloruh(SHEIN) · Tops + Skirts · SKU封面图</dd></div>
      <div><dt>成品结构</dt><dd>品牌定位 / 商品展示 / 店铺视觉 / 竞品差距 / 升级方向</dd></div>
      <div><dt>竞品选图</dt><dd>逐店铺全量分布 → 品类 × 六维度 → 高频典型 + ≥约0.5%低频边界 + 六维组合簇</dd></div>
      <div><dt>证据要求</dt><dd>逐图观察 + 支持图 + 反例图 + 代表图 + 推导方法</dd></div></dl>
    <button disabled={disabled} onClick={onStart} type="button">
      {disabled ? "报告专项分析运行中…" : "开始报告专项分析（会产生费用）"}</button>
  </section>;
}

function FinalReport({ analysis, generation, report, onGenerate }) {
  const ready = analysis?.review?.ready_for_final;
  return <div className="final-report"><section className="report-summary"><div>
    <span>FINAL PDF</span><h2>生成最终视觉诊断 PDF</h2>
    <p>最终报告仅使用已逐章通过的报告专项分析草稿进行本地排版。</p></div>
    <div className="report-file-actions"><button disabled={!ready || ["queued", "running"].includes(generation?.status)}
      onClick={onGenerate} type="button">{["queued", "running"].includes(generation?.status)
        ? "正在生成PDF…" : "生成最终PDF"}</button>
      {report?.has_pdf ? <><a href={api.reportFileUrl(report.report_id)} target="_blank" rel="noreferrer">浏览PDF</a>
        <a download href={api.reportFileUrl(report.report_id)}>下载PDF</a></> : null}</div></section>
    {!ready ? <div className="empty-results">请先将五个实际 PDF Section 全部审核为满意。</div> : null}
    <UsageAudit analysis={analysis} generation={generation} />
    {generation ? <section className={`report-generation ${generation.status}`}>
      <strong>{stageLabels[generation.stage] || generation.stage}</strong>
      <progress max="100" value={generation.progress || 0} />
      {generation.error ? <p>{generation.error}</p> : null}</section> : null}
  </div>;
}

export default function Reports() {
  const [tab, setTab] = useState("analysis");
  const [jobs, setJobs] = useState([]);
  const [selected, setSelected] = useState("");
  const [generation, setGeneration] = useState(null);
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const job = jobs.find((row) => row.job_id === selected);
  const running = jobs.some((row) => ["queued", "running"].includes(row.status)
    || ["queued", "running"].includes(row.revision?.status));
  const refresh = () => Promise.all([api.reportAnalyses(), api.reports()]).then(([analyses, reports]) => {
    setJobs(analyses.items || []);
    setSelected((value) => value || analyses.items?.[0]?.job_id || "");
    const first = reports.items?.[0];
    return first ? api.report(first.report_id).then(setReport) : setReport(null);
  });
  useEffect(() => { refresh().catch((reason) => setError(reason.message)); }, []);
  useEffect(() => {
    if (!running && !["queued", "running"].includes(generation?.status)) return undefined;
    const timer = window.setTimeout(() => {
      const requests = [refresh()];
      if (["queued", "running"].includes(generation?.status)) {
        requests.push(api.reportGeneration(generation.job_id).then((value) => {
          setGeneration(value);
          return value.status === "complete" ? refresh() : value;
        }));
      }
      Promise.all(requests).catch((reason) => setError(reason.message));
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [running, generation?.status, generation?.job_id]);
  const start = () => api.startReportAnalysis({ target_store: "aloruh_shein",
    categories: ["TOPS", "SKIRTS"] })
    .then((created) => { setJobs((rows) => [created, ...rows]); setSelected(created.job_id); })
    .catch((reason) => setError(reason.message));
  const review = (sectionId, decision, suggestion) => api.reviewReportSection(
    job.job_id, sectionId, decision, suggestion,
  ).then((updated) => setJobs((rows) => rows.map((row) => row.job_id === updated.job_id ? updated : row)))
    .catch((reason) => { setError(reason.message); throw reason; });
  const generate = () => api.generateReport(job.job_id).then(setGeneration)
    .catch((reason) => setError(reason.message));
  return <div className="reports-page">
    <nav className="report-tabs"><button className={tab === "analysis" ? "active" : ""}
      onClick={() => setTab("analysis")} type="button">1. 报告专项分析与审核</button>
      <button className={tab === "final" ? "active" : ""} disabled={!job?.review?.ready_for_final}
        onClick={() => setTab("final")} type="button">2. 生成最终PDF</button></nav>
    {error ? <div className="error-banner">{error}</div> : null}
    {tab === "analysis" ? <><StartAnalysis disabled={running} onStart={start} />
      {jobs.length ? <div className="report-job-picker">{jobs.map((row) => <button
        className={row.job_id === selected ? "active" : ""} key={row.job_id}
        onClick={() => setSelected(row.job_id)} type="button">
        <strong>{row.job_id.slice(0, 8)}</strong><span>{row.status}</span></button>)}</div> : null}
      {job && ["queued", "running"].includes(job.status) ? <section className="report-generation">
        <strong>{stageLabels[job.stage] || job.stage}</strong><progress max="100" value={job.progress || 0} />
      </section> : null}
      {job?.status === "failed" ? <div className="error-banner">{job.error}</div> : null}
      {job?.status === "complete" ? <ReportAnalysisDraft job={job} onReview={review} /> : null}</>
      : <FinalReport analysis={job} generation={generation} onGenerate={generate} report={report} />}
  </div>;
}
