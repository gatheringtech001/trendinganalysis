import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { Texture, Vector3 } from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { createRigPose } from "./digitalHumanRig.js";
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
assert.deepEqual(jointRotation("Head", DEFAULT_LOOK), [0, 0, 0]);
assert.notDeepEqual(jointRotation("UpperArm_L", { ...DEFAULT_LOOK, ...POSES.editorial.values }), [0, 0, 0]);
assert.deepEqual(jointRotation("unknown", DEFAULT_LOOK), [0, 0, 0]);
assert.ok(jointRotation("Head", { ...DEFAULT_LOOK, head: 999 })[1] <= Math.PI / 4);
assert.deepEqual(jointRotation("Head", { ...DEFAULT_LOOK, head: NaN }), [0, 0, 0]);
assert.equal(accessoryVisible("accessory_earrings001", ["earrings"]), true);
assert.equal(accessoryVisible("accessory_earrings.001", []), false);
assert.equal(accessoryVisible("accessory_glasses_lens001", ["glasses"]), true);

const binary = readFileSync(new URL("../public/digital-human/mannequin.glb", import.meta.url));
assert.equal(binary.toString("ascii", 0, 4), "glTF");
assert.equal(binary.readUInt32LE(8), binary.length);
const gltf = JSON.parse(binary.toString("utf8", 20, 20 + binary.readUInt32LE(12)));
assert.match(gltf.asset.generator, /Blender/);
assert.ok(gltf.images?.length, "Preserve the supplied character texture");
assert.ok(gltf.skins?.some((skin) => skin.joints.length === 20), "Preserve the real 20-bone skeleton");
const nodes = new Map(gltf.nodes.map((node, index) => [node.name, { ...node, index }]));
for (const side of ["L", "R"]) {
  assert.ok(nodes.get(`UpperArm_${side}`).children.includes(nodes.get(`Forearm_${side}`).index));
  assert.ok(nodes.get(`Forearm_${side}`).children.includes(nodes.get(`Hand_${side}`).index));
  assert.ok(nodes.get(`Thigh_${side}`).children.includes(nodes.get(`Shin_${side}`).index));
}
for (const name of ["Character", "garment_top_body", "garment_top_sleeves", "garment_trousers", "garment_dress", "garment_skirt"]) {
  const node = nodes.get(name);
  assert.ok(node, `Missing independent region: ${name}`);
  assert.ok(node.skin !== undefined, `${name} must deform with the skeleton`);
}

// Geometry-only test; real textures and the rendered character are checked in Browser.
const loader = new GLTFLoader();
loader.register(() => ({ name: "GEOMETRY_TEST_TEXTURES", loadTexture: () => Promise.resolve(new Texture()) }));
const loaded = await loader.parseAsync(binary.buffer.slice(binary.byteOffset, binary.byteOffset + binary.byteLength), "");
const applyPose = createRigPose(loaded.scene);
const character = loaded.scene.getObjectByName("Character");
assert.ok(character.isSkinnedMesh);
const positions = character.geometry.attributes.position;
const samples = { hands: [], feet: [] };
applyPose(DEFAULT_LOOK);
for (let i = 0; i < positions.count; i++) {
  const point = new Vector3().fromBufferAttribute(positions, i);
  const entry = [i, character.applyBoneTransform(i, point.clone())];
  if (point.y < .065) samples.feet.push(entry);
  if (point.x > .29 && point.y > .69 && point.y < .80) samples.hands.push(entry);
}
assert.ok(samples.hands.length > 10 && samples.feet.length > 20);
applyPose({ ...DEFAULT_LOOK, leftArm: 30, leftElbow: 65 });
const movedDistance = ([index, neutral]) => character.applyBoneTransform(index, new Vector3().fromBufferAttribute(positions, index)).distanceTo(neutral);
assert.ok(Math.max(...samples.hands.map(movedDistance)) > .1, "Real hand vertices must move with the arm controls");
assert.ok(samples.feet.every((entry) => movedDistance(entry) < 1e-5), "Arm movement must leave the shoes fixed");
applyPose(DEFAULT_LOOK);
assert.ok(samples.hands.every((entry) => movedDistance(entry) < 1e-5), "Reset must restore the original pose without drift");
console.log("Digital human: garment isolation, catalog mapping, joint motion and bounds passed.");
