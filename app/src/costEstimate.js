const HOURS_PER_MONTH = 730;
const WEEKS_PER_MONTH = 52 / 12;
const DAYS_PER_MONTH = 30;
const KB_PER_GB = 1024 * 1024;

export const DEFAULT_INPUTS = Object.freeze({
  ownedStores: 1, concurrentUsers: 15,
  fullRunsPerWeek: 1, incrementalRunsPerDay: 1, reportsPerWeek: 1,
  retentionMonths: 6, dailyIncrementPercent: 1, fullRetagPercent: 0,
  averageImageKb: 200, egressGbPerUser: 2,
  currency: "USD", usdToCny: 7.12,
});

export const OBSERVED_BASELINE = Object.freeze({
  products: 60260, imageRecords: 288831, databaseGb: 84 / 1024,
  analyzedImages: 25916, taggingTestImages: 10468,
  taggingTestCostUsd: 47.5624121, taggingTestTokens: 8133715,
  reportTestImages: 492, reportTestCalls: 63,
  reportTestTokens: 1402809, reportTestCostUsd: 17.16,
});

export const SOURCE_LINKS = Object.freeze({
  retail: "https://prices.azure.com/api/retail/prices",
  vm: "https://azure.microsoft.com/en-us/pricing/details/virtual-machines/linux/", disks: "https://azure.microsoft.com/en-us/pricing/details/managed-disks/",
  containerApps: "https://azure.microsoft.com/en-us/pricing/details/container-apps/", postgres: "https://azure.microsoft.com/en-us/pricing/details/postgresql/flexible-server/",
  blob: "https://azure.microsoft.com/en-us/pricing/details/storage/blobs/", search: "https://azure.microsoft.com/en-us/pricing/details/search/",
  serviceBus: "https://azure.microsoft.com/en-us/pricing/details/service-bus/", entra: "https://www.microsoft.com/en-us/security/business/microsoft-entra-pricing",
  keyVault: "https://azure.microsoft.com/en-us/pricing/details/key-vault/", fabric: "https://azure.microsoft.com/en-us/pricing/details/microsoft-fabric/",
  monitor: "https://azure.microsoft.com/en-us/pricing/details/monitor/", bandwidth: "https://azure.microsoft.com/en-us/pricing/details/bandwidth/",
});
function bounded(value, minimum, maximum) {
  const number = Number(value);
  if (!Number.isFinite(number)) return minimum;
  return Math.min(maximum, Math.max(minimum, number));
}
export function normalizeInputs(value = {}) {
  return {
    ownedStores: Math.round(bounded(value.ownedStores, 1, 20)), concurrentUsers: Math.round(bounded(value.concurrentUsers, 1, 500)),
    fullRunsPerWeek: bounded(value.fullRunsPerWeek, 0, 7), incrementalRunsPerDay: bounded(value.incrementalRunsPerDay, 0, 24),
    reportsPerWeek: bounded(value.reportsPerWeek, 0, 7), retentionMonths: Math.round(bounded(value.retentionMonths, 1, 36)),
    dailyIncrementPercent: bounded(value.dailyIncrementPercent, 0, 20), fullRetagPercent: bounded(value.fullRetagPercent, 0, 100),
    averageImageKb: bounded(value.averageImageKb, 10, 5000), egressGbPerUser: bounded(value.egressGbPerUser, 0, 1000),
    currency: value.currency === "CNY" ? "CNY" : "USD",
    usdToCny: bounded(value.usdToCny, 1, 20),
  };
}
function buildWorkload(inputs) {
  const logicalStores = inputs.ownedStores * 4;
  const baselineImages = OBSERVED_BASELINE.imageRecords * inputs.ownedStores;
  const fullChecksMonthly = baselineImages * inputs.fullRunsPerWeek * WEEKS_PER_MONTH;
  const incrementalImagesMonthly = baselineImages
    * inputs.dailyIncrementPercent / 100
    * inputs.incrementalRunsPerDay * DAYS_PER_MONTH;
  const taggedImagesMonthly = incrementalImagesMonthly
    + fullChecksMonthly * inputs.fullRetagPercent / 100;
  const storedImages = baselineImages
    + incrementalImagesMonthly * inputs.retentionMonths;
  return {
    logicalStores,
    baselineImages,
    fullChecksMonthly,
    incrementalImagesMonthly,
    taggedImagesMonthly,
    storedImages,
    storageGb: storedImages * inputs.averageImageKb / KB_PER_GB,
    indexGb: storedImages * 8 / KB_PER_GB,
    curatedGb: Math.max(1, OBSERVED_BASELINE.databaseGb
      * inputs.ownedStores * inputs.retentionMonths),
    crawlRecordsMonthly: fullChecksMonthly + incrementalImagesMonthly,
  };
}
function vmComponent(inputs) {
  let sku = "D2as v5";
  let hourly = 0.119;
  let instances = 1;
  if (inputs.concurrentUsers > 5 || inputs.ownedStores > 1) {
    [sku, hourly] = ["D4as v5", 0.238];
  }
  if (inputs.concurrentUsers > 20 || inputs.ownedStores > 2) {
    const pressure = Math.max(inputs.concurrentUsers / 40, inputs.ownedStores / 4);
    [sku, hourly, instances] = ["D8as v5", 0.476, Math.ceil(pressure)];
  }
  return component("vm", "应用、API、爬虫与本地数据库 VM", "计算", {
    monthly: hourly * HOURS_PER_MONTH * instances,
    sku: `${instances > 1 ? `${instances} × ` : ""}${sku}`,
    basis: `${hourly.toFixed(3)}/小时 × 730 小时 × ${instances}；按店铺/并发容量阶梯选型`,
    source: SOURCE_LINKS.vm, confidence: "Medium", core: true,
  });
}

