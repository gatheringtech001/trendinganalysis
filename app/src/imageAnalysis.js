export const dimensionLabels = {
  product_category: "商品类别",
  silhouette_fit: "廓形与版型",
  design_elements: "设计元素",
  occasion: "穿着场景",
  composition: "画面构图",
  view_action: "视角与动作",
  selling_points: "卖点部位",
  scene: "拍摄场景",
  material_texture: "材质与纹理",
  color_pattern: "色彩与图案",
  visual_language: "视觉语言",
  styling: "搭配方式",
  lighting: "光线",
  model_state: "模特状态",
  graphic_overlay: "图文叠加",
};

export const dimensions = Object.keys(dimensionLabels);

const analysisTagLabels = {
  SOFT_DIFFUSED: "柔和漫射光", NATURAL_DAYLIGHT: "自然日光", HARD_DIRECT: "硬直射光",
  DIRECT_FLASH: "直接闪光", WARM_AMBIENT: "暖色环境光", COOL_AMBIENT: "冷色环境光",
  LOW_KEY: "低调光", HIGH_KEY: "高调光", MIXED_LIGHT: "混合光源",
  NO_MODEL: "无模特", STANDING_POSE: "站姿", WALKING_MOTION: "行走动态",
  SITTING_POSE: "坐姿", LOOKING_CAMERA: "看向镜头", LOOKING_AWAY: "视线离镜",
  FACE_CROPPED: "面部裁切", MIRROR_SELFIE: "镜面自拍", INTERACTING: "场景互动",
  NONE: "无图文叠加", TEXT_OVERLAY: "文字叠加", PRICE_PROMOTION: "价格促销信息",
  LOGO_WATERMARK: "Logo/水印", COLLAGE: "拼贴", FRAME_BORDER: "边框",
  STICKER_GRAPHIC: "贴纸图形", UI_SCREENSHOT: "界面截图",
  DRESSES: "连衣裙", TOPS: "上衣", SKIRTS: "半身裙", TROUSERS: "长裤",
  SHORTS: "短裤", SWIMWEAR: "泳装", OUTERWEAR: "外套", JEANS: "牛仔裤",
  JUMPSUITS: "连体裤", PLAYSUITS: "连身短裤", SETS: "套装", LINGERIE: "内衣",
  ACCESSORIES: "配饰", SHOES: "鞋履", OTHER: "其他", UNKNOWN: "未识别",
  BODYCON: "包身", FITTED: "修身", SLIM: "窄身", REGULAR: "常规",
  RELAXED: "宽松", OVERSIZED: "超宽松", A_LINE: "A字", STRAIGHT: "直筒",
  FLARED: "外扩", DRAPED: "垂坠", CORSETED: "束身",
  BACKLESS: "露背", CUTOUT: "镂空", HALTER: "挂脖", OFF_SHOULDER: "露肩",
  STRAPLESS: "无肩带", SPAGHETTI_STRAP: "细肩带", LACE_UP: "系带", SLIT: "开衩",
  RUFFLE: "荷叶边", TIE_DETAIL: "绑带细节", RUCHED: "抽褶", ASYMMETRIC: "不对称",
  SHEER_PANEL: "透视拼接", EMBELLISHED: "装饰点缀", PLEATED: "百褶",
  CASUAL: "休闲", GOING_OUT: "外出", PARTY: "派对", DATE_NIGHT: "约会",
  VACATION: "度假", BEACH: "海滩", POOL: "泳池", WEDDING_GUEST: "婚礼宾客",
  FESTIVAL: "音乐节", COMMUTE: "通勤", FORMAL: "正式场合", HOME: "居家",
  FULL_BODY: "全身", THREE_QUARTER: "四分之三身", HALF_BODY: "半身",
  CLOSE_UP: "近景", DETAIL: "细节特写", FLAT_LAY: "平铺", PRODUCT_ONLY: "仅商品",
  FRONT_VIEW: "正面", SIDE_VIEW: "侧面", BACK_VIEW: "背面", TURNING_BACK: "回身",
  WALKING: "行走", SITTING: "坐姿", STANDING: "站姿", MIRROR_SELFIE: "镜面自拍",
  HAIR_MOVED: "撩动头发", LOOKING_AWAY: "视线移开", INTERACTING_WITH_SCENE: "场景互动",
  NECKLINE: "领口", SHOULDERS: "肩部", BACK: "背部", WAIST: "腰部",
  WAIST_HIP: "腰臀", LEGS: "腿部", HEMLINE: "下摆", SLEEVES: "袖部",
  FABRIC_TEXTURE: "面料纹理", DRAPE: "垂坠感", PRINT: "印花", FULL_OUTFIT: "整体造型",
  STUDIO_NEUTRAL: "纯色影棚", MIRROR: "镜面", BEDROOM: "卧室", GARDEN: "花园",
  STREET: "街头", NIGHT: "夜景", ARCHITECTURE: "建筑空间", NATURE: "自然环境",
  KNIT: "针织", LACE: "蕾丝", SATIN_LIKE: "缎面质感", SILK_LIKE: "丝绸质感",
  DENIM: "牛仔", COTTON_LIKE: "棉质感", CHIFFON: "雪纺", MESH: "网纱",
  SEQUIN: "亮片", LEATHER_LIKE: "皮革质感", RIBBED: "罗纹", CROCHET: "钩织",
  COLOR_BLACK: "黑色", COLOR_WHITE: "白色", COLOR_GREY: "灰色", COLOR_BEIGE: "米色",
  COLOR_BROWN: "棕色", COLOR_RED: "红色", COLOR_PINK: "粉色", COLOR_ORANGE: "橙色",
  COLOR_YELLOW: "黄色", COLOR_GREEN: "绿色", COLOR_BLUE: "蓝色", COLOR_PURPLE: "紫色",
  COLOR_METALLIC: "金属色", COLOR_MULTI: "多色", PATTERN_SOLID: "纯色",
  PATTERN_FLORAL: "花卉图案", PATTERN_STRIPE: "条纹", PATTERN_CHECK: "格纹",
  PATTERN_ANIMAL: "动物纹", PATTERN_ABSTRACT: "抽象图案", PATTERN_GRAPHIC: "图形印花",
  ECOMMERCE_CLEAN: "简洁电商", EDITORIAL: "杂志大片", LIFESTYLE: "生活方式",
  SOCIAL_UGC: "社交UGC", ROMANTIC: "浪漫", VINTAGE: "复古", Y2K: "千禧风",
  MINIMAL: "极简", GLAMOROUS: "华丽", SOFT_LIGHT: "柔光", NATURAL_LIGHT: "自然光",
  DIRECT_FLASH: "直闪", WARM_TONE: "暖色调", COOL_TONE: "冷色调",
  SINGLE_ITEM: "单品展示", FULL_LOOK: "整套造型", LAYERED: "叠穿",
  ACCESSORIES_VISIBLE: "配饰可见", HANDBAG: "手提包", SHOES_VISIBLE: "鞋履可见",
  JEWELRY: "珠宝配饰", MATCHING_SET: "成套搭配", SWIM_COVERUP: "泳装罩衫",
};

