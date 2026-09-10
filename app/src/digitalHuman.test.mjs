import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DEFAULT_LOOK, POSES, accessoryVisible, garmentVisible, jointRotation, inferOutfit } from "./digitalHuman.js";

assert.equal(garmentVisible("garment_dress_strap001", "dress"), true);
assert.equal(garmentVisible("garment_top_sleeve", "dress"), false);
assert.equal(garmentVisible("garment_trousers_lower001", "trousers"), true);
assert.equal(garmentVisible("garment_top", "trousers"), true);
assert.equal(garmentVisible("garment_skirt", "skirt"), true);
assert.equal(garmentVisible("garment_trousers_upper", "skirt"), false);
assert.equal(inferOutfit({ title: "Black Midi Dress" }), "dress");
assert.equal(inferOutfit({ title: "Pleated skirt" }), "skirt");
assert.equal(inferOutfit({ category: "JEANS" }), "trousers");
assert.equal(inferOutfit({ title: "Leather bag" }), null);
assert.equal(inferOutfit({ title: "Top handle bag" }), null);
assert.equal(inferOutfit({ title: "Crop top" }), "trousers");
assert.deepEqual(jointRotation("joint_head", DEFAULT_LOOK), [0, 0, 0]);
assert.notDeepEqual(jointRotation("joint_shoulder_L", { ...DEFAULT_LOOK, ...POSES.editorial.values }), [0, 0, 0]);
assert.deepEqual(jointRotation("unknown", DEFAULT_LOOK), [0, 0, 0]);
assert.ok(jointRotation("joint_head", { ...DEFAULT_LOOK, head: 999 })[1] <= Math.PI / 4);
assert.deepEqual(jointRotation("joint_head", { ...DEFAULT_LOOK, head: NaN }), [0, 0, 0]);
assert.equal(accessoryVisible("accessory_earrings001", ["earrings"]), true);
assert.equal(accessoryVisible("accessory_earrings.001", []), false);
assert.equal(accessoryVisible("accessory_glasses_lens001", ["glasses"]), true);

const binary = readFileSync(new URL("../public/digital-human/mannequin.glb", import.meta.url));
assert.equal(binary.toString("ascii", 0, 4), "glTF");
assert.equal(binary.readUInt32LE(8), binary.length);
const gltf = JSON.parse(binary.toString("utf8", 20, 20 + binary.readUInt32LE(12)));
assert.match(gltf.asset.generator, /Blender/);
const nodes = new Map(gltf.nodes.map((node, index) => [node.name, { ...node, index }]));
for (const side of ["L", "R"]) {
  assert.ok(nodes.get(`joint_shoulder_${side}`).children.includes(nodes.get(`joint_elbow_${side}`).index));
  assert.ok(nodes.get(`joint_elbow_${side}`).children.includes(nodes.get(`joint_wrist_${side}`).index));
  assert.ok(nodes.get(`joint_hip_${side}`).children.includes(nodes.get(`joint_knee_${side}`).index));
}
assert.ok(nodes.has("garment_trousers_waist"));
assert.ok(gltf.meshes.length > 40);
console.log("Digital human: garment isolation, catalog mapping, joint motion and bounds passed.");
