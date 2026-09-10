import React, { useEffect, useState } from "react";
import { api, stores } from "./api";
import ProductImage from "./Media";
import { inferOutfit, OUTFITS } from "./digitalHuman.js";

const PAGE_SIZE = 8;

export default function DigitalHumanWardrobe({ store, selected, onSelect }) {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState({ items: [], total: 0 });
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");
  useEffect(() => {
    let current = true;
    setStatus("loading");
    setError("");
    api.products({ store, q: search, page, page_size: PAGE_SIZE }).then((data) => {
      if (!current) return;
      setResult(data);
      setStatus("ready");
    }).catch((reason) => {
      if (!current) return;
      setError(reason.message);
      setStatus("error");
    });
    return () => { current = false; };
  }, [store, search, page]);
  const pages = Math.max(1, Math.ceil(result.total / PAGE_SIZE));
  return <section className="dh-catalog">
    <div className="dh-section-title"><h3>店铺灵感库</h3><span>商品快照</span></div>
    <p className="dh-hint">选择商品关联搭配参考；识别到的品类会切换示意模板。</p>
    <form className="dh-search" onSubmit={(event) => { event.preventDefault(); setSearch(query.trim()); setPage(1); }}>
      <input aria-label="搜索参考商品" placeholder="搜索店铺商品…" value={query} onChange={(event) => setQuery(event.target.value)} />
      <button type="submit">搜索</button>
    </form>
    {status === "loading" && <p role="status">正在读取商品…</p>}
    {error && <p role="alert" className="dh-error">商品读取失败：{error}</p>}
    {status === "ready" && <>
      <div className="dh-products">
        {result.items.map((product) => {
          const key = `${product.store_id}:${product.product_id}`;
          const outfit = inferOutfit(product);
          return <button key={key} className="dh-product" aria-pressed={selected === key} onClick={() => onSelect(product, outfit)}>
            <ProductImage src={product.primary_image_url} alt={product.title} />
            <span className="dh-product-copy"><small>{stores[product.store_id]}</small><strong>{product.title}</strong>
              <small>{outfit ? `示意模板 · ${OUTFITS[outfit]}` : "仅关联参考 · 无匹配模板"}</small></span>
          </button>;
        })}
      </div>
      {!result.items.length && <p>未找到匹配商品，请调整关键词或店铺。</p>}
      <div className="dh-pagination">
        <button disabled={page === 1} onClick={() => setPage((value) => value - 1)} aria-label="上一页商品">←</button>
        <span>{page} / {pages} 页 · {result.total.toLocaleString()} 件</span>
        <button disabled={page >= pages} onClick={() => setPage((value) => value + 1)} aria-label="下一页商品">→</button>
      </div>
    </>}
  </section>;
}
