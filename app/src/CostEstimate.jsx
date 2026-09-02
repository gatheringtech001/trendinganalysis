import React, { useMemo, useState } from "react";
import {
  DEFAULT_INPUTS,
  OBSERVED_BASELINE,
  SOURCE_LINKS,
  calculateEstimate,
  formatMoney,
} from "./costEstimate.js";
import "./costEstimate.css";

const integer = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 });

const controls = [
  ["ownedStores", "自营店铺", 1, 20, 1, "每个自营店绑定 3 个竞品"],
  ["concurrentUsers", "同步在线用户", 1, 500, 1, "影响交互计算规格"],
  ["fullRunsPerWeek", "全量爬取 / 周", 0, 7, 1, "全量校验，默认不重复打标"],
  ["incrementalRunsPerDay", "增量爬取 / 天", 0, 24, 1, "新增或变更图片会打标"],
  ["reportsPerWeek", "报告 / 周 / 自营店", 0, 7, 1, "每份按已完成专项分析实测"],
  ["retentionMonths", "图片与数据留存月数", 1, 36, 1, "同时作为总成本观察周期"],
];

const advancedControls = [
  ["dailyIncrementPercent", "每日增量占全量 %", 0, 20, 0.1, "未知业务量，默认规划值 1%"],
  ["fullRetagPercent", "全量爬取重打标 %", 0, 100, 1, "默认 0%，按内容哈希复用标签"],
  ["averageImageKb", "平均图片大小 KB", 10, 5000, 10, "本地 288 张样本约 199 KB"],
  ["egressGbPerUser", "人均出站 GB / 月", 0, 1000, 1, "首 100 GB / 月免费"],
];

const architecture = {
  infra: ["用户", "公网 IP", "Linux VM：Web / API / 爬虫 / SQLite", "托管磁盘", "Azure OpenAI"],
  paas: ["Entra ID + Static Web Apps", "Container Apps API", "Service Bus + Jobs", "PostgreSQL + Blob", "AI Search + OneLake + Azure OpenAI"],
};

function InputControl({ row, value, onChange }) {
  const [id, label, min, max, step, hint] = row;
  return <label className="cost-input">
    <span>{label}</span>
    <input aria-label={label} min={min} max={max} step={step} type="number"
      value={value} onChange={(event) => onChange(id, event.target.value)} />
    <small>{hint}</small>
  </label>;
}

function Summary({ title, version, currency, rate, accent }) {
  const money = (value) => formatMoney(value, currency, rate);
  return <article className={`cost-summary ${accent}`}>
    <span>{title}</span>
    <strong>{money(version.steadyMonthly)}</strong>
    <small>稳态月成本</small>
    <dl>
      <div><dt>首次全量打标</dt><dd>{money(version.onboarding)}</dd></div>
      <div><dt>首月成本</dt><dd>{money(version.firstMonth)}</dd></div>
      <div><dt>留存周期总成本</dt><dd>{money(version.horizonTotal)}</dd></div>
    </dl>
  </article>;
}

function Architecture({ version, disabled }) {
  return <div className="architecture-flow" aria-label={`${version} 架构`}>
    {architecture[version].map((node, index) => <React.Fragment key={node}>
      <span className={disabled && index > 0 ? "architecture-node muted" : "architecture-node"}>{node}</span>
      {index < architecture[version].length - 1 && <i aria-hidden="true">→</i>}
    </React.Fragment>)}
  </div>;
}

