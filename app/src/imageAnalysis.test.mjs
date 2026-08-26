import assert from "node:assert/strict";

import {
  formatAnalysisTag,
  formatCategory,
} from "./imageAnalysis.js";

assert.equal(formatCategory("TOPS"), "上衣");
assert.equal(formatCategory("Maxi & Midi Skirts"), "长款及中长款半身裙");
assert.equal(formatCategory("SHEIN category 8507"), "SHEIN类目 8507");
assert.equal(formatCategory("CAMI TOPS"), "细肩带上衣");
assert.equal(formatCategory("BARDOT JUMPERS"), "露肩套头衫");
assert.equal(formatCategory("BIKINI BOTTOMS"), "比基尼下装");
assert.equal(formatCategory("TANK TOPS"), "背心上衣");
assert.equal(formatCategory("TRENCH COATS"), "风衣大衣");
assert.equal(formatCategory("MULTI WEAR TOP"), "多穿法上衣");
assert.equal(formatCategory("NECKLACES"), "项链");
assert.equal(formatCategory("SWIMSUITS"), "泳装");
assert.equal(formatCategory("DENIM CAPRIS"), "牛仔七分裤");

assert.equal(formatAnalysisTag("BODYCON"), "包身");
assert.equal(formatAnalysisTag("ASYMMETRIC"), "不对称");
assert.equal(formatAnalysisTag("DATE_NIGHT"), "约会");
assert.equal(formatAnalysisTag("THREE_QUARTER"), "四分之三身");
assert.equal(formatAnalysisTag("TURNING_BACK"), "回身");
assert.equal(formatAnalysisTag("WAIST_HIP"), "腰臀");
assert.equal(formatAnalysisTag("STUDIO_NEUTRAL"), "纯色影棚");
assert.equal(formatAnalysisTag("SATIN_LIKE"), "缎面质感");
assert.equal(formatAnalysisTag("PATTERN_FLORAL"), "花卉图案");
assert.equal(formatAnalysisTag("SOCIAL_UGC"), "社交UGC");
assert.equal(formatAnalysisTag("MATCHING_SET"), "成套搭配");
assert.equal(formatAnalysisTag("UNKNOWN"), "未识别");

console.log("imageAnalysis translations passed");
