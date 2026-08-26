import React, { useDeferredValue, useEffect, useMemo, useState } from "react";
import { api, formatNumber, formatPrice, stores } from "./api";
import Icon from "./icons";
import { dimensionLabels, dimensions, formatAnalysisTag, formatCategory, formatConfidence } from "./imageAnalysis";
import ProductImage from "./Media";

const categoryMethodNames = {
  azure_ai_vision_tags: "Azure AI Vision标签归类",
  azure_openai_visual: "Azure OpenAI视觉归类",
  manual_visual_review: "人工视觉复核",
  official_shein_category_id: "SHEIN官方类目",
};

const channelNames = {
  official_site: "品牌官网",
  customer_dataset: "客户数据",
  shein_sg: "SHEIN SG",
};

const storeDescriptions = {
  aloruh_shein: "Aloruh SHEIN SG 官方目录与商品详情图片",
  aloruh_local: "Aloruh 自有站与客户本地上传数据",
};

function Filters({ category, categories, mode, query, available, sort, onChange }) {
  return (
    <div className="filter-bar">
      <label>
        <span className="sr-only">全部分类</span>
        <select value={category} onChange={(event) => onChange("category", event.target.value)}>
          <option value="">全部分类</option>
          {categories.map((item) => (
            <option key={item.category} value={item.category}>{formatCategory(item.category)}</option>
          ))}
        </select>
      </label>
      <label className="search-control">
        <Icon name="search" size={17} />
        <input
          placeholder="搜索商品名或SKU"
          value={query}
          onChange={(event) => onChange("query", event.target.value)}
        />
      </label>
      <label className="toggle-control">
        <input type="checkbox" checked={available} onChange={(event) => onChange("available", event.target.checked)} />
        <span />仅看在售
      </label>
      {mode === "products" && (
        <select value={sort} onChange={(event) => onChange("sort", event.target.value)} aria-label="排序方式">
          <option value="rank">默认顺序</option>
          <option value="images">图片数量</option>
          <option value="views">浏览量</option>
          <option value="reviews">评论量</option>
          <option value="price_asc">价格从低到高</option>
          <option value="price_desc">价格从高到低</option>
        </select>
      )}
    </div>
  );
}

function CategoryRail({ categories, mode, selected, onSelect }) {
  const countKey = mode === "images" ? "images" : "products";
  return (
    <aside className="category-rail">
      <h2>{mode === "images" ? "图片分类" : "SKU分类"}</h2>
      <button className={!selected ? "selected" : ""} onClick={() => onSelect("")}>
        <span>全部分类</span><strong>{formatNumber(categories.reduce((sum, row) => sum + row[countKey], 0))}</strong>
      </button>
      {categories.slice(0, 12).map((item) => (
        <button className={selected === item.category ? "selected" : ""} key={item.category} onClick={() => onSelect(item.category)}>
          <span>{formatCategory(item.category)}</span><strong>{formatNumber(item[countKey])}</strong>
        </button>
      ))}
    </aside>
  );
}

function ProductCard({ item, mode, selected, onSelect }) {
  const image = mode === "images" ? item.image_url : item.primary_image_url;
  const activity = item.estimated_sold_label
    ? `估算销量 ${item.estimated_sold_label}`
    : item.product_detail_views != null
      ? `${formatNumber(item.product_detail_views)}浏览`
      : item.review_count
        ? `${item.review_count}评论`
        : `${item.image_count}张图片`;
  return (
    <button className={selected ? "gallery-card selected" : "gallery-card"} onClick={() => onSelect(item)}>
      <ProductImage src={image} alt={item.title} />
      <div>
        <h3>{item.title}</h3>
        <p>{stores[item.store_id]} · {item.market || "US"} · {formatCategory(item.category)}</p>
        {mode === "images" && item.analysis ? (
          <small className="card-analysis-badge">
            {item.analysis.analysis_version === "fashion-image-v2" ? 15 : 12}维已分析 · {formatAnalysisTag(item.analysis.tags.product_category?.[0])}
          </small>
        ) : null}
        <strong>{formatPrice(item.price_usd)}</strong>
        <span>{mode === "images" ? `第${item.position}张` : activity}</span>
      </div>
    </button>
  );
}

