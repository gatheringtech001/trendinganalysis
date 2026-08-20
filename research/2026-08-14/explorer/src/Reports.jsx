import React, { memo, useEffect, useMemo, useState } from "react";
import { api, formatNumber, stores } from "./api";
import { CompletedAnalysis } from "./DetailedVisualAnalysis";
import { dimensionLabels, formatAnalysisTag } from "./imageAnalysis";
import ProductImage from "./Media";

const tabs = { detailed: "1. Detailed 审核", final: "2. 最终报告" };
const generationStages = {
  queued: "排队中", aggregating: "聚合分析数据", downloading_evidence_images: "获取证据图片",
  rendering_sections: "生成报告章节", rendering_evidence_appendix: "生成证据附录",
  publishing: "发布报告文件", complete: "生成完成", failed: "生成失败",
};

function EvidenceDetails({ evidence, title = "查看完整证据链" }) {
  const filters = Object.entries(evidence?.filters || {});
  return (
    <details className="report-evidence">
      <summary>{title}</summary>
      <div className="evidence-meta">
        <span><b>方法</b>{evidence?.analysis_method || "—"}</span>
        <span><b>样本</b>{formatNumber(evidence?.sample_count)} 张</span>
        <span><b>源记录</b>{formatNumber(evidence?.source_records?.length)} 条</span>
      </div>
      <div className="evidence-filters">
        {filters.map(([key, value]) => (
          <span key={key}>{dimensionLabels[key] || key}：{
            (Array.isArray(value) ? value : [value]).map(formatAnalysisTag).join("、")
          }</span>
        ))}
      </div>
      {evidence?.metrics?.length ? <div className="evidence-metrics">
        {evidence.metrics.map((metric, index) => (
          <span key={`${metric.name || metric.label || metric.row}-${index}`}>
            <b>{formatAnalysisTag(metric.name || metric.label || `${metric.row} × ${metric.column}`)}</b>
            {formatNumber(metric.value ?? metric.count)}
          </span>
        ))}
      </div> : null}
      {evidence?.images?.length ? <div className="evidence-images">
        {evidence.images.map((image) => (
          <article key={`${image.product_id}-${image.image_url}`}>
            <ProductImage alt={image.title} src={image.image_url} />
            <span>{image.product_id}</span>
          </article>
        ))}
      </div> : null}
      <details className="source-record-list">
        <summary>全部 {formatNumber(evidence?.source_records?.length)} 条源记录ID</summary>
        <code>{(evidence?.source_records || []).join("\n")}</code>
      </details>
    </details>
  );
}

const ReportSection = memo(function ReportSection({ section }) {
  return (
    <section className="report-section">
      <header><span>SECTION</span><h3>{section.title}</h3><p>{section.description}</p></header>
      <EvidenceDetails evidence={section.evidence} title="查看Section证据范围" />
      <div className="report-claims">
        {section.claims.map((claim) => (
          <article key={claim.claim_id}>
            <span>结论</span><p>{claim.conclusion}</p>
            <EvidenceDetails evidence={claim.evidence} />
          </article>
        ))}
      </div>
    </section>
  );
});

function AttentionHeatmap({ data }) {
  const max = Math.max(...(data?.cells || []).map((cell) => cell.count), 1);
  return (
    <section className="report-visual-card">
      <header><span>VISUAL ATTENTION</span><h3>视觉焦点热力图</h3></header>
      <div className="attention-map" aria-label="视觉焦点身体区域热力图">
        <div className="body-outline" />
        {(data?.cells || []).map((cell) => (
          <span key={cell.label} style={{ left: `${cell.x}%`, top: `${cell.y}%`,
            "--heat": cell.count / max, "--size": `${24 + 34 * cell.count / max}px` }}
            title={`${formatAnalysisTag(cell.label)}：${cell.count}张`}>
            {formatAnalysisTag(cell.label)}<b>{cell.count}</b>
          </span>
        ))}
      </div>
      <p>热度表示该区域被selling_points标签覆盖的图片数，不代表销量或商业热度。</p>
    </section>
  );
}

function CombinationHeatmap({ data }) {
  const cells = data?.cells || [];
  const lookup = useMemo(() => new Map(
    cells.map((cell) => [`${cell.row}:${cell.column}`, cell.count]),
  ), [cells]);
  const max = Math.max(...cells.map((cell) => cell.count), 1);
  return (
    <section className="report-visual-card combination-card">
      <header><span>CO-OCCURRENCE</span><h3>维度组合热力图</h3></header>
      <div className="combination-scroll"><table><thead><tr><th>构图 × 动作</th>
        {(data?.columns || []).map((column) => <th key={column}>{formatAnalysisTag(column)}</th>)}
      </tr></thead><tbody>{(data?.rows || []).map((row) => <tr key={row}>
        <th>{formatAnalysisTag(row)}</th>
        {(data?.columns || []).map((column) => {
          const count = lookup.get(`${row}:${column}`) || 0;
          return <td key={column} style={{ "--heat": count / max }}>{count}</td>;
        })}
      </tr>)}</tbody></table></div>
      <p>每个单元格是构图与动作标签在同一张图片中的共现次数。</p>
    </section>
  );
}