function managedDiskComponent(storageGb) {
  const tiers = [
    { capacity: 512, sku: "P20 LRS", price: 80.54 },
    { capacity: 1024, sku: "P30 LRS", price: 148.68 },
    { capacity: 2048, sku: "P40 LRS", price: 284.9371 },
  ];
  let tier = tiers.find((row) => storageGb <= row.capacity);
  let count = 1;
  if (!tier) {
    tier = tiers[2];
    count = Math.ceil(storageGb / tier.capacity);
  }
  return component("disk", "托管磁盘（系统 + 六个月图片/数据）", "存储", {
    monthly: tier.price * count + 9.6,
    sku: `E10 OS + ${count} × ${tier.sku}`,
    basis: `$9.60/月系统盘 + ${count} × $${tier.price.toFixed(2)}/月数据盘；按 ${storageGb.toFixed(0)} GB 向上取档`,
    source: SOURCE_LINKS.disks, confidence: "Medium", core: true,
  });
}

function component(id, label, category, values) {
  return { id, label, category, onboarding: 0, core: false, ...values };
}

function aiComponents(inputs, workload) {
  const tagUnit = OBSERVED_BASELINE.taggingTestCostUsd
    / OBSERVED_BASELINE.taggingTestImages;
  return [
    component("aiTagging", "Azure OpenAI 图片打标", "AI", {
      monthly: workload.taggedImagesMonthly * tagUnit,
      onboarding: workload.baselineImages * tagUnit,
      sku: "gpt-5.6-terra 实测单价",
      basis: `$47.5624 / 10,468 张 = $${tagUnit.toFixed(6)}/张；首月全量，稳态仅新增/变更 + 指定重打标`,
      confidence: "High", core: true,
    }),
    component("aiReports", "Azure OpenAI 周报专项分析", "AI", {
      monthly: OBSERVED_BASELINE.reportTestCostUsd * inputs.reportsPerWeek
        * WEEKS_PER_MONTH * inputs.ownedStores,
      sku: "gpt-5.6-sol 实测任务",
      basis: `$17.16/份 × ${inputs.reportsPerWeek}/周 × 4.33 周 × ${inputs.ownedStores} 个自营店`,
      confidence: "High", core: true,
    }),
  ];
}

