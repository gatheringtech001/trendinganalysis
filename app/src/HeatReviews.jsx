import React, { useEffect, useMemo, useState } from "react";
import { api, formatNumber, formatPrice, stores } from "./api";
import { formatCategory } from "./imageAnalysis";
import ProductImage from "./Media";

const statusText = {
  not_public: "未公开",
  not_available: "无公开字段",
  unknown_window: "有数据 · 周期未知",
};

function Headline({ data }) {
  const cards = [
    ["真实销量覆盖", `${data.headline.stores_with_actual_sales}/${data.coverage.length}`, "四个品牌均未披露销售件数"],
    ["估算销量代理", formatNumber(data.headline.products_with_estimated_sales), "仅 Aloruh(shein) 公开 Estimated sold"],
    ["商品浏览记录", formatNumber(data.headline.products_with_views), "仅 PLT；原始商品/颜色记录"],
    ["评论记录", formatNumber(data.headline.review_records), "商品级与品牌级合计"],
  ];
  return (
    <section className="engagement-headline" aria-label="热度数据概览">
      {cards.map(([label, value, note]) => (
        <article key={label}><span>{label}</span><strong>{value}</strong><small>{note}</small></article>
      ))}
    </section>
  );
}

function Coverage({ rows }) {
  return (
    <section className="engagement-section">
      <div className="section-heading"><h2>五个数据源覆盖</h2><span>真实指标与代理指标分开展示</span></div>
      <div className="coverage-grid">
        {rows.map((row) => (
          <article className="coverage-card" key={row.store_id}>
            <h3>{stores[row.store_id]}</h3>
            <dl>
              <div><dt>真实销量</dt><dd className="missing">{statusText[row.actual_sales_status]}</dd></div>
              <div><dt>估算销量代理</dt><dd>{formatNumber(row.products_with_estimated_sales)}</dd></div>
              <div><dt>浏览量</dt><dd>{formatNumber(row.products_with_views)} 条</dd></div>
              <div><dt>浏览商品族</dt><dd>{formatNumber(row.unique_products_with_views)}</dd></div>
              <div><dt>浏览中位数</dt><dd>{row.median_views == null ? "—" : formatNumber(row.median_views)}</dd></div>
              <div><dt>Top Seller</dt><dd>{formatNumber(row.top_seller_products)}</dd></div>
              <div><dt>Bestseller榜单</dt><dd>{formatNumber(row.bestseller_products)}</dd></div>
              <div><dt>评论</dt><dd>{formatNumber(row.review_records)}</dd></div>
            </dl>
            <p>浏览量：{statusText[row.views_period]} · 评论层级：{row.review_scope === "product" ? "商品级" : row.review_scope === "brand" ? "品牌级" : "无公开记录"}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function SalesProxyLeaders({ rows }) {
  return (
    <section className="engagement-section">
      <div className="section-heading"><h2>Aloruh(shein) 估算销量代理</h2><span>SHEIN SG Estimated sold · 非真实订单量</span></div>
      {rows.length ? <div className="review-product-grid">
        {rows.map((row) => (
          <a href={row.source_url} key={`${row.store_id}-${row.product_id}`} target="_blank" rel="noreferrer">
            <ProductImage src={row.primary_image_url} alt={row.title} />
            <div><h3>{row.title}</h3><p>{row.market} · {formatCategory(row.category)} · {formatPrice(row.price_usd)}</p>
              <strong>{row.estimated_sold_label}</strong><span>{row.bestseller_rank ? `榜单 #${row.bestseller_rank}` : "Estimated"}</span></div>
          </a>
        ))}
      </div> : <div className="empty-results">当前店铺没有公开 Estimated sold 字段</div>}
    </section>
  );
}

function ViewLeaders({ rows }) {
  const maximum = useMemo(() => Math.max(...rows.map((row) => row.product_detail_views), 1), [rows]);
  return (
    <section className="engagement-section">
      <div className="section-heading"><h2>PLT 商品浏览热度</h2><span>按商品族去重 · 统计周期未知</span></div>
      {rows.length ? (
        <div className="heat-list">
          {rows.map((row, index) => (
            <a className="heat-row" href={row.source_url} key={`${row.store_id}-${row.product_id}`} target="_blank" rel="noreferrer">
              <span className="heat-rank">{String(index + 1).padStart(2, "0")}</span>
              <ProductImage src={row.primary_image_url} alt={row.title} />
              <div className="heat-product">
                <h3>{row.title}</h3><p>{formatCategory(row.category)} · {formatPrice(row.price_usd)}</p>
                <i style={{ width: `${(row.product_detail_views / maximum) * 100}%` }} />
              </div>
              <div className="heat-value"><strong>{formatNumber(row.product_detail_views)}</strong><span>浏览代理</span></div>
              {row.top_seller ? <b>Top Seller</b> : null}
            </a>
          ))}
        </div>
      ) : <div className="empty-results">当前店铺没有公开商品浏览字段</div>}
    </section>
  );
}

function ReviewLeaders({ rows }) {
  return (
    <section className="engagement-section">
      <div className="section-heading"><h2>商品评论热度</h2><span>仅展示可关联 SKU 的评论</span></div>
      {rows.length ? <div className="review-product-grid">
        {rows.map((row) => (
          <a href={row.source_url} key={`${row.store_id}-${row.product_id}`} target="_blank" rel="noreferrer">
            <ProductImage src={row.primary_image_url} alt={row.title} />
            <div><h3>{row.title}</h3><p>{stores[row.store_id]} · {formatCategory(row.category)}</p>
              <strong>{formatNumber(row.review_count)} 条</strong><span>★ {row.average_rating ?? "—"}</span></div>
          </a>
        ))}
      </div> : <div className="empty-results">当前店铺没有可关联 SKU 的商品评论</div>}
    </section>
  );
}

function ReviewSamples({ rows }) {
  return (
    <section className="engagement-section">
      <div className="section-heading"><h2>近期评论样本</h2><span>品牌级评论不会归因到具体商品</span></div>
      <div className="review-samples">
        {rows.map((row) => (
          <a href={row.source_url} key={`${row.store_id}-${row.review_id}`} target="_blank" rel="noreferrer">
            <div><strong>{stores[row.store_id]}</strong><span>{row.review_scope === "product" ? "商品级" : "品牌级"}</span></div>
            <h3>{row.product_title || row.title || "公开评论片段"}</h3>
            <p>{row.content}</p><small>{row.rating ? `★ ${row.rating} · ` : ""}{row.created_at?.slice(0, 10)}</small>
          </a>
        ))}
      </div>
    </section>
  );
}

function Analysis({ items }) {
  return (
    <section className="analysis-panel">
      <div className="section-heading"><h2>整体分析</h2><span>基于当前外部快照</span></div>
      <div className="analysis-grid">
        {items.map((item, index) => (
          <article key={item.title}><span>0{index + 1}</span><div><h3>{item.title}</h3><p>{item.finding}</p></div><b>{item.confidence}</b></article>
        ))}
      </div>
      <p className="analysis-caveat">结论边界：浏览量周期未知，评论覆盖不对称，任何销量或转化判断仍需店铺内部订单与流量数据验证。</p>
    </section>
  );
}

export default function HeatReviews({ store }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    setData(null); setError("");
    api.engagement(store).then(setData).catch((reason) => setError(reason.message));
  }, [store]);
  if (error) return <div className="error-banner">{error}</div>;
  if (!data) return <div className="loading">正在载入热度与评论数据…</div>;
  return <div className="engagement-view">
    <Headline data={data} />
    <Coverage rows={data.coverage} />
    <SalesProxyLeaders rows={data.sales_proxy_leaders} />
    <ViewLeaders rows={data.view_leaders} />
    <ReviewLeaders rows={data.review_leaders} />
    <ReviewSamples rows={data.review_samples} />
    <Analysis items={data.overall_analysis} />
    <footer className="data-status">真实销量：未公开；估算销量代理：Aloruh(shein) SHEIN SG Estimated sold；浏览量：PLT 官方索引；评论：官网及公开品牌片段。</footer>
  </div>;
}
