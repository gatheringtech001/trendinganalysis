import React, { useEffect, useState } from "react";
import { api, formatNumber, formatPrice, storeColors, stores } from "./api";
import { formatCategory } from "./imageAnalysis";
import ProductImage from "./Media";

const defaultQuestion = "哪家店的连衣裙SKU最多？";
const suggestions = ["哪家店图片索引最多？", "各数据源商品价格中位数？", "哪家店售罄SKU最多？"];

function MetricStrip({ metrics }) {
  const values = [
    [metrics.products, "商品SKU"],
    [metrics.images, "图片索引"],
    [metrics.downloaded, "已下载样本"],
    [metrics.reviews, "评论记录"],
  ];
  return (
    <section className="metric-strip" aria-label="核心数据">
      {values.map(([value, label]) => (
        <div className="metric" key={label}>
          <strong>{formatNumber(value)}</strong>
          <span>{label}</span>
        </div>
      ))}
    </section>
  );
}

function CategoryChart({ categories }) {
  const rows = categories.slice(0, 5);
  const max = Math.max(...rows.map((row) => row.products), 1);
  return (
    <section className="chart-section">
      <div className="section-heading">
        <h2>SKU分类结构</h2>
        <span>按官网商品记录计数</span>
      </div>
      <div className="category-chart">
        {rows.map((row) => (
          <div className="bar-row" key={row.category}>
            <span className="bar-label">{formatCategory(row.category)}</span>
            <div className="bar-track">
              <div className="bar-total" style={{ width: `${(row.products / max) * 100}%` }}>
                {row.stores.map((item) => (
                  <span
                    key={item.store_id}
                    style={{
                      background: storeColors[item.store_id],
                      width: `${(item.value / row.products) * 100}%`,
                    }}
                  />
                ))}
              </div>
            </div>
            <strong>{formatNumber(row.products)}</strong>
          </div>
        ))}
      </div>
      <div className="legend">
        {Object.entries(stores).filter(([key]) => key).map(([key, label]) => (
          <span key={key}><i style={{ background: storeColors[key] }} />{label}</span>
        ))}
      </div>
    </section>
  );
}

function ProductRail({ store }) {
  const [products, setProducts] = useState([]);
  useEffect(() => {
    api.products({ store, available: 1, page_size: 5, sort: "newest" })
      .then((result) => setProducts(result.items));
  }, [store]);
  return (
    <section className="product-rail-section">
      <div className="section-heading">
        <h2>近期商品图</h2>
        <a href="#images">查看全部图片</a>
      </div>
      <div className="product-rail">
        {products.map((item) => (
          <a className="rail-card" href="#images" key={`${item.store_id}-${item.product_id}`}>
            <ProductImage src={item.primary_image_url} alt={item.title} />
            <div>
              <h3>{item.title}</h3>
              <p>{formatCategory(item.category)}</p>
              <strong>{formatPrice(item.price_usd)}</strong>
              <span>{stores[item.store_id]}</span>
            </div>
          </a>
        ))}
      </div>
    </section>
  );
}

function AskPanel() {
  const [question, setQuestion] = useState(defaultQuestion);
  const [answer, setAnswer] = useState(null);
  const [busy, setBusy] = useState(false);
  const ask = async (nextQuestion = question) => {
    setQuestion(nextQuestion);
    setBusy(true);
    try {
      setAnswer(await api.ask(nextQuestion));
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => { ask(defaultQuestion); }, []);
  return (
    <aside className="ask-panel">
      <h2>问数据</h2>
      <textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
      <button className="primary-button" disabled={busy} onClick={() => ask()}>
        {busy ? "分析中…" : "开始分析"}
      </button>
      <div className="suggestions">
        {suggestions.map((item) => <button key={item} onClick={() => ask(item)}>{item}</button>)}
      </div>
      {answer && (
        <div className={answer.supported ? "answer" : "answer unsupported"}>
          <p>{answer.answer}</p>
          <span>基于官网商品索引 · {answer.confidence}置信度</span>
        </div>
      )}
    </aside>
  );
}

export default function Overview({ store, summary }) {
  return (
    <>
      <MetricStrip metrics={summary.metrics} />
      <div className="overview-grid">
        <div className="overview-main">
          <CategoryChart categories={summary.categories} />
          <ProductRail store={store} />
        </div>
        <AskPanel />
      </div>
      <footer className="data-status">
        数据覆盖：官网商品目录、商品图片、评论、UGC与WebIQ外部证据
      </footer>
    </>
  );
}
