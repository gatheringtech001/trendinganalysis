import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_INPUTS,
  calculateEstimate,
  formatMoney,
} from "./costEstimate.js";

test("two owned stores expand to eight logical stores", () => {
  const estimate = calculateEstimate({ ...DEFAULT_INPUTS, ownedStores: 2 });
  assert.equal(estimate.workload.logicalStores, 8);
  assert.equal(estimate.workload.baselineImages, 577662);
});

test("tagging and weekly report costs use measured AI baselines", () => {
  const estimate = calculateEstimate({
    ...DEFAULT_INPUTS,
    dailyIncrementPercent: 0,
    fullRetagPercent: 0,
    reportsPerWeek: 1,
  });
  const tagging = estimate.versions.paas.components.find((row) => row.id === "aiTagging");
  const reports = estimate.versions.paas.components.find((row) => row.id === "aiReports");
  assert.equal(tagging.monthly, 0);
  assert.ok(Math.abs(tagging.onboarding - 1312.33) < 0.02);
  assert.ok(Math.abs(reports.monthly - 74.36) < 0.02);
});

test("component removal immediately changes the selected total", () => {
  const baseline = calculateEstimate(DEFAULT_INPUTS);
  const withoutSearch = calculateEstimate(DEFAULT_INPUTS, { paas: ["aiSearch"] });
  const search = baseline.versions.paas.components.find((row) => row.id === "aiSearch");
  assert.ok(search.monthly > 0);
  assert.ok(Math.abs(
    baseline.versions.paas.steadyMonthly
      - withoutSearch.versions.paas.steadyMonthly
      - search.monthly,
  ) < 0.01);
});

test("one interactive user selects a smaller compute baseline than fifteen", () => {
  const one = calculateEstimate({ ...DEFAULT_INPUTS, concurrentUsers: 1 });
  const fifteen = calculateEstimate({ ...DEFAULT_INPUTS, concurrentUsers: 15 });
  const oneVm = one.versions.infra.components.find((row) => row.id === "vm");
  const fifteenVm = fifteen.versions.infra.components.find((row) => row.id === "vm");
  assert.equal(oneVm.sku, "D2as v5");
  assert.equal(fifteenVm.sku, "D4as v5");
  assert.ok(one.versions.infra.steadyMonthly < fifteen.versions.infra.steadyMonthly);
});

test("retention increases stored volume and storage cost", () => {
  const threeMonths = calculateEstimate({ ...DEFAULT_INPUTS, retentionMonths: 3 });
  const sixMonths = calculateEstimate({ ...DEFAULT_INPUTS, retentionMonths: 6 });
  assert.ok(sixMonths.workload.storageGb > threeMonths.workload.storageGb);
  const threeBlob = threeMonths.versions.paas.components.find((row) => row.id === "blob");
  const sixBlob = sixMonths.versions.paas.components.find((row) => row.id === "blob");
  assert.ok(sixBlob.monthly > threeBlob.monthly);
});

test("currency formatting remains explicit", () => {
  assert.equal(formatMoney(12.345, "USD", 7.12), "$12.35");
  assert.equal(formatMoney(12.345, "CNY", 7.12), "¥87.90");
});