function infraComponents(inputs, workload) {
  const disk = managedDiskComponent(workload.storageGb);
  const egressGb = Math.max(0,
    inputs.concurrentUsers * inputs.egressGbPerUser - 100);
  return [
    vmComponent(inputs),
    disk,
    component("backup", "Azure Backup", "韧性", {
      monthly: 10 + workload.storageGb * 0.0224,
      sku: "1 个受保护 VM + LRS",
      basis: `$10/实例月 + ${workload.storageGb.toFixed(1)} GB × $0.0224/GB月`,
      source: SOURCE_LINKS.retail, confidence: "Medium", core: true,
    }),
    component("publicIp", "标准公网 IPv4", "网络", {
      monthly: 0.005 * HOURS_PER_MONTH,
      sku: "Standard IPv4",
      basis: "$0.005/小时 × 730 小时",
      source: SOURCE_LINKS.retail, confidence: "High", core: true,
    }),
    component("monitor", "Application Insights / Log Analytics", "可观测性", {
      monthly: 5 * 4.03,
      sku: "Analytics Logs 5 GB/月",
      basis: "5 GB/月 × $4.03/GB；日志量为规划假设",
      source: SOURCE_LINKS.monitor, confidence: "Low",
    }),
    component("egress", "互联网出站流量", "网络", {
      monthly: egressGb * 0.12,
      sku: "Asia Premium Global Network",
      basis: `首 100 GB 免费；其后 ${egressGb.toFixed(1)} GB × $0.12/GB`,
      source: SOURCE_LINKS.bandwidth, confidence: "Low",
    }),
    ...aiComponents(inputs, workload),
  ];
}

function apiContainerCost(inputs) {
  const replicas = Math.max(1, Math.ceil(inputs.concurrentUsers / 20));
  const cpu = inputs.concurrentUsers <= 5 ? 0.25 : 0.5;
  const memory = inputs.concurrentUsers <= 5 ? 0.5 : 1;
  const seconds = HOURS_PER_MONTH * 3600;
  return replicas * seconds * (cpu * 0.000003 + memory * 0.000003);
}

function jobContainerCost(inputs, workload) {
  const fullHours = inputs.fullRunsPerWeek * WEEKS_PER_MONTH
    * workload.logicalStores;
  const incrementalHours = inputs.incrementalRunsPerDay * DAYS_PER_MONTH
    * workload.logicalStores * 0.25;
  const tagHours = workload.taggedImagesMonthly / 500;
  const workerHours = fullHours + incrementalHours + tagHours;
  return workerHours * 3600 * (2 * 0.000024 + 4 * 0.000003);
}

function postgresComponent(inputs, workload) {
  const small = inputs.concurrentUsers <= 5 && inputs.ownedStores === 1;
  const hourly = small ? 0.0286 : 0.1144;
  const sku = small ? "B1ms" : "B2s";
  const storageGb = Math.max(small ? 32 : 128, Math.ceil(workload.curatedGb * 4));
  return component("postgres", "Azure Database for PostgreSQL", "数据", {
    monthly: hourly * HOURS_PER_MONTH + storageGb * 0.15,
    sku: `${sku} + ${storageGb} GB`,
    basis: `$${hourly}/小时 × 730 + ${storageGb} GB × $0.15/GB月`,
    source: SOURCE_LINKS.postgres, confidence: "Medium", core: true,
  });
}