function Breakdown({ name, versionId, version, currency, rate, onToggle }) {
  const removedCore = version.components.filter((row) => row.core && !row.enabled);
  return <section className="cost-breakdown">
    <div className="cost-section-heading">
      <div><span>COMPONENT PRICING</span><h3>{name}</h3></div>
      <strong>{formatMoney(version.steadyMonthly, currency, rate)} / 月</strong>
    </div>
    {removedCore.length > 0 && <p className="cost-warning">
      已移除核心能力：{removedCore.map((row) => row.label).join("、")}。价格已扣除，但架构不再满足完整需求。
    </p>}
    <div className="cost-table-wrap"><table className="cost-table">
      <thead><tr><th>启用</th><th>组件 / 规格</th><th>稳态月费</th><th>首次费用</th><th>计算依据</th></tr></thead>
      <tbody>{version.components.map((row) => <tr className={row.enabled ? "" : "disabled"} key={row.id}>
        <td><input aria-label={`${name} ${row.label}`} checked={row.enabled} type="checkbox"
          onChange={() => onToggle(versionId, row.id)} /></td>
        <td><strong>{row.label}{row.core && <em>核心</em>}</strong><small>{row.category} · {row.sku}</small></td>
        <td>{formatMoney(row.monthly, currency, rate)}</td>
        <td>{row.onboarding ? formatMoney(row.onboarding, currency, rate) : "—"}</td>
        <td><span>{row.basis}</span>{row.source && <a href={row.source} rel="noreferrer" target="_blank">官方依据</a>}
          <small>置信度 {row.confidence}</small></td>
      </tr>)}</tbody>
    </table></div>
  </section>;
}

function Evidence() {
  const tagUnit = OBSERVED_BASELINE.taggingTestCostUsd / OBSERVED_BASELINE.taggingTestImages;
  return <section className="cost-evidence">
    <div className="cost-section-heading"><div><span>OBSERVED + PRICED + MODELED</span><h3>依据与边界</h3></div></div>
    <div className="evidence-grid">
      <article><b>仓库当前快照</b><strong>{integer.format(OBSERVED_BASELINE.imageRecords)} 图片记录</strong>
        <p>{integer.format(OBSERVED_BASELINE.products)} 商品；SQLite 约 84 MB；{integer.format(OBSERVED_BASELINE.analyzedImages)} 张已有标签。</p></article>
      <article><b>图片打标实测</b><strong>${tagUnit.toFixed(6)} / 张</strong>
        <p>{integer.format(OBSERVED_BASELINE.taggingTestImages)} 张、{integer.format(OBSERVED_BASELINE.taggingTestTokens)} tokens、${OBSERVED_BASELINE.taggingTestCostUsd.toFixed(2)}。</p></article>
      <article><b>周报专项分析实测</b><strong>${OBSERVED_BASELINE.reportTestCostUsd.toFixed(2)} / 份</strong>
        <p>{OBSERVED_BASELINE.reportTestImages} 张证据图、{OBSERVED_BASELINE.reportTestCalls} 次 API、{integer.format(OBSERVED_BASELINE.reportTestTokens)} tokens。</p></article>
      <article><b>Azure 单价</b><strong>East Asia · USD PAYG</strong>
        <p>2026-09-02 通过 <a href={SOURCE_LINKS.retail} rel="noreferrer" target="_blank">Azure Retail Prices API</a> 与官方产品页核对；税、EA 折扣、支持计划除外。</p></article>
    </div>
    <div className="cost-notes">
      <p><b>High</b>：来自本系统完整运行记录或直接单价；<b>Medium</b>：官方单价叠加容量选型；<b>Low</b>：日志量、出站量等尚无生产观测。</p>
      <p>不含开发实施、人力运维、域名、短信 MFA、生产 SLA 冗余、跨区容灾和税费。全量周爬按 URL/内容哈希去重，默认只给新增或变更图片打标；若要求每周重打标，请调高“全量爬取重打标 %”。</p>
    </div>
  </section>;
}

