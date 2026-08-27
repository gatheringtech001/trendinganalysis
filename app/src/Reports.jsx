import React, { useEffect, useMemo, useState } from "react";
import { api, formatNumber, stores } from "./api";
import { formatCategory } from "./imageAnalysis";
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
const observableLabels = {
  scene: "拍摄场景", framing: "画面构图", pose_action: "姿势与动作",
  lighting: "光线", palette: "色彩", styling: "搭配",
  silhouette: "廓形", design_details: "设计细节", material_texture: "材质纹理",
  garment_display: "商品展示", first_image_type: "首图类型",
  brand_signal: "品牌信号", text_overlay: "文字叠加", model_presence: "模特在场",
  face_visibility: "面部可见性", hairstyle: "可见发型",
  makeup_presentation: "可见妆容", expression_gaze: "表情与视线",
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
  const profile = result.scope?.store_profile || {};
  const keyAnalysis = result.scope?.key_category_analysis || {};
  const imageLookup = useMemo(() => new Map(
    (result.images || []).map((image) => [image.image_id, image]),
  ), [result.images]);
  const observationLookup = useMemo(() => new Map(
    (result.image_observations || []).map((row) => [row.image_id, row]),
  ), [result.image_observations]);
  return <div className="report-analysis-draft">
    {!result.scope?.key_category_analysis ? <aside className="legacy-report-notice">
      这是旧版报告：三家竞品各最多 12 张分位选图，未按品牌拆分结论。新任务会使用竞品全量维度分布，
      再选择分层高清证据，并强制分别分析 Princess Polly、Motel Rocks、PrettyLittleThing。
    </aside> : null}
    <section className="report-summary"><div><span>REPORT-SPECIFIC ANALYSIS</span>
      <h2>报告专项分析草稿</h2><p>这是为最终视觉诊断 PDF 重新执行的分析，不是旧维度聚合结果。</p></div>
      <dl><div><dt>目标商品 / 图片</dt><dd>{formatNumber(result.scope?.target_products)} / {formatNumber(result.scope?.target_images)}</dd></div>
        <div><dt>竞品12维可比分母</dt><dd>{result.scope?.competitor_population_images == null
          ? "旧版未记录" : formatNumber(result.scope.competitor_population_images)}</dd></div>
        <div><dt>竞品高清证据</dt><dd>{formatNumber(result.scope?.competitor_images)}</dd></div>
        <div><dt>PDF Section</dt><dd>{result.sections?.length || 0}</dd></div></dl></section>
    {result.scope?.key_category_analysis ? <section className="analysis-scope-cards">
      <article><span>店铺基本信息</span><h3>{profile.store_name}</h3>
        <dl><div><dt>商品</dt><dd>{formatNumber(profile.product_count)}</dd></div>
          <div><dt>图片索引</dt><dd>{formatNumber(profile.image_count)}</dd></div>
          <div><dt>市场</dt><dd>{profile.market || "未记录"}</dd></div>
          <div><dt>数据更新时间</dt><dd>{profile.data_updated_at?.slice(0, 19) || "未记录"}</dd></div></dl></article>
      <article><span>重点品类 · 全量排序后随机复核</span><h3>前三重点＋白皮书补充品类</h3>
        <ol>{[
          ...(keyAnalysis.key_categories || []),
          ...(keyAnalysis.supplementary_categories || []),
        ].map((row) => <li key={row.category}>
          <strong>{formatCategory(row.category)}</strong>
          <span>全量 {formatNumber(row.population_products)} 件</span>
          <span>随机 {formatNumber(row.sample_selected)} 个商品 / 成功读取 {formatNumber(row.downloaded_images ?? row.sample_selected)} 张图</span>
        </li>)}</ol>
        <small>复现种子：{keyAnalysis.sampling?.seed}</small></article>
      <article><span>图片与竞品证据</span><h3>缓存优先，不重复下载</h3>
        <dl><div><dt>缓存命中</dt><dd>{formatNumber(result.cache_hits)}</dd></div>
          <div><dt>实际下载</dt><dd>{formatNumber(result.network_downloads)}</dd></div>
          <div><dt>竞品</dt><dd>{Object.values(result.scope?.competitor_brands || {}).join(" / ")}</dd></div>
          <div><dt>明确排除</dt><dd>人群画像、代表红人、敏感属性推断</dd></div></dl></article>
    </section> : null}
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
                <div key={key}><dt>{observableLabels[key] || key}</dt><dd>{value}</dd></div>)}</dl>
              <ul>{(observation.evidence_cues || []).map((cue) => <li key={cue}>{cue}</li>)}</ul>
            </details></div></article>;
      })}</div>
    </details>
  </div>;
}