export function ImageAnalysisPanel({ analysis }) {
  if (!analysis) return <p className="image-analysis-empty">当前图片尚无多维分析。</p>;
  return (
    <section className="image-analysis-panel">
      <div className="image-analysis-heading">
        <div><span>12 DIMENSIONS</span><h4>图片维度分析</h4></div>
        <strong>{analysis.analysis_status === "complete" ? "完整" : "部分"}</strong>
      </div>
      <div className="image-analysis-grid">
        {dimensions.map((dimension) => (
          <article key={dimension}>
            <header><h5>{dimensionLabels[dimension]}</h5><span>{formatConfidence(analysis.confidence?.[dimension])}</span></header>
            <ul>{(analysis.tags?.[dimension] || []).map((tag) => <li key={tag}>{formatAnalysisTag(tag)}</li>)}</ul>
          </article>
        ))}
      </div>
    </section>
  );
}

export function DetailDrawer({ detail, onClose }) {
  const [activeImage, setActiveImage] = useState(0);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    const selected = detail?.images?.findIndex((item) => item.position === detail.selected_position);
    setActiveImage(selected >= 0 ? selected : 0);
    setCopied(false);
  }, [detail?.product_id, detail?.selected_position]);
  if (!detail) return <aside className="detail-drawer empty">选择商品后查看全部图片</aside>;
  const image = detail.images[activeImage]?.source_url || detail.primary_image_url;
  const imageAnalysis = detail.images[activeImage]?.analysis;
  const isCustomerDataset = detail.source_type === "customer_dataset";
  const categoryMethod = isCustomerDataset
    ? `${categoryMethodNames[detail.category_method] || "视觉自动归类"} · ${Math.round(Number(detail.category_confidence || 0) * 100)}%置信度`
    : "官网目录分类";
  const copy = async () => {
    await navigator.clipboard.writeText(image);
    setCopied(true);
  };
  return (
    <aside className="detail-drawer">
      <div className="drawer-heading"><h2>商品详情</h2><button onClick={onClose} aria-label="关闭详情">×</button></div>
      <ProductImage className="detail-image" src={image} alt={detail.title} />
      <h3>{detail.title}</h3>
      <p>{stores[detail.store_id]}</p>
      <dl>
        <div><dt>SKU</dt><dd>{detail.product_id}</dd></div>
        <div><dt>市场 / 渠道</dt><dd>{detail.market || "US"} · {channelNames[detail.channel] || detail.channel}</dd></div>
        <div><dt>分类</dt><dd>{formatCategory(detail.category)}</dd></div>
        <div><dt>分类方式</dt><dd>{categoryMethod}</dd></div>
        <div><dt>价格</dt><dd>{formatPrice(detail.price_usd)}</dd></div>
        <div><dt>状态</dt><dd>{isCustomerDataset ? "客户数据集记录" : detail.available ? "在售" : "售罄"}</dd></div>
        <div><dt>真实销量</dt><dd>未公开</dd></div>
        <div><dt>销量代理</dt><dd>{detail.estimated_sold_label ? `${detail.estimated_sold_label}（SHEIN Estimated）` : "无公开字段"}</dd></div>
        <div><dt>浏览量</dt><dd>{detail.product_detail_views == null ? "无公开字段" : `${formatNumber(detail.product_detail_views)}（周期未知）`}</dd></div>
        <div><dt>榜单代理</dt><dd>{detail.bestseller_rank ? `Bestseller #${detail.bestseller_rank}` : detail.top_seller ? "Top Seller" : `目录排名 ${detail.catalog_rank || "—"}`}</dd></div>
        <div><dt>评论</dt><dd>{detail.review_summary.count ? `${detail.review_summary.count}条 · ★ ${detail.review_summary.average_rating}` : "无商品级评论"}</dd></div>
      </dl>
      <ImageAnalysisPanel analysis={imageAnalysis} />
      {detail.reviews?.length ? <div className="drawer-reviews">
        <h4>评论样本</h4>
        {detail.reviews.slice(0, 3).map((review) => <article key={review.review_id}><strong>★ {review.rating || "—"}</strong><p>{review.content}</p></article>)}
      </div> : null}
      <div className="thumbnail-strip">
        {detail.images.slice(0, 8).map((item, index) => (
          <button className={activeImage === index ? "active" : ""} key={item.position} onClick={() => setActiveImage(index)}>
            <ProductImage src={item.source_url} alt={`${detail.title} ${item.position}`} />
          </button>
        ))}
      </div>
      <div className="drawer-actions">
        <a href={detail.source_url} target="_blank" rel="noreferrer">{isCustomerDataset ? "打开源图" : "打开官网"}</a>
        <button onClick={copy}>{copied ? "已复制" : "复制图片链接"}</button>
      </div>
      <small>图片URL哈希：{detail.images[activeImage]?.url_sha256 || "—"}</small>
    </aside>
  );
}