const categoryLabels = {
  ...analysisTagLabels,
  "T-SHIRTS": "T恤", TEES: "T恤", SHIRTS: "衬衫", BLOUSES: "女式衬衫",
  "SHIRTS AND BLOUSES": "衬衫与女式衬衫", BODYSUITS: "连体上衣",
  "JUMPERS & CARDIGANS": "套头衫与开衫", JUMPERS: "套头衫", CARDIGANS: "开衫",
  KNITWEAR: "针织衫", SWEATERS: "毛衣", HOODIES: "连帽衫",
  "HOODIES & SWEATSHIRTS": "连帽衫与卫衣", SWEATSHIRTS: "卫衣",
  JOGGERS: "慢跑裤", LEGGINGS: "紧身裤", JORTS: "牛仔短裤", SKORTS: "裤裙",
  "TWO-PIECE SETS": "两件套", "KNIT SETS": "针织套装", "DENIM SETS": "牛仔套装",
  COORDS: "配套装", "CO-ORDS": "配套装", SUITS: "西装套装", BLAZERS: "西装外套",
  BEACHWEAR: "沙滩装", "BEACH COVER-UPS": "沙滩罩衫", TANKINI: "坦基尼泳装",
  NIGHTWEAR: "睡衣", SLEEPWEAR: "睡衣", NIGHTGOWNS: "睡裙", UNDERWEAR: "内裤",
  BRAS: "文胸", THONGS: "丁字裤", KNICKERS: "女式内裤", "LINGERIE SETS": "内衣套装",
  "LINGERIE BODYSUITS": "连体内衣", UNITARDS: "紧身连体衣", VESTS: "背心",
  BELTS: "腰带", HATS: "帽子", HEADBANDS: "发带", "HAIR ACCESSORIES": "发饰",
  "GLOVES & SCARVES": "手套与围巾", SCARVES: "围巾", SUNGLASSES: "太阳镜",
  "SOCKS & HOSIERY": "袜子与丝袜", "HOSIERY & SOCKS": "丝袜与袜子",
  RINGS: "戒指", BRACELETS: "手链", BRACELET: "手链", BANGLES: "手镯",
  "BRACELETS & CUFFS": "手链与手镯", KEYCHAINS: "钥匙扣", "TECH ACCESSORIES": "数码配件",
  HEELS: "高跟鞋", BOOTS: "靴子", FLATS: "平底鞋", SNEAKERS: "运动鞋",
  CLOTHING: "服装", GARMENT: "服装", SPECIALTY: "特殊品类", STORAGE: "收纳",
  SKIN: "护肤", FACE: "面部彩妆", EYES: "眼部彩妆", BROWS: "眉部彩妆",
  LIPS: "唇部彩妆", FRAGRANCE: "香水", "BEAUTY TOOLS": "美妆工具",
  "HAIR STYLING": "美发造型", "HAIR STYLING TOOLS": "美发工具",
  "GIFT CARDS": "礼品卡", "GIFT VOUCHER": "礼券", "FREE GIFTS": "赠品",
  DONATION: "捐赠", FEE: "费用", UNCLASSIFIED: "未分类",
};

