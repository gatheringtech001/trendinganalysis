import React from "react";
import { formatNumber } from "./api";
import { dimensionLabels, dimensions, formatAnalysisTag } from "./imageAnalysis";

export function DimensionFilters({ options, selected, filters, onToggle, onTagChange }) {
  const byKey = new Map(options.map((row) => [row.dimension, row.tags]));
  return (
    <section className="dimension-selector-group" aria-label="分析维度与标签选择">
      <div className="dimension-filter-heading">
        <h2>1. 选择分析维度</h2>
        <span>已选 {selected.length} / {dimensions.length}</span>
      </div>
      <p>先勾选需要组合的维度，可多选；每勾选一项，下方增加一个标签下拉框。</p>
      <div className="dimension-checkboxes" role="group" aria-label="15 个分析维度">
        {dimensions.map((dimension) => {
          const checked = selected.includes(dimension);
          const available = Boolean(byKey.get(dimension)?.length);
          return (
            <label className={checked ? "selected" : ""} key={dimension}>
              <input
                checked={checked}
                disabled={!available}
                onChange={() => onToggle(dimension)}
                type="checkbox"
              />
              <span>
                <strong>{dimensionLabels[dimension]}</strong>
                <small>{available ? `${formatNumber(byKey.get(dimension).length)} 个标签` : "待补分析"}</small>
              </span>
            </label>
          );
        })}
      </div>

      <div className="dimension-filter-heading tag-filter-heading">
        <h2>2. 选择具体标签</h2>
        <span>最多 {selected.length} 个下拉框</span>
      </div>
      {selected.length ? (
        <div className="dimension-tag-selectors">
          {selected.map((dimension) => (
            <label key={dimension}>
              <span>{dimensionLabels[dimension]}</span>
              <select
                aria-label={`${dimensionLabels[dimension]}标签`}
                onChange={(event) => onTagChange(dimension, event.target.value)}
                value={filters[dimension] || ""}
              >
                <option value="">请选择具体标签</option>
                {(byKey.get(dimension) || []).map((option) => (
                  <option key={option.tag} value={option.tag}>
                    {formatAnalysisTag(option.tag)} · {formatNumber(option.images)} 张
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>
      ) : <p className="filter-guidance">勾选上方维度后，这里会出现对应的标签下拉框。</p>}
    </section>
  );
}

export function StoreSelector({ options, selected, onToggle }) {
  const label = selected.length === options.length
    ? `全部店铺 · ${selected.length}`
    : `已选店铺 · ${selected.length}`;
  return (
    <details className="store-multiselect">
      <summary>{label}</summary>
      <div aria-label="显示店铺" role="group">
        {options.map((option) => {
          const checked = selected.includes(option.store_id);
          return (
            <label key={option.store_id}>
              <input
                checked={checked}
                disabled={checked && selected.length === 1}
                onChange={() => onToggle(option.store_id)}
                type="checkbox"
              />
              <span>{option.name}</span>
              <strong>{formatNumber(option.analyzed_images)}</strong>
            </label>
          );
        })}
      </div>
    </details>
  );
}