function SourceRecordAppendix({ records }) {
  return <section className="source-record-appendix">
    <header><span>DATA EVIDENCE</span><h3>证据数据明细 · {formatNumber(records.length)} 条</h3>
      <p>记录ID与每个Section、Claim证据链中的source_records一一对应。</p></header>
    <div className="source-record-table"><table><thead><tr><th>证据图片</th><th>记录ID</th>
      <th>类别</th><th>分析方法</th><th>维度标签</th><th>平均置信度</th></tr></thead>
      <tbody>{records.map((record) => {
        const confidence = Object.values(record.confidence || {});
        const average = confidence.length
          ? confidence.reduce((sum, value) => sum + Number(value), 0) / confidence.length : 0;
        return <tr key={record.record_id}><td>{record.image
          ? <ProductImage alt={record.image.title} src={record.image.image_url} /> : "—"}</td>
          <td><code>{record.record_id}</code><small>{record.image?.product_id}</small></td>
          <td>{formatAnalysisTag(record.category)}</td><td>{record.analysis_method}</td>
          <td>{Object.entries(record.tags || {}).map(([dimension, values]) =>
            `${dimensionLabels[dimension] || dimension}：${values.map(formatAnalysisTag).join("、")}`,
          ).join("；")}</td><td>{Math.round(average * 100)}%</td></tr>;
      })}</tbody></table></div>
  </section>;
}

function UsageAudit({ generation, detailed }) {
  const upstream = generation?.result?.upstream_detailed_usage || detailed?.usage || {};
  const pdfUsage = generation?.result?.usage || {};
  return <section className="generation-usage-audit">
    <div><strong>上游 Detailed 分析</strong><span>{formatNumber(upstream.total_tokens)} Token</span>
      <span>${Number(upstream.estimated_cost_usd || 0).toFixed(4)}</span></div>
    <div><strong>最终 PDF 生成</strong><span>{formatNumber(pdfUsage.total_tokens)} Token</span>
      <span>${Number(pdfUsage.estimated_cost_usd || 0).toFixed(4)}</span></div>
    <p>最终 PDF 仅做本地排版，不调用模型；费用不会重复计算。</p>
  </section>;
}

function FinalReport({ detailed, report, generation, onGenerate }) {
  const [showRecords, setShowRecords] = useState(false);
  if (!report) return <div className="loading">正在生成可追溯报告视图…</div>;
  const fileUrl = api.reportFileUrl(report.report_id);
  return <div className="final-report">
    <section className="report-summary">
      <div><span>FINAL VISUAL DIAGNOSIS</span><h2>{report.title}</h2><p>{report.summary}</p></div>
      <dl><div><dt>样本</dt><dd>{formatNumber(report.sample_count)}</dd></div>
        <div><dt>维度</dt><dd>{report.dimension_coverage.target}</dd></div>
        <div><dt>Section</dt><dd>{report.sections.length}</dd></div></dl>
      <div className="report-file-actions">
        <button disabled={["queued", "running"].includes(generation?.status)}
          onClick={onGenerate} type="button">
          {["queued", "running"].includes(generation?.status) ? "正在生成…" : "生成最终报告"}
        </button>
        {report.has_pdf ? <><a href={fileUrl} target="_blank" rel="noreferrer">浏览PDF</a>
          <a download href={fileUrl}>下载PDF</a></> : null}
      </div>
    </section>
    <section className="approved-detailed-source"><strong>已通过审核的 Detailed 报告</strong>
      <code>{detailed?.job_id}</code><span>7 / 7 Section 满意</span></section>
    <UsageAudit detailed={detailed} generation={generation} />
    {generation ? <section className={`report-generation ${generation.status}`}>
      <div><strong>{generationStages[generation.stage] || generation.stage}</strong>
        <span>{generation.progress || 0}%</span></div>
      <progress max="100" value={generation.progress || 0} />
      {generation.error ? <p>{generation.error}</p> : null}
      {generation.status === "complete" ? <p>
        已按当前数据重新生成 {generation.result?.pages} 页报告，覆盖
        {formatNumber(generation.result?.sample_count)} 张图片。
      </p> : null}
    </section> : null}
    <div className="report-heatmaps"><AttentionHeatmap data={report.attention_heatmap} />
      <CombinationHeatmap data={report.combination_heatmap} /></div>
    <div className="report-sections">{report.sections.map((section) => (
      <ReportSection key={section.section_id} section={section} />
    ))}</div>
    <button className="source-record-toggle" onClick={() => setShowRecords((value) => !value)} type="button">
      {showRecords ? "收起证据数据明细" : `打开证据数据明细（${formatNumber(report.source_records.length)}条）`}
    </button>
    {showRecords ? <SourceRecordAppendix records={report.source_records} /> : null}
  </div>;
}

