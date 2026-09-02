import React, { useEffect, useState } from "react";
import { api, stores } from "./api";
import Icon from "./icons";
import Overview from "./Overview";
import Explorer from "./Explorer";
import HeatReviews from "./HeatReviews";
import { AskView } from "./AskSources";
import SourcesView from "./SourcesView";
import { CompetitorAnalysisView, StoreAnalysisView } from "./AnalysisViews";
import ImageDimensions from "./ImageDimensions";
import Reports from "./Reports";
import CostEstimate from "./CostEstimate.jsx";

const views = {
  overview: { label: "总览", icon: "overview" },
  products: { label: "商品与SKU", icon: "products" },
  images: { label: "图片索引", icon: "images" },
  dimensions: { label: "维度分析", icon: "images" },
  reports: { label: "视觉报告", icon: "sources" },
  costs: { label: "成本估算", icon: "engagement" },
  engagement: { label: "热度与评论", icon: "engagement" },
  profile: { label: "店铺剖析", icon: "overview" },
  comparison: { label: "竞品分析", icon: "engagement" },
  ask: { label: "数据问答", icon: "ask" },
  sources: { label: "方法与来源", icon: "sources" },
};

function activeFromHash() {
  const value = window.location.hash.replace("#", "");
  return views[value] ? value : "overview";
}

export default function App() {
  const [active, setActive] = useState(activeFromHash);
  const [store, setStore] = useState("");
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const onHash = () => setActive(activeFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    if (active === "costs") {
      setError("");
      return;
    }
    setError("");
    api.summary(store).then(setSummary).catch((reason) => setError(reason.message));
  }, [active, store]);

  useEffect(() => {
    if (active === "profile" && !store) setStore("princess_polly");
  }, [active, store]);

  const navigate = (view) => {
    window.location.hash = view;
    setActive(view);
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" onClick={() => navigate("overview")}>
          <span className="brand-mark">FS</span>
          <span>Fashion Scope</span>
        </button>
        <nav aria-label="研究站导航">
          {Object.entries(views).map(([key, view]) => (
            <button
              aria-current={active === key ? "page" : undefined}
              className={active === key ? "nav-item active" : "nav-item"}
              key={key}
              onClick={() => navigate(key)}
            >
              <Icon name={view.icon} />
              <span>{view.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <span>研究快照</span>
          <strong>{summary?.snapshot || "—"}</strong>
          <small>美国主样本 · SG补充 · 只读</small>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div>
            <h1>{active === "overview" ? "四品牌·五数据源外部画像研究站" : views[active].label}</h1>
            <p>{active === "costs"
              ? "双架构 · 组件可删减 · USD / CNY 实时重算"
              : `美国主样本 · Aloruh 已按 SHEIN / Local 拆分 · 快照 ${summary?.snapshot || "—"}`}</p>
          </div>
          {active === "comparison" ? <span className="comparison-scope">两店动态对比</span> : ["dimensions", "reports", "costs"].includes(active) ? <span className="comparison-scope">{active === "costs" ? "East Asia · PAYG" : "证据可追溯"}</span> : <label className="store-select">
            <span className="sr-only">选择店铺</span>
            <select value={store} onChange={(event) => setStore(event.target.value)}>
              {Object.entries(stores).map(([value, label]) => (
                <option key={value || "all"} value={value}>{label}</option>
              ))}
            </select>
          </label>}
        </header>

        {error && active !== "costs" && <div className="error-banner">{error}</div>}
        {!summary && !error && active !== "costs" && <div className="loading">正在载入研究快照…</div>}
        {summary && active === "overview" && <Overview store={store} summary={summary} />}
        {summary && active === "products" && <Explorer mode="products" store={store} />}
        {summary && active === "images" && <Explorer mode="images" store={store} />}
        {summary && active === "dimensions" && <ImageDimensions />}
        {summary && active === "reports" && <Reports />}
        {active === "costs" && <CostEstimate />}
        {summary && active === "engagement" && <HeatReviews store={store} />}
        {summary && active === "profile" && <StoreAnalysisView store={store} />}
        {summary && active === "comparison" && <CompetitorAnalysisView />}
        {summary && active === "ask" && <AskView summary={summary} />}
        {summary && active === "sources" && <SourcesView summary={summary} store={store} />}
      </main>
    </div>
  );
}
