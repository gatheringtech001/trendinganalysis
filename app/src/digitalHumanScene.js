import * as THREE from "three";

export function disposeTree(root) {
  const geometries = new Set();
  const materials = new Set();
  root.traverse((node) => {
    if (node.geometry) geometries.add(node.geometry);
    if (node.material) (Array.isArray(node.material) ? node.material : [node.material]).forEach((m) => materials.add(m));
  });
  geometries.forEach((value) => value.dispose());
  materials.forEach((value) => value.dispose());
}

function block(group, options) {
  const { position, scale, color, round = false } = options;
  const geometry = round ? new THREE.CylinderGeometry(1, 1, 1, 64) : new THREE.BoxGeometry(1, 1, 1);
  const object = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ color, roughness: .8 }));
  object.position.set(...position);
  object.scale.set(...scale);
  object.castShadow = true;
  object.receiveShadow = true;
  group.add(object);
  return object;
}

export function makeStage(scene, kind) {
  const colors = { studio: 0xe9e8e3, gallery: 0xe2ded4, street: 0xb9c2c5, coast: 0xc9e3e4 };
  scene.background = new THREE.Color(colors[kind]);
  scene.fog = new THREE.Fog(colors[kind], 8, 22);
  const group = new THREE.Group();
  group.name = "Stage";
  block(group, { position: [0, -.09, 0], scale: [30, .1, 30], color: kind === "coast" ? 0xd4c5ad : 0xcac9c3 });
  block(group, { position: [0, -.02, 0], scale: [.78, .07, .78], color: 0xece9e1, round: true });
  if (kind === "studio") {
    block(group, { position: [-1.4, 1.5, -1], scale: [.06, 3.2, 1.7], color: 0xf7f6ed });
    block(group, { position: [1.6, 1.1, -1.5], scale: [.75, 2.4, .1], color: 0xb8beb2 });
  }
  if (kind === "gallery") {
    for (const x of [-1.5, 1.5]) {
      block(group, { position: [x, 1.35, -1.8], scale: [.22, 2.8, .22], color: 0xf0eee8, round: true });
      block(group, { position: [x, .55, -.1], scale: [.5, 1.1, .5], color: 0xd6cdbb });
    }
    block(group, { position: [0, 1.7, -2.2], scale: [1.4, 1.3, .08], color: 0x3c5750 });
    block(group, { position: [.15, 1.8, -2.13], scale: [.38, .03, .38], color: 0xc3a575, round: true }).rotation.x = Math.PI / 2;
  }
  if (kind === "street") {
    block(group, { position: [0, -.03, -1.6], scale: [10, .08, .18], color: 0x707c82 });
    for (const x of [-2.5, -1.3, 1.3, 2.5]) {
      block(group, { position: [x, 1.7, -3], scale: [.9, 3.5, .7], color: 0x8c979b });
      block(group, { position: [x, 1.8, -2.62], scale: [.55, 1.8, .06], color: 0x394a50 });
    }
  }
  if (kind === "coast") {
    block(group, { position: [0, -.08, -8], scale: [30, .1, 10], color: 0x528c96 });
    block(group, { position: [0, .48, -2], scale: [6, .06, .1], color: 0xf5efe1 });
    for (const x of [-2.5, -1.5, -.5, .5, 1.5, 2.5]) {
      block(group, { position: [x, .2, -2], scale: [.06, .55, .06], color: 0xf5efe1 });
    }
  }
  return group;
}
