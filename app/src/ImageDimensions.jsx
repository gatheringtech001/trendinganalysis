import React, { useEffect, useMemo, useState } from "react";
import { api, formatNumber, stores as storeNames } from "./api";
import DetailedVisualAnalysis from "./DetailedVisualAnalysis";
import { DetailDrawer } from "./Explorer";
import { DimensionFilters, StoreSelector } from "./ImageDimensionControls";
import { dimensionLabels, dimensions, formatAnalysisTag } from "./imageAnalysis";
import ProductImage from "./Media";

const storeIds = Object.keys(storeNames).filter(Boolean);
const defaultStoreOptions = storeIds.map((storeId) => ({
  store_id: storeId,
  name: storeNames[storeId],
  analyzed_images: 0,
}));
const emptyResult = {
  analyzed_images: 0,
  dimension_options: [],
  matched_images: 0,
  store_groups: [],
  stores: defaultStoreOptions,
};

const imageKey = (item) => `${item.store_id}:${item.product_id}:${item.position}`;

function DimensionImage({
  item, selected, selectedForAnalysis, selectedDimensions, onSelect,
  onToggleAnalysis,
}) {
  const visibleDimensions = selectedDimensions.slice(0, 3);
  return (
    <article className={selectedForAnalysis ? "dimension-image-card picked" : "dimension-image-card"}>
      <button
        aria-label={`查看 ${item.title} 的完整维度分析`}
        className={selected ? "dimension-image selected" : "dimension-image"}
        onClick={() => onSelect(item)}
        type="button"
      >
        <ProductImage src={item.image_url} alt={item.title} />
        <div>
          <h3>{item.title}</h3>
          <p>{storeNames[item.store_id]} · {item.product_id}</p>
          <dl>
            {visibleDimensions.map((dimension) => (
              <div key={dimension}>
                <dt>{dimensionLabels[dimension]}</dt>
                <dd>{(item.analysis?.tags?.[dimension] || []).map(formatAnalysisTag).join(" · ") || "未识别"}</dd>
              </div>
            ))}
          </dl>
          {selectedDimensions.length > visibleDimensions.length
            ? <small>另有 {selectedDimensions.length - visibleDimensions.length} 个已选维度</small>
            : null}
        </div>
      </button>
      <label className="analysis-image-picker">
        <input
          checked={selectedForAnalysis}
          onChange={() => onToggleAnalysis(item)}
          type="checkbox"
        />
        <span>{selectedForAnalysis ? "已选入精细分析" : "选入精细分析"}</span>
      </label>
    </article>
  );
}

function StoreGroup({
  row, selectedDimensions, detail, onSelect, onToggleAnalysis, selectedImageKeys,
}) {
  return (
    <section className={row.images ? "dimension-store-group" : "dimension-store-group empty"}>
      <header>
        <h3>{row.store_name}</h3>
        <span>{formatNumber(row.images)} 张 · 店内分析图片占比 {(row.share * 100).toFixed(1)}%</span>
      </header>
      {row.items.length ? (
        <div className="dimension-gallery">
          {row.items.map((item) => (
            <DimensionImage
              item={item}
              key={`${item.store_id}-${item.product_id}-${item.position}`}
              onSelect={onSelect}
              onToggleAnalysis={onToggleAnalysis}
              selected={detail?.store_id === item.store_id
                && detail?.product_id === item.product_id
                && detail?.selected_position === item.position}
              selectedForAnalysis={selectedImageKeys.has(imageKey(item))}
              selectedDimensions={selectedDimensions}
            />
          ))}
        </div>
      ) : <p>当前固定组合在该店铺没有匹配图片</p>}
    </section>
  );
}

