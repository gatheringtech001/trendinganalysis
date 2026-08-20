export const stores = {
  "": "全部店铺",
  princess_polly: "Princess Polly",
  motel: "Motel Rocks",
  prettylittlething: "PrettyLittleThing",
  aloruh_shein: "Aloruh(shein)",
  aloruh_local: "Aloruh(local)",
};

export const storeColors = {
  princess_polly: "#315eea",
  motel: "#c76454",
  prettylittlething: "#4c254e",
  aloruh_shein: "#8b6f47",
  aloruh_local: "#2f766d",
};

export const formatNumber = (value) =>
  new Intl.NumberFormat("zh-CN").format(Number(value || 0));

export const formatPrice = (value) =>
  value == null ? "—" : `$${Number(value).toFixed(Number(value) % 1 ? 2 : 0)}`;

const apiBase = window.location.pathname === "/"
  ? ""
  : window.location.pathname.replace(/\/$/, "");

function queryString(params) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== "" && value !== false && value != null) search.set(key, value);
  });
  return search.toString();
}

async function request(path, options) {
  const response = await fetch(`${apiBase}${path}`, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.message || `请求失败：${response.status}`);
  return payload;
}

export const api = {
  reports: () => request("/api/reports"),
  report: (reportId) => request(`/api/reports/${encodeURIComponent(reportId)}`),
  reportFileUrl: (reportId) => `${apiBase}/api/reports/${encodeURIComponent(reportId)}/file`,
  generateReport: (detailedJobId) => request("/api/reports/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ detailed_job_id: detailedJobId }),
  }),
  reportGeneration: (jobId) => request(
    `/api/report-generation/${encodeURIComponent(jobId)}`,
  ),
  detailedAnalyses: () => request("/api/detailed-analysis"),
  summary: (store = "") => request(`/api/summary?${queryString({ store })}`),
  engagement: (store = "") => request(`/api/engagement?${queryString({ store })}`),
  analysis: (store = "") => request(`/api/analysis?${queryString({ store })}`),
  categories: (store = "") => request(`/api/categories?${queryString({ store })}`),
  products: (params) => request(`/api/products?${queryString(params)}`),
  images: (params) => request(`/api/images?${queryString(params)}`),
  imageDimensions: (params) => request(`/api/image-dimensions?${queryString(params)}`),
  startDetailedAnalysis: (payload) => request("/api/detailed-analysis", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }),
  detailedAnalysis: (jobId) => request(
    `/api/detailed-analysis/${encodeURIComponent(jobId)}`,
  ),
  reviewDetailedSection: (jobId, sectionId, decision, suggestion = "") => request(
    `/api/detailed-analysis/${encodeURIComponent(jobId)}/reviews/${encodeURIComponent(sectionId)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, suggestion }),
    },
  ),
  product: (store, productId) =>
    request(`/api/products/${encodeURIComponent(store)}/${encodeURIComponent(productId)}`),
  ask: (question) =>
    request("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }),
};