const categoryPhraseLabels = {
  "MAXI & MIDI SKIRTS": "长款及中长款半身裙",
  "MAXI & MIDI DRESSES": "长款及中长款连衣裙",
  "ONE-PIECE SWIMWEAR": "连体泳装", "BIKINI SETS": "比基尼套装",
  "BAGS & PURSES": "包袋与手袋", JEWELLERY: "珠宝配饰",
  "JACKETS & COATS": "夹克与大衣", "SHORTS CO-ORDS": "短裤配套装",
  "SKIRT CO-ORDS": "半身裙配套装", "TROUSER COORDS": "长裤配套装",
};

const categoryModifiers = [
  ["MULTI WEAR", "多穿法"], ["BUTTERFLY", "蝴蝶款"], ["BATWING", "蝙蝠袖"],
  ["LITTLE BLACK", "小黑"], ["LONG SLEEVE", "长袖"], ["ONE SHOULDER", "单肩"],
  ["ONE SLEEVE", "单袖"], ["OPEN BACK", "露背"], ["HALTERNECK", "挂脖"],
  ["BANDEAU", "抹胸"], ["BARDOT", "露肩"], ["STRAPPY", "吊带"],
  ["CORSET", "束身"], ["PLUNGE", "深V"], ["HIGH NECK", "高领"],
  ["BODYCON", "包身"], ["A-LINE", "A字"], ["PLEATED", "百褶"],
  ["WRAP", "裹身"], ["FLARED", "喇叭"], ["WIDE LEG", "阔腿"],
  ["STRAIGHT LEG", "直筒"], ["BOOTLEG", "靴型"], ["LOW RISE", "低腰"],
  ["CARGO", "工装"], ["PARALLEL", "平行版型"], ["ROOMY", "宽松"],
  ["TAILORED", "剪裁"], ["FAUX LEATHER", "仿皮"], ["FAUX FUR", "仿皮草"],
  ["DENIM", "牛仔"], ["KNITTED", "针织"], ["KNIT", "针织"],
  ["WOVEN", "梭织"], ["LACE", "蕾丝"], ["SATIN", "缎面"],
  ["SEQUIN", "亮片"], ["PRINTED", "印花"], ["GRAPHIC", "图案"],
  ["BASIC", "基础款"], ["GOING OUT", "外出"], ["FORMAL", "正式"],
  ["SPORTS", "运动"], ["PLUS SIZE", "大码"], ["CROP", "短款"],
  ["BIKINI", "比基尼"], ["BOXER", "平角"], ["CAMI", "细肩带"],
  ["CAPRI", "七分"], ["JOGGER", "慢跑"], ["PYJAMA", "睡衣"],
  ["SHRUG", "披肩"], ["SLIP", "吊带"], ["SWIM", "泳装"],
  ["TANK", "背心"], ["TOTE", "托特"], ["TRENCH", "风衣"],
  ["PU", "聚氨酯仿皮"], ["FUR", "皮草"], ["HOT", "热辣款"],
  ["MAXI", "长款"], ["MIDI", "中长款"], ["MINI", "迷你"], ["MICRO", "超短"],
];