export default function CostEstimate() {
  const [inputs, setInputs] = useState(DEFAULT_INPUTS);
  const [disabled, setDisabled] = useState({ infra: [], paas: [] });
  const [showAdvanced, setShowAdvanced] = useState(false);
  const estimate = useMemo(() => calculateEstimate(inputs, disabled), [inputs, disabled]);
  const { workload, versions } = estimate;
  const money = (value) => formatMoney(value, inputs.currency, inputs.usdToCny);
  const update = (id, value) => setInputs((current) => ({ ...current, [id]: value }));
  const toggle = (version, id) => setDisabled((current) => ({
    ...current,
    [version]: current[version].includes(id)
      ? current[version].filter((value) => value !== id)
      : [...current[version], id],
  }));
  const difference = versions.paas.steadyMonthly - versions.infra.steadyMonthly;

  return <div className="cost-report">
    <section className="cost-hero">
      <div><span>INTERACTIVE AZURE COST MODEL · 2026-09-02</span>
        <h2>AI 是主要变量；PaaS 用更高固定费换任务韧性与可检索证据</h2>
        <p>按 1 个自营店绑定 3 个竞品建模。修改业务参数或取消任一组件后，两套架构的首月、稳态月和留存周期成本会立即重算。</p></div>
      <div className="cost-actions">
        <button type="button" onClick={() => { setInputs(DEFAULT_INPUTS); setDisabled({ infra: [], paas: [] }); }}>恢复默认</button>
        <button type="button" onClick={() => window.print()}>打印 / 导出 PDF</button>
      </div>
    </section>

    <section className="cost-controls">
      <div className="control-heading"><div><span>SCENARIO INPUTS</span><h3>业务参数</h3></div>
        <div className="preset-buttons"><button onClick={() => update("concurrentUsers", 1)} type="button">1 人</button>
          <button onClick={() => update("concurrentUsers", 15)} type="button">客户 15 人</button>
          <button onClick={() => update("ownedStores", 1)} type="button">1 自营 / 4 店</button>
          <button onClick={() => update("ownedStores", 2)} type="button">2 自营 / 8 店</button></div></div>
      <div className="cost-input-grid">{controls.map((row) => <InputControl key={row[0]} row={row}
        value={inputs[row[0]]} onChange={update} />)}</div>
      <button className="advanced-toggle" type="button" onClick={() => setShowAdvanced((value) => !value)}>
        {showAdvanced ? "收起容量假设" : "展开容量假设"}
      </button>
      {showAdvanced && <div className="cost-input-grid advanced">{advancedControls.map((row) => <InputControl
        key={row[0]} row={row} value={inputs[row[0]]} onChange={update} />)}</div>}
      <div className="currency-row"><label>显示币种<select value={inputs.currency} onChange={(event) => update("currency", event.target.value)}>
        <option value="USD">USD</option><option value="CNY">CNY</option></select></label>
        {inputs.currency === "CNY" && <label>USD / CNY 规划汇率<input aria-label="USD / CNY 规划汇率" min="1" max="20" step="0.01"
          type="number" value={inputs.usdToCny} onChange={(event) => update("usdToCny", event.target.value)} /></label>}</div>
    </section>

    <section className="workload-strip">
      <div><strong>{workload.logicalStores}</strong><span>逻辑店铺</span></div>
      <div><strong>{integer.format(workload.taggedImagesMonthly)}</strong><span>稳态月打标图片</span></div>
      <div><strong>{workload.storageGb.toFixed(1)} GB</strong><span>{inputs.retentionMonths} 个月图片存储</span></div>
      <div><strong>{money(Math.abs(difference))}</strong><span>PaaS 稳态月{difference >= 0 ? "溢价" : "节省"}</span></div>
    </section>

    <section className="summary-grid">
      <Summary title="版本 1 · Infra + 现有系统" version={versions.infra} currency={inputs.currency} rate={inputs.usdToCny} accent="infra" />
      <Summary title="版本 2 · Azure PaaS / SaaS" version={versions.paas} currency={inputs.currency} rate={inputs.usdToCny} accent="paas" />
    </section>

    <section className="architecture-grid">
      <article><span>VERSION 1</span><h3>单机整合，迁移最少</h3><Architecture version="infra" disabled={disabled.infra.length > 0} />
        <p>沿用 Python + SQLite + 本地任务线程；单点故障、爬取与在线查询争抢资源，适合 PoC 或短期低复杂度运行。</p></article>
      <article><span>VERSION 2</span><h3>在线服务与批处理解耦</h3><Architecture version="paas" disabled={disabled.paas.length > 0} />
        <p>Container Apps Jobs 持久化批任务状态；Blob 保存原始图片，PostgreSQL 保存业务数据，AI Search 查向量证据，OneLake 保存整理后的周期历史。</p></article>
    </section>

    <Breakdown name="版本 1 · Infra + 现有系统" versionId="infra" version={versions.infra}
      currency={inputs.currency} rate={inputs.usdToCny} onToggle={toggle} />
    <Breakdown name="版本 2 · Azure PaaS / SaaS" versionId="paas" version={versions.paas}
      currency={inputs.currency} rate={inputs.usdToCny} onToggle={toggle} />
    <Evidence />
  </div>;
}