function paasComponents(inputs, workload) {
  const searchUnits = Math.max(1, Math.ceil(workload.indexGb / 15));
  const egressGb = Math.max(0,
    inputs.concurrentUsers * inputs.egressGbPerUser - 100);
  return [
    component("staticWeb", "Azure Static Web Apps", "应用", {
      monthly: 9, sku: "Standard", basis: "$9/应用月",
      source: SOURCE_LINKS.retail, confidence: "High", core: true,
    }),
    component("containerApps", "Container Apps API + Jobs", "计算", {
      monthly: apiContainerCost(inputs) + jobContainerCost(inputs, workload),
      sku: "Consumption",
      basis: "$0.000024/vCPU秒 + $0.000003/GiB秒；API 保底副本 + 爬取/打标任务时长模型",
      source: SOURCE_LINKS.containerApps, confidence: "Medium", core: true,
    }),
    postgresComponent(inputs, workload),
    component("blob", "Blob Storage 图片与原始数据", "存储", {
      monthly: workload.storageGb * 0.02208,
      sku: "Hot LRS",
      basis: `${workload.storageGb.toFixed(1)} GB × $0.02208/GB月；图片按内容去重`,
      source: SOURCE_LINKS.blob, confidence: "Medium", core: true,
    }),
    component("aiSearch", "Azure AI Search 向量检索", "检索", {
      monthly: searchUnits * 0.101 * HOURS_PER_MONTH,
      sku: `${searchUnits} × Basic Unit`,
      basis: `${workload.indexGb.toFixed(1)} GB 索引 ÷ 15 GB/Unit 向上取整 × $0.101/小时 × 730`,
      source: SOURCE_LINKS.search, confidence: "Medium",
    }),
    component("serviceBus", "Azure Service Bus", "任务编排", {
      monthly: 10, sku: "Standard", basis: "$10/月基础单元；前 13M 次操作包含",
      source: SOURCE_LINKS.serviceBus, confidence: "High", core: true,
    }),
    component("entra", "Microsoft Entra ID", "身份", {
      monthly: 0, sku: "Tenant basic app sign-in",
      basis: "沿用客户租户基础登录能力，增量许可按 $0；如需 Conditional Access，P1 另计 $7/用户月",
      source: SOURCE_LINKS.entra, confidence: "Medium", core: true,
    }),
    component("keyVault", "Azure Key Vault", "安全", {
      monthly: 0.03, sku: "Standard", basis: "按 10,000 次 secret 操作/月预留 × $0.03",
      source: SOURCE_LINKS.keyVault, confidence: "Medium", core: true,
    }),
    component("oneLake", "Microsoft Fabric + OneLake", "分析数据", {
      monthly: 2 * 0.18 * HOURS_PER_MONTH + workload.curatedGb * 0.03,
      sku: "2 CU + OneLake Hot",
      basis: `2 CU × $0.18/CU小时 × 730 + ${workload.curatedGb.toFixed(1)} GB × $0.03/GB月；仅存整理后的历史数据`,
      source: SOURCE_LINKS.fabric, confidence: "Medium",
    }),
    component("monitor", "Application Insights / Log Analytics", "可观测性", {
      monthly: 5 * 4.03, sku: "Analytics Logs 5 GB/月",
      basis: "5 GB/月 × $4.03/GB；用于 token、延迟、错误和重试追踪",
      source: SOURCE_LINKS.monitor, confidence: "Low",
    }),
    component("egress", "互联网出站流量", "网络", {
      monthly: egressGb * 0.12, sku: "Asia Premium Global Network",
      basis: `首 100 GB 免费；其后 ${egressGb.toFixed(1)} GB × $0.12/GB`,
      source: SOURCE_LINKS.bandwidth, confidence: "Low",
    }),
    ...aiComponents(inputs, workload),
  ];
}

function summarizeVersion(components, disabled, horizonMonths) {
  const excluded = new Set(disabled || []);
  const selected = components.map((row) => ({ ...row, enabled: !excluded.has(row.id) }));
  const steadyMonthly = selected.reduce((sum, row) =>
    sum + (row.enabled ? row.monthly : 0), 0);
  const onboarding = selected.reduce((sum, row) =>
    sum + (row.enabled ? row.onboarding : 0), 0);
  return {
    components: selected,
    steadyMonthly,
    onboarding,
    firstMonth: steadyMonthly + onboarding,
    horizonTotal: steadyMonthly * horizonMonths + onboarding,
  };
}

export function calculateEstimate(value = DEFAULT_INPUTS, disabled = {}) {
  const inputs = normalizeInputs({ ...DEFAULT_INPUTS, ...value });
  const workload = buildWorkload(inputs);
  return {
    inputs, workload,
    versions: {
      infra: summarizeVersion(
        infraComponents(inputs, workload), disabled.infra, inputs.retentionMonths,
      ),
      paas: summarizeVersion(
        paasComponents(inputs, workload), disabled.paas, inputs.retentionMonths,
      ),
    },
  };
}

export function formatMoney(usd, currency, usdToCny) {
  const value = currency === "CNY" ? usd * usdToCny : usd;
  return new Intl.NumberFormat(currency === "CNY" ? "zh-CN" : "en-US", {
    style: "currency", currency, minimumFractionDigits: 2, maximumFractionDigits: 2,
  }).format(value);
}
