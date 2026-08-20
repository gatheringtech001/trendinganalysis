import React, { memo, useEffect, useMemo, useState } from "react";
import { api, formatNumber, stores } from "./api";
import { CompletedAnalysis } from "./DetailedVisualAnalysis";
import { dimensionLabels, formatAnalysisTag } from "./imageAnalysis";
import ProductImage from "./Media";

const tabs = { final: "最终视觉诊断", detailed: "Detailed 高清精细分析" };

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

function FinalReport({ report }) {
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
        <a href={fileUrl} target="_blank" rel="noreferrer">浏览PDF</a>
        <a download href={fileUrl}>下载PDF</a>
      </div>
    </section>
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

function DetailedReports({ rows }) {
  const [selected, setSelected] = useState(rows[0]?.job_id || "");
  useEffect(() => { if (!selected && rows[0]) setSelected(rows[0].job_id); }, [rows, selected]);
  const job = rows.find((row) => row.job_id === selected);
  if (!rows.length) return <div className="empty-results">还没有已保存的Detailed高清分析任务。</div>;
  return <div className="detailed-report-history">
    <aside>{rows.map((row) => <button className={selected === row.job_id ? "active" : ""}
      key={row.job_id} onClick={() => setSelected(row.job_id)} type="button">
      <strong>{Object.values(row.filters || {}).map(formatAnalysisTag).join(" · ") || "自定义选图"}</strong>
      <span>{(row.stores || []).map((store) => stores[store] || store).join("、")}</span>
      <small>{row.status === "complete" ? "已完成" : row.status}</small>
    </button>)}</aside>
    <main>{job ? <CompletedAnalysis job={job} /> : null}</main>
  </div>;
}

export default function Reports() {
  const [tab, setTab] = useState("final");
  const [report, setReport] = useState(null);
  const [detailed, setDetailed] = useState([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api.reports().then((reports) => {
      const first = reports.items?.[0];
      return Promise.all([first ? api.report(first.report_id) : null, api.detailedAnalyses()]);
    }).then(([value, jobs]) => {
      if (!active) return;
      setReport(value);
      setDetailed(jobs.items || []);
    }).catch((reason) => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, []);
  return <div className="reports-page">
    <nav className="report-tabs" aria-label="报告类型">{Object.entries(tabs).map(([key, label]) => (
      <button aria-current={tab === key ? "page" : undefined} className={tab === key ? "active" : ""}
        key={key} onClick={() => setTab(key)} type="button">{label}</button>
    ))}</nav>
    {error ? <div className="error-banner">{error}</div> : null}
    {tab === "final" ? <FinalReport report={report} /> : <DetailedReports rows={detailed} />}
  </div>;
}