function StartAnalysis({ categories, disabled, onStart, summary }) {
  const supplementary = "T恤 / 半裙 / 两件套 / 外套 / 西装 / 针织套装";
  return <section className="report-analysis-start">
    <span>ON-DEMAND REPORT ANALYSIS</span><h2>主动生成报告专项分析</h2>
    <p>先用店铺全部商品计算品类结构，前三大品类各抽20个商品，并从白皮书重点补充品类各抽5个；
      每个商品最多读取2个视角，用 GPT-5.6 Sol 逐图复核。目标店首图使用完整15维标签；三家竞品仍使用已采集
      12 维标签分布选择典型与有效边界证据；只有标签完整的品类进入竞品比较，未覆盖品类会明确标注不比较。
      高清图片优先命中共享缓存，不重复下载。</p>
    <dl><div><dt>店铺全量</dt><dd>{formatNumber(summary?.metrics?.products)} 个商品 · {formatNumber(summary?.metrics?.images)} 条图片索引</dd></div>
      <div><dt>自动重点品类</dt><dd>{categories.length
        ? categories.map((row) => `${formatCategory(row.category)} ${formatNumber(row.products)}件`).join(" / ")
        : "正在读取…"}</dd></div>
      <div><dt>目标抽样</dt><dd>前三品类各20个＋补充品类各5个 · 每商品最多2视角</dd></div>
      <div><dt>补充品类</dt><dd>{supplementary}</dd></div>
      <div><dt>成品结构</dt><dd>品牌定位 / 商品展示 / 店铺视觉 / 竞品差距 / 升级方向</dd></div>
      <div><dt>竞品选图</dt><dd>Princess Polly / Motel Rocks / PrettyLittleThing · 完整 12 维可比分母 → 典型与有效边界证据</dd></div>
      <div><dt>分析边界</dt><dd>覆盖可见模特特征；不做人群画像、代表红人或敏感属性推断</dd></div></dl>
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
  const [catalogSummary, setCatalogSummary] = useState(null);
  const [catalogCategories, setCatalogCategories] = useState([]);
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
  const keyCategoryPreview = useMemo(
    () => catalogCategories.slice(0, 3), [catalogCategories],
  );
  useEffect(() => {
    Promise.all([
      refresh(), api.summary("aloruh_shein"), api.categories("aloruh_shein"),
    ]).then(([, summary, categories]) => {
      setCatalogSummary(summary);
      setCatalogCategories(categories.items || []);
    }).catch((reason) => setError(reason.message));
  }, []);
  useEffect(() => {
    if (!running && !["queued", "running"].includes(generation?.status)) return undefined;
    let cancelled = false;
    let timer;
    const poll = () => {
      const requests = [refresh()];
      if (["queued", "running"].includes(generation?.status)) {
        requests.push(api.reportGeneration(generation.job_id).then((value) => {
          setGeneration(value);
          return value.status === "complete" ? refresh() : value;
        }));
      }
      Promise.all(requests)
        .catch((reason) => setError(reason.message))
        .finally(() => {
          if (!cancelled) timer = window.setTimeout(poll, 1000);
        });
    };
    timer = window.setTimeout(poll, 1000);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [running, generation?.status, generation?.job_id]);
  const start = () => api.startReportAnalysis({
    target_store: "aloruh_shein", category_mode: "auto",
    key_category_limit: 3, sample_per_category: 20,
  })
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
    {tab === "analysis" ? <><StartAnalysis categories={keyCategoryPreview} disabled={running}
      onStart={start} summary={catalogSummary} />
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
