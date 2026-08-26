import React, { useEffect, useState } from "react";
import { api, formatNumber, formatPrice, storeColors, stores } from "./api";
import { formatCategory } from "./imageAnalysis";
import { SkuCandidates, VisualAnalysis, VisualComparison } from "./VisualCompetition";

const evidenceLabels = {
  catalog: "商品与价格",
  audience: "目标客群",
  visual: "视觉系统",
  trend: "趋势判断",
};

const observationLabels = {
  fact: "官方事实",
  proxy: "代理指标",
  gap: "证据缺口",
};

const reviewScopeLabels = {
  product: "商品级",
  brand: "品牌级",
  unavailable: "缺失",
};

const percent = (value) => `${Math.round(Number(value || 0) * 100)}%`;

const storeOptions = Object.entries(stores).filter(([storeId]) => storeId);

function signedDifference(value, unit = "") {
  const rounded = Math.round(Number(value || 0) * 100) / 100;
  return `${rounded > 0 ? "+" : ""}${rounded}${unit}`;
}

function buildPairInsights(rows, visualRows) {
  const [left, right] = rows;
  const [leftVisual, rightVisual] = visualRows;
  if (!left || !right) return [];

  const priceGap = Number(right.median_price || 0) - Number(left.median_price || 0);
  const saleGap = (Number(right.sale_rate || 0) - Number(left.sale_rate || 0)) * 100;
  const insights = [
    {
      confidence: "High",
      title: "价格中位数差异",
      finding: priceGap === 0
        ? `两店价格中位数相同，均为 ${formatPrice(left.median_price)}。`
        : `${right.store_name} 相对 ${left.store_name} 为 ${signedDifference(priceGap, " 美元")}；这是公开目录价格差，不代表成交价。`,
    },
    {
      confidence: "High",
      title: "促销覆盖差异",
      finding: saleGap === 0
        ? `两店促销覆盖相同，均为 ${percent(left.sale_rate)}。`
        : `${right.store_name} 相对 ${left.store_name} 为 ${signedDifference(saleGap, " 个百分点")}；只反映当前快照中的促销 SKU 占比。`,
    },
  ];
  const hasVisualPair = leftVisual && rightVisual
    && Number(leftVisual.valid_images) > 0 && Number(rightVisual.valid_images) > 0;
  if (!hasVisualPair) {
    insights.push({
      confidence: "Low",
      title: "主图视觉样本缺口",
      finding: "至少一家店没有独立有效主图样本，因此不计算亮度、饱和度或背景差异；价格、促销与候选 SKU 比较不受影响。",
    });
    return insights;
  }
  const brightnessGap = (Number(rightVisual.brightness) - Number(leftVisual.brightness)) * 100;
  const neutralGap = (Number(rightVisual.neutral_border_rate) - Number(leftVisual.neutral_border_rate)) * 100;
  insights.push({
      confidence: "Medium",
      title: "主图视觉差异",
      finding: `${right.store_name} 相对 ${left.store_name} 的平均亮度为 ${signedDifference(brightnessGap, " 个百分点")}，中性浅背景占比为 ${signedDifference(neutralGap, " 个百分点")}；仅覆盖已下载并通过校验的主图样本。`,
  });
  return insights;
}

function useAnalysis(store = "") {
  const [state, setState] = useState({ data: null, error: "" });
  useEffect(() => {
    let active = true;
    setState({ data: null, error: "" });
    api.analysis(store)
      .then((data) => active && setState({ data, error: "" }))
      .catch((error) => active && setState({ data: null, error: error.message }));
    return () => { active = false; };
  }, [store]);
  return state;
}

function AnalysisState({ error }) {
  return <div className={error ? "error-banner" : "loading"}>{error || "正在生成分析视图…"}</div>;
}

function ProfileMetrics({ metrics }) {
  const items = [
    [formatNumber(metrics.products), "商品SKU"],
    [formatPrice(metrics.median_price), "价格中位数"],
    [percent(metrics.sale_rate), "促销覆盖"],
    [percent(metrics.availability_rate), "当前在售"],
    [metrics.images_per_product, "平均图片/款"],
  ];
  if (metrics.products_with_estimated_sales) {
    items.push([formatNumber(metrics.products_with_estimated_sales), "Estimated sold代理"]);
  }
  return (
    <section className="profile-metrics" aria-label="店铺核心指标">
      {items.map(([value, label]) => <article key={label}><strong>{value}</strong><span>{label}</span></article>)}
    </section>
  );
}