function DetailedReports({ onReady, onReview, onSelect, reviewSaving, rows, selected }) {
  const job = rows.find((row) => row.job_id === selected);
  if (!rows.length) return <div className="empty-results">还没有已保存的Detailed高清分析任务。</div>;
  return <div className="detailed-report-history">
    <aside>{rows.map((row) => <button className={selected === row.job_id ? "active" : ""}
      key={row.job_id} onClick={() => onSelect(row.job_id)} type="button">
      <strong>{Object.values(row.filters || {}).map(formatAnalysisTag).join(" · ") || "自定义选图"}</strong>
      <span>{(row.stores || []).map((store) => stores[store] || store).join("、")}</span>
      <small>{row.status === "complete" ? `审核 ${row.review?.approved_sections || 0} / ${row.review?.total_sections || 7}` : row.status}</small>
    </button>)}</aside>
    <main>{job ? <><section className={`review-workflow ${job.review?.ready_for_final ? "ready" : "pending"}`}>
      <div><strong>Detailed Section 审核</strong><span>
        已审核 {job.review?.reviewed_sections || 0} / {job.review?.total_sections || 7}，
        满意 {job.review?.approved_sections || 0} / {job.review?.total_sections || 7}
      </span></div>
      {job.review?.rejected_sections ? <p>有 {job.review.rejected_sections} 个 Section 待按建议修订，最终报告暂时锁定。</p> : null}
      {job.review?.ready_for_final ? <button onClick={onReady} type="button">进入最终报告生成</button>
        : <p>请逐项审核下方全部 Section；只有全部 👍 满意后才能生成最终报告。</p>}
    </section><CompletedAnalysis job={job} onReview={(sectionId, decision, suggestion) =>
      onReview(job.job_id, sectionId, decision, suggestion)} reviewSaving={reviewSaving} /></> : null}</main>
  </div>;
}

export default function Reports() {
  const [tab, setTab] = useState("detailed");
  const [report, setReport] = useState(null);
  const [detailed, setDetailed] = useState([]);
  const [generation, setGeneration] = useState(null);
  const [selectedDetailed, setSelectedDetailed] = useState("");
  const [reviewSaving, setReviewSaving] = useState("");
  const [error, setError] = useState("");
  const loadReport = () => api.reports().then((reports) => {
    const first = reports.items?.[0];
    return first ? api.report(first.report_id) : null;
  });
  useEffect(() => {
    let active = true;
    Promise.all([loadReport(), api.detailedAnalyses()]).then(([value, jobs]) => {
      if (!active) return;
      setReport(value);
      setDetailed(jobs.items || []);
      setSelectedDetailed((current) => current || jobs.items?.[0]?.job_id || "");
    }).catch((reason) => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (!["queued", "running"].includes(generation?.status)) return undefined;
    const timer = window.setTimeout(() => {
      api.reportGeneration(generation.job_id).then((job) => {
        setGeneration(job);
        if (job.status === "complete") loadReport().then(setReport);
      }).catch((reason) => setError(reason.message));
    }, 750);
    return () => window.clearTimeout(timer);
  }, [generation]);
  const generate = () => {
    setError("");
    api.generateReport(selectedDetailed).then(setGeneration).catch((reason) => setError(reason.message));
  };
  const reviewSection = (jobId, sectionId, decision, suggestion) => {
    setError("");
    setReviewSaving(sectionId);
    return api.reviewDetailedSection(jobId, sectionId, decision, suggestion).then((updated) => {
      setDetailed((rows) => rows.map((row) => row.job_id === jobId ? updated : row));
    }).catch((reason) => setError(reason.message)).finally(() => setReviewSaving(""));
  };
  const detailedJob = detailed.find((row) => row.job_id === selectedDetailed);
  const finalReady = Boolean(detailedJob?.review?.ready_for_final);
  return <div className="reports-page">
    <nav className="report-tabs" aria-label="报告类型">{Object.entries(tabs).map(([key, label]) => (
      <button aria-current={tab === key ? "page" : undefined} className={tab === key ? "active" : ""}
        disabled={key === "final" && !finalReady} key={key} onClick={() => setTab(key)}
        title={key === "final" && !finalReady ? "请先完成Detailed报告Section审核" : ""}
        type="button">{label}</button>
    ))}</nav>
    {error ? <div className="error-banner">{error}</div> : null}
    {tab === "final" ? <FinalReport detailed={detailedJob} generation={generation}
      onGenerate={generate} report={report} /> : <DetailedReports onReady={() => setTab("final")}
      onReview={reviewSection} onSelect={setSelectedDetailed} reviewSaving={reviewSaving}
      rows={detailed} selected={selectedDetailed} />}
  </div>;
}
