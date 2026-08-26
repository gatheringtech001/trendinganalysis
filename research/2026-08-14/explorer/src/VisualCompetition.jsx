import React from "react";
import { formatPrice, storeColors, stores } from "./api";


const percent = (value) => `${Math.round(Number(value || 0) * 100)}%`;

function MetricBar({ label, value, display = percent }) {
  const width = Math.min(Math.max(Number(value || 0) * 100, 2), 100);
  return (
    <div className="visual-metric">
      <p><span>{label}</span><b>{display(value)}</b></p>
      <i><em style={{ width: `${width}%` }} /></i>
    </div>
  );
}

function VisualSamples({ samples }) {
  return (
    <div className="visual-samples">
      {samples.map((item) => (
        <a href={item.source_url} target="_blank" rel="noreferrer" key={item.product_id}>
          <img src={item.image_url} alt={item.title} loading="lazy" />
          <span>{item.title}</span>
        </a>
      ))}
    </div>
  );
}

export function VisualAnalysis({ visual, storeName }) {
  const metrics = visual.metrics;
  return (
    <section className="profile-section visual-analysis">
      <div className="section-heading">
        <h2>视觉系统分析</h2>
        <span>{visual.valid_images} 张有效主图 · {visual.confidence} 置信度</span>
      </div>
      <div className="visual-summary-grid">
        <article className="visual-quant-card">
          <div className="analysis-card-heading"><span>COMPUTED FEATURES</span><h3>可复算图像特征</h3></div>
          {visual.valid_images ? <>
            <MetricBar label="平均亮度" value={metrics.brightness} />
            <MetricBar label="平均饱和度" value={metrics.saturation} />
            <MetricBar label="中性浅背景" value={metrics.neutral_border_rate} />
            <MetricBar label="画面细节密度" value={metrics.edge_density} />
            <div className="visual-palette">
              {visual.palette.map((item) => <span key={item.label}>{item.label}<b>{item.count}</b></span>)}
            </div>
          </> : <p>暂无独立下载视觉样本，不把其他来源的图像特征外推到该店铺。</p>}
        </article>
        <article className="visual-review-card">
          <div className="analysis-card-heading"><span>CONTACT SHEET REVIEW</span><h3>人工复核视觉语言</h3></div>
          <dl>{Object.entries(visual.manual_review).map(([label, body]) => (
            <div key={label}><dt>{label}</dt><dd>{body}</dd></div>
          ))}</dl>
        </article>
      </div>
      <VisualSamples samples={visual.samples} />
      <p className="visual-method">
        {storeName}：{visual.method} 当前下载 {visual.sample_size} 张，排除 {visual.excluded_images} 张占位或不可用图；不外推至全量图片索引。
      </p>
    </section>
  );
}

export function VisualComparison({ rows }) {
  return (
    <section className="profile-section">
      <div className="section-heading"><h2>两店视觉差异</h2><span>同一算法 · 接触表人工复核</span></div>
      <div className="visual-comparison-grid">
        {rows.map((row) => (
          <article key={row.store_id} style={{ "--store-color": storeColors[row.store_id] }}>
            <div className="visual-store-heading"><i /><div><h3>{row.store_name}</h3><span>{row.valid_images}/{row.sample_size} 张 · {row.confidence}</span></div></div>
            {row.valid_images ? <>
              <div className="visual-store-metrics">
                <span><b>{percent(row.brightness)}</b>亮度</span>
                <span><b>{percent(row.saturation)}</b>饱和度</span>
                <span><b>{percent(row.neutral_border_rate)}</b>中性浅背景</span>
                <span><b>{percent(row.edge_density)}</b>细节密度</span>
              </div>
              <p><b>场景</b>{row.scene}</p>
              <p><b>构图</b>{row.composition}</p>
              <p><b>视觉语言</b>{row.visual_language}</p>
            </> : <p><b>证据缺口</b>{row.visual_language}</p>}
          </article>
        ))}
      </div>
      <p className="visual-method">量化指标来自五个数据源当前 91 张下载主图，其中 1 张官方占位图已排除；Aloruh(shein) 尚无独立下载样本，本视图不把 Aloruh(local) 的视觉特征外推给它。</p>
    </section>
  );
}

function ProductSide({ product }) {
  return (
    <a className="sku-side" href={product.source_url} target="_blank" rel="noreferrer">
      <img src={product.image_url} alt={product.title} loading="lazy" />
      <div>
        <span>{product.store_name}</span>
        <h3>{product.title}</h3>
        <strong>{formatPrice(product.price_usd)}</strong>
        <small>{product.heat_proxy}</small>
      </div>
    </a>
  );
}

function MatchCard({ match, firstStore }) {
  const selectedIsLeft = match.left.store_id === firstStore;
  const left = selectedIsLeft ? match.left : match.right;
  const right = selectedIsLeft ? match.right : match.left;
  return (
    <article className="sku-match-card">
      <div className="sku-match-score"><strong>{match.score}</strong><span>候选匹配分</span></div>
      <div className="sku-pair"><ProductSide product={left} /><span className="sku-versus">VS</span><ProductSide product={right} /></div>
      <div className="sku-reasons">{match.reasons.map((reason) => <span key={reason}>{reason}</span>)}</div>
    </article>
  );
}

export function SkuCandidates({ matches, method, pairStoreIds }) {
  const [firstStore, secondStore] = pairStoreIds;
  const filtered = matches.filter((match) => {
    const matchStores = new Set([match.left.store_id, match.right.store_id]);
    return matchStores.has(firstStore) && matchStores.has(secondStore);
  }).slice(0, 8);
  return (
    <section className="profile-section sku-candidates">
      <div className="section-heading"><h2>潜在竞品 SKU</h2><span>候选发现，不是销量竞争结论</span></div>
      <div className="sku-toolbar">
        <p>{stores[firstStore]} ↔ {stores[secondStore]} · 当前显示 {filtered.length} 组</p>
      </div>
      {filtered.length ? (
        <div className="sku-match-list">{filtered.map((match) => (
          <MatchCard match={match} firstStore={firstStore} key={`${match.left.store_id}-${match.left.product_id}-${match.right.store_id}-${match.right.product_id}`} />
        ))}</div>
      ) : <p className="sku-empty">当前两店没有满足同品类条件的候选 SKU。</p>}
      <div className="sku-method"><b>匹配方法</b><p>{method.definition}</p><p>{method.scope}</p><small>{method.boundary}</small></div>
    </section>
  );
}