function DimensionDetail({ detail, onClose }) {
  useEffect(() => {
    const closeOnEscape = (event) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);
  if (!detail) return null;
  return (
    <div className="dimension-detail-overlay" onClick={onClose} role="presentation">
      <div
        aria-label="图片与商品维度详情"
        aria-modal="true"
        className="dimension-detail-panel"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        <DetailDrawer detail={detail} onClose={onClose} />
      </div>
    </div>
  );
}

export default function ImageDimensions() {
  const [selectedDimensions, setSelectedDimensions] = useState([]);
  const [filters, setFilters] = useState({});
  const [selectedStores, setSelectedStores] = useState(storeIds);
  const [result, setResult] = useState(emptyResult);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [analysisJob, setAnalysisJob] = useState(null);
  const [imagesPerStore, setImagesPerStore] = useState(4);
  const [analysisMode, setAnalysisMode] = useState("random");
  const [selectedImages, setSelectedImages] = useState([]);
  const missingDimensions = selectedDimensions.filter((dimension) => !filters[dimension]);
  const ready = selectedDimensions.length > 0 && missingDimensions.length === 0;
  const activeFilters = Object.fromEntries(
    selectedDimensions.map((dimension) => [dimension, filters[dimension]]),
  );
  const filtersKey = ready ? JSON.stringify(activeFilters) : "{}";
  const storesKey = selectedStores.join(",");
  const selectedImageKeys = useMemo(
    () => new Set(selectedImages.map(imageKey)), [selectedImages],
  );

  useEffect(() => {
    let active = true;
    setAnalysisJob(null);
    setSelectedImages([]);
    setLoading(true);
    setError("");
    api.imageDimensions({
      filters: filtersKey,
      stores: storesKey,
      images_per_store: 12,
    })
      .then((data) => { if (active) setResult(data); })
      .catch((reason) => { if (active) setError(reason.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [filtersKey, storesKey]);

  useEffect(() => {
    if (!["queued", "running"].includes(analysisJob?.status)) return undefined;
    let active = true;
    const timer = window.setTimeout(() => {
      api.detailedAnalysis(analysisJob.job_id)
        .then((data) => { if (active) setAnalysisJob(data); })
        .catch((reason) => { if (active) setError(reason.message); });
    }, 1500);
    return () => { active = false; window.clearTimeout(timer); };
  }, [analysisJob]);

  const resetSelection = () => setDetail(null);
  const toggleDimension = (dimension) => {
    setSelectedDimensions((current) => dimensions.filter((value) => (
      value === dimension ? !current.includes(value) : current.includes(value)
    )));
    setFilters((current) => {
      if (!selectedDimensions.includes(dimension)) return current;
      const next = { ...current };
      delete next[dimension];
      return next;
    });
    resetSelection();
  };
  const changeTag = (dimension, tag) => {
    setFilters((current) => ({ ...current, [dimension]: tag }));
    resetSelection();
  };
  const toggleStore = (storeId) => {
    setSelectedStores((current) => current.includes(storeId)
      ? current.filter((value) => value !== storeId)
      : storeIds.filter((value) => current.includes(value) || value === storeId));
    resetSelection();
  };
  const selectImage = async (item) => {
    try {
      const selected = await api.product(item.store_id, item.product_id);
      setDetail({ ...selected, selected_position: item.position });
    } catch (reason) {
      setError(reason.message);
    }
  };
  const toggleAnalysisImage = (item) => {
    setSelectedImages((current) => {
      const key = imageKey(item);
      if (current.some((value) => imageKey(value) === key)) {
        return current.filter((value) => imageKey(value) !== key);
      }
      if (current.length >= 24) {
        setError("一次最多手动选择 24 张图片");
        return current;
      }
      return [...current, {
        store_id: item.store_id,
        product_id: item.product_id,
        position: item.position,
      }];
    });
    setAnalysisJob(null);
  };
  const eligibleStores = result.store_groups
    .filter((row) => row.images > 0)
    .map((row) => row.store_id);
  const maxImagesPerStore = Math.max(1, Math.min(
    8, Math.floor(24 / Math.max(eligibleStores.length, 1)),
  ));
  const estimatedDetailedImages = result.store_groups.reduce(
    (total, row) => total + Math.min(row.images, imagesPerStore), 0,
  );
  const startDetailedAnalysis = async () => {
    setError("");
    try {
      const manualStores = storeIds.filter((storeId) => (
        selectedImages.some((item) => item.store_id === storeId)
      ));
      const payload = {
        filters: activeFilters,
        stores: analysisMode === "manual" ? manualStores : eligibleStores,
      };
      if (analysisMode === "manual") payload.selected_images = selectedImages;
      else payload.images_per_store = Math.min(imagesPerStore, maxImagesPerStore);
      const job = await api.startDetailedAnalysis(payload);
      setAnalysisJob(job);
    } catch (reason) {
      setError(reason.message);
    }
  };

  return (
    <div className="dimensions-page">
      <section className="dimension-hero">
        <div>
          <span>IMAGE INTELLIGENCE</span>
          <h2>图片多维固定组合分析</h2>
          <p>先选维度，再为每个维度指定一个标签；多个标签按 AND 精确筛选。</p>
        </div>
        <dl>
          <div><dt>已分析图片</dt><dd>{formatNumber(result.analyzed_images)}</dd></div>
          <div><dt>已选维度</dt><dd>{formatNumber(selectedDimensions.length)}</dd></div>
          <div><dt>匹配图片</dt><dd>{formatNumber(ready ? result.matched_images : 0)}</dd></div>
        </dl>
      </section>

      {error ? <div className="error-banner">{error}</div> : null}
      <div className="dimension-controls">
        <DimensionFilters
          filters={filters}
          onTagChange={changeTag}
          onToggle={toggleDimension}
          options={result.dimension_options}
          selected={selectedDimensions}
        />
        <section className="store-selector-group">
          <div className="dimension-filter-heading">
            <h2>3. 选择显示店铺</h2>
            <span>已选 {selectedStores.length} / {result.stores.length}</span>
          </div>
          <p>店铺可多选；最终匹配图片会天然按店铺分别展示。</p>
          <StoreSelector
            onToggle={toggleStore}
            options={result.stores}
            selected={selectedStores}
          />
        </section>
      </div>

      <main className="dimension-content">
        <div className="section-heading">
          <h2>固定组合结果</h2>
          <span>{ready && !loading ? `${formatNumber(result.matched_images)} 张匹配 · 按店铺展示` : "等待完整筛选条件"}</span>
        </div>
        {!selectedDimensions.length
          ? <div className="filter-result-guidance">请先从 15 个维度中勾选至少一个已有数据的维度；新增3维会在补分析后开放筛选。</div>
          : null}
        {selectedDimensions.length && missingDimensions.length
          ? <div className="filter-result-guidance">请为 {missingDimensions.map((dimension) => dimensionLabels[dimension]).join("、")} 选择具体标签。</div>
          : null}
        {ready ? (
          <>
            <div className="active-filter-summary" aria-label="当前固定组合">
              {selectedDimensions.map((dimension) => (
                <span key={dimension}>
                  <small>{dimensionLabels[dimension]}</small>
                  {formatAnalysisTag(filters[dimension])}
                </span>
              ))}
            </div>
            {loading ? <div className="loading">正在筛选图片…</div> : null}
            {!loading && result.matched_images ? (
              <div className="dimension-store-feed">
                {result.store_groups.map((row) => (
                  <StoreGroup
                    detail={detail}
                    key={row.store_id}
                    onSelect={selectImage}
                    onToggleAnalysis={toggleAnalysisImage}
                    row={row}
                    selectedImageKeys={selectedImageKeys}
                    selectedDimensions={selectedDimensions}
                  />
                ))}
              </div>
            ) : null}
            {!loading && !result.matched_images
              ? <div className="empty-results">所选店铺没有同时满足全部标签的图片</div>
              : null}
            <DetailedVisualAnalysis
              analysisMode={analysisMode}
              disabled={loading || !result.matched_images || !eligibleStores.length
                || (analysisMode === "manual" && !selectedImages.length)}
              eligibleStores={eligibleStores}
              estimatedImages={analysisMode === "manual"
                ? selectedImages.length : estimatedDetailedImages}
              imagesPerStore={Math.min(imagesPerStore, maxImagesPerStore)}
              job={analysisJob}
              maxImagesPerStore={maxImagesPerStore}
              onAnalysisModeChange={(mode) => {
                setAnalysisMode(mode);
                setAnalysisJob(null);
              }}
              onImagesPerStoreChange={setImagesPerStore}
              onStart={startDetailedAnalysis}
              selectedImages={selectedImages}
            />
          </>
        ) : null}
      </main>
      <DimensionDetail detail={detail} onClose={() => setDetail(null)} />
      <footer className="data-status">每个已选维度只取一个标签，维度之间使用 AND；图片只要包含对应标签即命中，结果不再枚举组合。</footer>
    </div>
  );
}
