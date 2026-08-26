import React, { useEffect, useState } from "react";
import { formatNumber, stores as storeNames } from "./api";
import ProductImage from "./Media";

const stageLabels = {
  queued: "等待执行",
  downloading_hd_images: "正在下载并校验高清图",
  sol_visual_analysis: "GPT-5.6 Sol 正在进行精细视觉分析",
  complete: "分析完成",
  failed: "分析失败",
};
const observableLabels = {
  scene: "场景", framing: "景别与构图", pose_action: "动作与姿态",
  lighting: "光线", color_palette: "色彩", styling: "搭配",
  garment_details: "服装细节",
};

function TextList({ items }) {
  if (!items?.length) return null;
  return <ul>{items.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>;
}

function UsageSummary({ usage }) {
  if (!usage) return null;
  return (
    <><dl className="detailed-usage">
      <div><dt>总耗时</dt><dd>{Number(usage.wall_clock_seconds || 0).toFixed(1)} 秒</dd></div>
      <div><dt>API 调用</dt><dd>{formatNumber(usage.api_calls)}</dd></div>
      <div><dt>输入 Token</dt><dd>{formatNumber(usage.input_tokens)}</dd></div>
      <div><dt>缓存输入 Token</dt><dd>{formatNumber(usage.cached_input_tokens)}</dd></div>
      <div><dt>输出 Token</dt><dd>{formatNumber(usage.output_tokens)}</dd></div>
      <div><dt>Reasoning Token</dt><dd>{formatNumber(usage.reasoning_tokens)}</dd></div>
      <div><dt>总 Token</dt><dd>{formatNumber(usage.total_tokens)}</dd></div>
      <div><dt>预估费用</dt><dd>${Number(usage.estimated_cost_usd || 0).toFixed(4)}</dd></div>
    </dl><p className="detailed-pricing-note">{usage.pricing?.source || "费用为运行记录中的预估值"}</p></>
  );
}

function SectionReview({ sectionId, title, review, onReview, saving }) {
  const current = review?.sections?.[sectionId] || {};
  const [editingDown, setEditingDown] = useState(current.decision === "down");
  const [suggestion, setSuggestion] = useState(current.suggestion || "");
  useEffect(() => {
    setEditingDown(current.decision === "down");
    setSuggestion(current.suggestion || "");
  }, [current.decision, current.suggestion]);
  return <div className={`section-review ${current.decision || "pending"}`}>
    <div><strong>这个 Section 是否满意？</strong><span>{current.decision === "up"
      ? "已通过" : current.decision === "down" ? "待按建议修订" : "待审核"}</span></div>
    <div className="section-review-actions">
      <button aria-label={`${title}满意`} aria-pressed={current.decision === "up"}
        disabled={saving} onClick={() => onReview(sectionId, "up", "")} type="button">👍 满意</button>
      <button aria-label={`${title}不满意`} aria-pressed={current.decision === "down"}
        disabled={saving} onClick={() => setEditingDown(true)} type="button">👎 不满意</button>
    </div>
    {editingDown ? <div className="section-review-suggestion">
      <label htmlFor={`review-${sectionId}`}>修改建议（必填）</label>
      <textarea id={`review-${sectionId}`} maxLength="2000" placeholder="说明需要修改的结论、证据或表达方式"
        value={suggestion} onChange={(event) => setSuggestion(event.target.value)} />
      <button disabled={saving || !suggestion.trim()}
        onClick={() => onReview(sectionId, "down", suggestion)} type="button">
        {saving ? "保存中…" : "保存修改建议"}
      </button>
    </div> : null}
  </div>;
}

function ReviewableSection({ children, reviewProps, sectionId, title }) {
  return <section><h3>{title}</h3>{children}<SectionReview sectionId={sectionId}
    title={title} {...reviewProps} /></section>;
}

function StoreResults({ rows }) {
  return (
    <div className="detailed-store-results">
      {(rows || []).map((row) => (
        <article key={row.store_id}>
          <h4>{storeNames[row.store_id] || row.store_id}</h4>
          <p>{row.visual_positioning}</p>
          <h5>可复制视觉代码</h5>
          <TextList items={row.repeatable_codes} />
          <h5>不一致点 / 信息缺口</h5>
          <TextList items={row.inconsistencies} />
        </article>
      ))}
    </div>
  );
}

function Hypotheses({ rows }) {
  return (
    <div className="detailed-hypotheses">
      {(rows || []).map((row, index) => (
        <article key={`${index}-${row.change}`}>
          <h4>{row.change}</h4>
          <p>{row.mechanism}</p>
          <dl><dt>验证指标</dt><dd>{row.kpi}</dd><dt>实验设计</dt><dd>{row.test_design}</dd></dl>
        </article>
      ))}
    </div>
  );
}

function ImageResults({ analysisRows, images }) {
  return (
    <div className="detailed-image-results">
      {(analysisRows || []).map((row) => {
        const image = images?.[row.i - 1] || {};
        return (
          <article key={row.i}>
            <div className="detailed-image-heading">
              {image.resolved_url ? <ProductImage src={image.resolved_url} alt={`分析图片 ${row.i}`} /> : null}
              <div>
                <span>图片 {row.i}</span>
                <h4>{storeNames[image.store_id] || image.store_id || "未知店铺"}</h4>
                <p>{image.product_id} · 置信度 {Math.round(Number(row.confidence || 0) * 100)}%</p>
              </div>
            </div>
            <p className="detailed-intent">{row.visual_intent}</p>
            <details><summary>肉眼可见事实</summary><dl className="observable-grid">
              {Object.entries(row.observable || {}).map(([key, value]) => (
                <div key={key}><dt>{observableLabels[key] || key}</dt><dd>{value}</dd></div>
              ))}
            </dl></details>
            <div className="detailed-image-columns">
              <section><h5>优点</h5><TextList items={row.strengths} /></section>
              <section><h5>不足</h5><TextList items={row.weaknesses} /></section>
              <section><h5>改进建议</h5><TextList items={row.recommended_changes} /></section>
            </div>
            <details><summary>证据链</summary><TextList items={(row.evidence || []).map(
              (item) => `${item.claim}：${item.visible_cue}`,
            )} /></details>
          </article>
        );
      })}
    </div>
  );
}

export function CompletedAnalysis({ job, onReview, reviewSaving }) {
  const result = job.result || {};
  const analysis = result.analysis || {};
  const reviewProps = {
    review: job.review, onReview,
    saving: reviewSaving,
  };
  return (
    <div className="detailed-results">
      <UsageSummary usage={job.usage} />
      <ReviewableSection reviewProps={reviewProps} sectionId="overall_conclusion" title="总体视觉结论">
        <p>{analysis.selection_thesis}</p>
      </ReviewableSection>
      <div className="detailed-two-column">
        <ReviewableSection reviewProps={reviewProps} sectionId="shared_patterns" title="共同模式">
          <TextList items={analysis.shared_patterns} />
        </ReviewableSection>
        <ReviewableSection reviewProps={reviewProps} sectionId="cross_store_differences" title="跨店差异">
          <TextList items={analysis.cross_store_differences} />
        </ReviewableSection>
      </div>
      <ReviewableSection reviewProps={reviewProps} sectionId="store_positioning" title="各店铺视觉定位">
        <StoreResults rows={analysis.store_summaries} />
      </ReviewableSection>
      <ReviewableSection reviewProps={reviewProps} sectionId="recommended_shot_system" title="推荐拍摄系统">
        <TextList items={analysis.recommended_shot_system} />
      </ReviewableSection>
      <ReviewableSection reviewProps={reviewProps} sectionId="ab_test_hypotheses" title="A/B 测试假设">
        <Hypotheses rows={analysis.test_hypotheses} />
      </ReviewableSection>
      <ReviewableSection reviewProps={reviewProps} sectionId="image_analysis" title="逐图精细分析">
        <ImageResults analysisRows={analysis.images} images={result.images} />
      </ReviewableSection>
    </div>
  );
}

export default function DetailedVisualAnalysis({
  analysisMode, disabled, eligibleStores, estimatedImages, imagesPerStore, job,
  maxImagesPerStore, onAnalysisModeChange, onImagesPerStoreChange, onStart,
  selectedImages,
}) {
  const running = ["queued", "running"].includes(job?.status);
  return (
    <section className="detailed-analysis-panel" aria-label="进一步精细视觉分析">
      <header>
        <div><span>SECOND-STAGE VISION</span><h2>进一步精细视觉分析</h2></div>
        <strong>GPT-5.6 Sol · 高清图</strong>
      </header>
      <p>当前维度条件只负责圈定图片集；这里会下载匹配商品的高清图，再分析构图、动作、卖点表达、店铺差异和可验证的优化方案。</p>
      <div className="detailed-selection-modes" role="radiogroup" aria-label="选择精细分析取图方式">
        <label className={analysisMode === "random" ? "selected" : ""}>
          <input
            checked={analysisMode === "random"}
            name="analysis-mode"
            onChange={() => onAnalysisModeChange("random")}
            type="radio"
          />
          <span><strong>随机取样</strong><small>从每家匹配店铺随机抽取</small></span>
        </label>
        <label className={analysisMode === "manual" ? "selected" : ""}>
          <input
            checked={analysisMode === "manual"}
            name="analysis-mode"
            onChange={() => onAnalysisModeChange("manual")}
            type="radio"
          />
          <span><strong>手动选图</strong><small>分析你在上方勾选的图片</small></span>
        </label>
      </div>
      <div className="detailed-analysis-actions">
        {analysisMode === "random" ? <label>每店抽样
            <select value={imagesPerStore} onChange={(event) => onImagesPerStoreChange(Number(event.target.value))}>
              {Array.from({ length: maxImagesPerStore }, (_, index) => index + 1).map((value) => (
                <option key={value} value={value}>{value} 张</option>
              ))}
            </select>
          </label> : <div><small>手动选择</small><strong>{selectedImages.length} / 24 张</strong></div>}
        <div><small>将分析</small><strong>{analysisMode === "manual"
          ? `${new Set(selectedImages.map((item) => item.store_id)).size} 家店 · ${estimatedImages} 张高清图`
          : `${eligibleStores.length} 家店 · 约 ${estimatedImages} 张高清图`}</strong></div>
        <button disabled={disabled || running} onClick={onStart} type="button">
          {running ? "分析进行中…" : analysisMode === "manual" && !selectedImages.length
            ? "请先在上方选图" : "开始精细视觉分析（付费）"}
        </button>
      </div>
      <p className="detailed-cost-note">任务会产生 Azure OpenAI 费用；同一条件的运行中或已完成任务会直接复用，不重复计费。</p>
      {job ? <div className={`detailed-job-status ${job.status}`}>
        <strong>{stageLabels[job.stage] || job.stage}</strong>
        <span>{job.progress || 0}%</span>
        <div><i style={{ width: `${job.progress || 0}%` }} /></div>
        {job.error ? <p>{job.error}</p> : null}
      </div> : null}
      {job?.status === "complete" ? <CompletedAnalysis job={job} /> : null}
    </section>
  );
}