export default function Explorer({ mode, store }) {
  const [categories, setCategories] = useState([]);
  const [filters, setFilters] = useState({ category: "", query: "", available: false, sort: "rank" });
  const [page, setPage] = useState(1);
  const [result, setResult] = useState({ items: [], total: 0, page_size: 24 });
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const pageSize = mode === "images" ? 24 : 18;
  const deferredQuery = useDeferredValue(filters.query);

  useEffect(() => { api.categories(store).then((data) => setCategories(data.items)); }, [store]);
  useEffect(() => { setFilters((current) => ({ ...current, category: "" })); setPage(1); }, [store, mode]);
  useEffect(() => {
    let active = true;
    setLoading(true);
    const method = mode === "images" ? api.images : api.products;
    method({ store, category: filters.category, q: deferredQuery, available: filters.available ? 1 : "", sort: filters.sort, page, page_size: pageSize })
      .then(async (data) => {
        if (!active) return;
        setResult(data);
        setLoading(false);
        const first = data.items[0];
        const wideScreen = window.matchMedia("(min-width: 1181px)").matches;
        const loaded = first && wideScreen ? await api.product(first.store_id, first.product_id) : null;
        const nextDetail = loaded ? { ...loaded, selected_position: first.position || 1 } : null;
        if (active) setDetail(nextDetail);
      })
      .catch(() => active && setLoading(false));
    return () => { active = false; };
  }, [mode, store, filters.category, filters.available, filters.sort, deferredQuery, page]);

  const select = async (item) => {
    const selected = await api.product(item.store_id, item.product_id);
    setDetail({ ...selected, selected_position: item.position || 1 });
  };
  const updateFilter = (key, value) => { setFilters((current) => ({ ...current, [key]: value })); setPage(1); };
  const pages = useMemo(() => Math.max(1, Math.ceil(result.total / pageSize)), [result.total, pageSize]);

  return (
    <>
      <div className="explorer-subtitle">
        <p>{storeDescriptions[store] || (mode === "images" ? "官网目录与商品图片索引" : "官网目录商品记录")}</p>
        <strong>{formatNumber(result.total)}条结果</strong>
      </div>
      <Filters {...filters} categories={categories} mode={mode} onChange={updateFilter} />
      <div className="explorer-layout">
        <CategoryRail categories={categories} mode={mode} selected={filters.category} onSelect={(value) => updateFilter("category", value)} />
        <section className="gallery-area">
          <div className="gallery-heading">
            <span>{loading ? "正在查询…" : `${formatNumber(result.total)}个${mode === "images" ? "图片" : "商品"}`}</span>
            <div><Icon name="grid" size={17} /><Icon name="list" size={17} /></div>
          </div>
          <div className="product-gallery">
            {result.items.map((item) => (
              <ProductCard
                item={item}
                key={`${item.store_id}-${item.product_id}-${item.position || 0}`}
                mode={mode}
                selected={detail?.store_id === item.store_id
                  && detail?.product_id === item.product_id
                  && (mode !== "images" || detail?.selected_position === item.position)}
                onSelect={select}
              />
            ))}
          </div>
          {!loading && result.items.length === 0 && <div className="empty-results">没有符合当前条件的记录</div>}
          <div className="pagination">
            <button disabled={page === 1} onClick={() => setPage(page - 1)}>上一页</button>
            <span>{page} / {formatNumber(pages)}</span>
            <button disabled={page === pages} onClick={() => setPage(page + 1)}>下一页</button>
          </div>
        </section>
        <DetailDrawer detail={detail} onClose={() => setDetail(null)} />
      </div>
      <footer className="data-status">来源：品牌官网、图片 CDN、客户本地数据与 Aloruh SHEIN SG；两个 Aloruh 数据源已分开，Estimated sold 仅为公开代理。</footer>
    </>
  );
}
