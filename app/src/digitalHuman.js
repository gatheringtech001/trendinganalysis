export const OUTFITS = { trousers: "原款商务套装", dress: "西装领长裙", skirt: "西装 + 长裙" };
export const SCENES = { studio: "柔光影棚", gallery: "艺术展厅", street: "城市街景", coast: "海岸露台" };
export const ACCESSORIES = { glasses: "墨镜", earrings: "耳环", necklace: "项链", bag: "手袋", hat: "宽檐帽" };
export const JOINTS = {
  leftArm: { label: "左臂展开", min: -15, max: 70 },
  rightArm: { label: "右臂展开", min: -15, max: 70 },
  leftElbow: { label: "左肘弯曲", min: 0, max: 100 },
  rightElbow: { label: "右肘弯曲", min: 0, max: 100 },
  stride: { label: "前后步幅", min: -12, max: 12 },
  head: { label: "头部转向", min: -45, max: 45 },
};
const NEUTRAL = { leftArm: 0, rightArm: 0, leftElbow: 0, rightElbow: 0, stride: 0, head: 0 };
export const POSES = {
  neutral: { label: "自然站姿", values: NEUTRAL },
  editorial: { label: "杂志造型", values: { ...NEUTRAL, leftArm: 28, leftElbow: 65, head: -18 } },
  runway: { label: "秀场迈步", values: { ...NEUTRAL, stride: 9, leftElbow: 18, rightElbow: 12, head: 8 } },
  open: { label: "舒展双臂", values: { ...NEUTRAL, leftArm: 45, rightArm: 45, head: -12 } },
  greeting: { label: "抬手致意", values: { ...NEUTRAL, rightArm: 50, rightElbow: 85, head: 15 } },
};
export const DEFAULT_LOOK = {
  outfit: "trousers", scene: "studio", color: "#ffffff", bottomColor: "#ffffff",
  accessories: [], pose: "neutral", turn: -12, ...NEUTRAL,
};

export function garmentVisible(name, outfit) {
  if (!name.startsWith("garment_")) return true;
  if (outfit === "dress") return name.startsWith("garment_dress");
  return name.startsWith("garment_top") || name.startsWith(`garment_${outfit}`);
}

export function accessoryVisible(name, selected) {
  return selected.some((key) => name.startsWith(`accessory_${key}`));
}

function angle(look, key) {
  const value = Number.isFinite(look[key]) ? look[key] : 0;
  return Math.max(JOINTS[key].min, Math.min(JOINTS[key].max, value)) * Math.PI / 180;
}

export function jointRotation(name, look) {
  const rotations = {
    Head: [0, angle(look, "head"), 0],
    UpperArm_L: [0, 0, angle(look, "leftArm")],
    UpperArm_R: [0, 0, -angle(look, "rightArm")],
    Forearm_L: [-angle(look, "leftElbow"), 0, 0],
    Forearm_R: [-angle(look, "rightElbow"), 0, 0],
    Thigh_L: [angle(look, "stride"), 0, 0],
    Thigh_R: [-angle(look, "stride"), 0, 0],
  };
  return rotations[name] || [0, 0, 0];
}

export function inferOutfit(product) {
  const text = `${product.category || ""} ${product.title || ""}`.toLowerCase();
  if (/\b(bag|necklace|earring|sunglasses|hat|shoe|bikini|swimsuit)\b/.test(text)) return null;
  if (/\b(dress|dresses)\b/.test(text)) return "dress";
  if (/\b(skirt|skirts)\b/.test(text)) return "skirt";
  if (/\b(trousers|pants|jeans|top|tops|shirt|blouse|tee|t-shirt)\b/.test(text)) return "trousers";
  return null;
}