function CategoryFocus({ categories }) {
  const max = Math.max(...categories.map((item) => item.products), 1);
  return (
    <section className="analysis-card category-focus">
      <div className="analysis-card-heading"><span>PRODUCT MIX</span><h3>品类结构</h3></div>
      <div className="focus-bars">
        {categories.map((item) => (
          <div key={item.category}>
            <p><b>{formatCategory(item.category)}</b><span>{formatNumber(item.products)} · {percent(item.share)}</span></p>
            <i><em style={{ width: `${(item.products / max) * 100}%` }} /></i>
          </div>
        ))}
      </div>
      <small>官方目录横截面；品类占比不代表销售贡献。</small>
    </section>
  );
}

function AudienceEvidence({ profile }) {
  const { metrics, review_themes: themes } = profile;
  return (
    <section className="analysis-card audience-card">
      <div className="analysis-card-heading"><span>AUDIENCE EVIDENCE</span><h3>客群与画像证据</h3></div>
      <div className="audience-counts">
        <div><strong>{formatNumber(metrics.review_records)}</strong><span>{reviewScopeLabels[metrics.review_scope]}评论</span></div>
        <div><strong>{formatNumber(metrics.ugc_records)}</strong><span>UGC候选</span></div>
      </div>
      <div className="theme-list">
        {themes.length ? themes.map((item) => (
          <span key={item.theme}>{item.label}<b>{item.count}</b></span>
        )) : <p>暂无可聚合的评论主题。</p>}
      </div>
      <small>这些主题用于发现问题与场景，不能据此推断年龄、收入或购买人群。</small>
    </section>
  );
}

function EvidenceMatrix({ evidence }) {
  return (
    <section className="evidence-matrix">
      {Object.entries(evidence).map(([key, item]) => (
        <article key={key}>
          <div><span>{evidenceLabels[key]}</span><b className={`confidence ${item.confidence.toLowerCase().replace("-", "")}`}>{item.confidence}</b></div>
          <p>{item.note}</p>
        </article>
      ))}
    </section>
  );
}