const categoryNouns = {
  DRESSES: "连衣裙", DRESS: "连衣裙", TOPS: "上衣", TOP: "上衣",
  SKIRTS: "半身裙", SKIRT: "半身裙", TROUSERS: "长裤", PANTS: "长裤",
  JEANS: "牛仔裤", SHORTS: "短裤", JACKETS: "夹克", JACKET: "夹克",
  COATS: "大衣", COAT: "大衣", CARDIGANS: "开衫", JUMPERS: "套头衫",
  BAGS: "包袋", BOTTOMS: "下装", CAPRIS: "七分裤", OVERALLS: "背带裤", SARONGS: "沙笼",
  EARRINGS: "耳环", NECKLACES: "项链", SWIMSUITS: "泳装", SWIMWEAR: "泳装",
  VEST: "背心", VESTS: "背心",
};

export function formatCategory(value) {
  const normalized = String(value || "UNKNOWN").trim().toUpperCase();
  if (categoryLabels[normalized]) return categoryLabels[normalized];
  if (categoryPhraseLabels[normalized]) return categoryPhraseLabels[normalized];
  const sheinCategory = normalized.match(/^SHEIN CATEGORY (\d+)$/);
  if (sheinCategory) return `SHEIN类目 ${sheinCategory[1]}`;
  let translated = normalized;
  for (const [english, chinese] of categoryModifiers) {
    const escaped = english.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    translated = translated.replace(new RegExp(`(?<![A-Z])${escaped}(?![A-Z])`, "g"), chinese);
  }
  for (const [english, chinese] of Object.entries(categoryNouns)) {
    translated = translated.replace(new RegExp(`\\b${english}\\b`, "g"), chinese);
  }
  return translated
    .replaceAll(" & ", "及")
    .replaceAll(" CO-ORDS", "配套装")
    .replace(/(?<=[\p{Script=Han}])\s+(?=[\p{Script=Han}])/gu, "");
}

export function formatAnalysisTag(value) {
  const normalized = String(value || "UNKNOWN").toUpperCase();
  return analysisTagLabels[normalized] || formatCategory(normalized);
}

export function formatConfidence(value) {
  return `${Math.round(Number(value || 0) * 100)}%`;
}