function ObservationGrid({ observations }) {
  return (
    <section className="profile-section">
      <div className="section-heading"><h2>店铺剖析结论</h2><span>事实、代理与缺口分开呈现</span></div>
      <div className="observation-grid">
        {observations.map((item) => (
          <article className={item.kind} key={item.kind}>
            <span>{observationLabels[item.kind]}</span><h3>{item.title}</h3><p>{item.body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function Hypotheses({ items }) {
  return (
    <section className="profile-section">
      <div className="section-heading"><h2>优化假设</h2><span>均需内部销售或转化数据验证</span></div>
      <div className="hypothesis-list">
        {items.map((item, index) => (
          <article key={item.title}>
            <span>0{index + 1}</span>
            <div><h3>{item.title}</h3><p>{item.evidence}</p><small>验证条件：{item.validation}</small></div>
            <div><b>{item.confidence}</b><p>{item.expected_impact}</p></div>
          </article>
        ))}
      </div>
    </section>
  );
}

export function StoreAnalysisView({ store }) {
  const { data, error } = useAnalysis(store);
  if (!data) return <AnalysisState error={error} />;
  const profile = data.stores[0];
  return (
    <div className="profile-view">
      <section className="profile-hero">
        <div><span>STORE DIAGNOSIS · {data.snapshot}</span><h2>{profile.store_name}</h2><p>{profile.method}</p><p>市场口径：{profile.markets.map((item) => `${item.market} / ${item.channel}（${formatNumber(item.products)}）`).join("；")}</p></div>
        <div className="profile-boundary"><b>分析边界</b><p>基于外部公开快照；真实经营表现仍需内部数据验证。</p></div>
      </section>
      <ProfileMetrics metrics={profile.metrics} />
      <div className="profile-two-column">
        <CategoryFocus categories={profile.categories} />
        <AudienceEvidence profile={profile} />
      </div>
      <VisualAnalysis visual={profile.visual} storeName={profile.store_name} />
      <EvidenceMatrix evidence={profile.evidence} />
      <ObservationGrid observations={profile.observations} />
      <Hypotheses items={profile.hypotheses} />
    </div>
  );
}

function ComparisonBars({ rows, field, format, title, note }) {
  const max = Math.max(...rows.map((row) => Number(row[field] || 0)), 1);
  return (
    <section className="comparison-chart">
      <div className="analysis-card-heading"><span>COMPARABLE METRIC</span><h3>{title}</h3></div>
      {rows.map((row) => (
        <div className="comparison-bar" key={row.store_id}>
          <span>{row.store_name}</span>
          <i><em style={{ background: storeColors[row.store_id], width: `${(Number(row[field] || 0) / max) * 100}%` }} /></i>
          <b>{format(row[field])}</b>
        </div>
      ))}
      <small>{note}</small>
    </section>
  );
}

function ComparisonTable({ rows }) {
  return (
    <section className="comparison-table-wrap">
      <table className="comparison-table">
        <thead><tr><th>店铺</th><th>市场口径</th><th>SKU</th><th>核心品类</th><th>中位价</th><th>促销</th><th>在售</th><th>图片/款</th><th>评论口径</th><th>客群证据</th><th>趋势证据</th></tr></thead>
        <tbody>{rows.map((row) => (
          <tr key={row.store_id}>
            <td><i style={{ background: storeColors[row.store_id] }} /><strong>{row.store_name}</strong></td>
            <td>{row.market_scope}</td>
            <td>{formatNumber(row.products)}</td>
            <td>{formatCategory(row.top_category)} <small>{percent(row.top_category_share)}</small></td>
            <td>{formatPrice(row.median_price)}</td><td>{percent(row.sale_rate)}</td><td>{percent(row.availability_rate)}</td>
            <td>{row.images_per_product}</td><td>{reviewScopeLabels[row.review_scope]}</td>
            <td>{row.audience_confidence}</td><td>{row.trend_confidence}</td>
          </tr>
        ))}</tbody>
      </table>
    </section>
  );
}

export function CompetitorAnalysisView() {
  const { data, error } = useAnalysis();
  const [leftStore, setLeftStore] = useState("princess_polly");
  const [rightStore, setRightStore] = useState("motel");
  if (!data) return <AnalysisState error={error} />;
  const { rows, caveats, visual_rows: visualRows, sku_matches: skuMatches, sku_method: skuMethod } = data.comparison;
  const pairStoreIds = [leftStore, rightStore];
  const pairRows = pairStoreIds.map((storeId) => rows.find((row) => row.store_id === storeId)).filter(Boolean);
  const pairVisualRows = pairStoreIds.map((storeId) => visualRows.find((row) => row.store_id === storeId)).filter(Boolean);
  const pairInsights = buildPairInsights(pairRows, pairVisualRows);
  return (
    <div className="comparison-view">
      <section className="comparison-hero">
        <span>COMPETITOR LANDSCAPE · {data.snapshot}</span>
        <h2>两店外部横截面对比</h2>
        <p>比较可核对的商品结构、价格、促销、图片密度与证据覆盖；不做虚假销量排名。</p>
        <div className="pair-selector" aria-label="选择两家店铺进行比较">
          <label>
            <span>店铺 A</span>
            <select value={leftStore} onChange={(event) => setLeftStore(event.target.value)}>
              {storeOptions.filter(([storeId]) => storeId !== rightStore).map(([storeId, storeName]) => (
                <option value={storeId} key={storeId}>{storeName}</option>
              ))}
            </select>
          </label>
          <b aria-hidden="true">↔</b>
          <label>
            <span>店铺 B</span>
            <select value={rightStore} onChange={(event) => setRightStore(event.target.value)}>
              {storeOptions.filter(([storeId]) => storeId !== leftStore).map(([storeId, storeName]) => (
                <option value={storeId} key={storeId}>{storeName}</option>
              ))}
            </select>
          </label>
        </div>
      </section>
      <div className="comparison-charts">
        <ComparisonBars rows={pairRows} field="median_price" format={formatPrice} title="价格中位数" note="仅统计公开且大于 0 美元的 SKU 价格。" />
        <ComparisonBars rows={pairRows} field="images_per_product" format={(value) => `${value}张`} title="平均图片密度" note="衡量素材覆盖，不评价构图或视觉质量。" />
      </div>
      <VisualComparison rows={pairVisualRows} />
      <SkuCandidates matches={skuMatches} method={skuMethod} pairStoreIds={pairStoreIds} />
      <section className="profile-section">
        <div className="section-heading"><h2>两店可比指标</h2><span>同一快照 · 口径差异已标注</span></div>
        <ComparisonTable rows={pairRows} />
      </section>
      <section className="comparison-insights">
        {pairInsights.map((item) => <article key={item.title}><span>{item.confidence}</span><h3>{item.title}</h3><p>{item.finding}</p></article>)}
      </section>
      <section className="comparison-caveats">
        <div><span>READ BEFORE USE</span><h2>比较限制</h2></div>
        <ul>{caveats.map((item) => <li key={item}>{item}</li>)}</ul>
      </section>
    </div>
  );
}
