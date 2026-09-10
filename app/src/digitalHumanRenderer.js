import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { accessoryVisible, garmentVisible, jointRotation } from "./digitalHuman.js";
import { disposeTree, makeStage } from "./digitalHumanScene.js";

function lights(scene) {
  scene.add(new THREE.HemisphereLight(0xf5f4ec, 0x5c6874, 1.1));
  const key = new THREE.DirectionalLight(0xfff0df, 2.8);
  key.position.set(-3, 5, 4);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.camera.left = key.shadow.camera.bottom = -3;
  key.shadow.camera.right = key.shadow.camera.top = 3;
  key.shadow.normalBias = .015;
  scene.add(key);
  const rim = new THREE.DirectionalLight(0xd8e7ff, 2.2);
  rim.position.set(3, 3, -2);
  scene.add(rim);
}

function dress(model, look) {
  model.rotation.y = look.turn * Math.PI / 180;
  model.traverse((node) => {
    if (node.name.startsWith("joint_")) {
      const delta = new THREE.Quaternion().setFromEuler(new THREE.Euler(...jointRotation(node.name, look)));
      node.quaternion.copy(node.userData.restRotation).multiply(delta);
    }
    if (node.name.startsWith("garment_")) node.visible = garmentVisible(node.name, look.outfit);
    if (node.name.startsWith("accessory_")) node.visible = accessoryVisible(node.name, look.accessories);
    if (node.material?.name === "GarmentColor") node.material.color.set(look.color);
    if (node.material?.name === "BottomColor") node.material.color.set(look.bottomColor);
  });
}

function download(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function createStudio(host, onError) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = .95;
  host.appendChild(renderer.domElement);
  renderer.domElement.setAttribute("aria-label", "数字人三维画布：拖动旋转，滚轮缩放");
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(34, 1, .05, 60);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.minDistance = 1.8;
  controls.maxDistance = 8;
  controls.maxPolarAngle = Math.PI / 2 + .03;
  const resetCamera = () => {
    camera.position.set(2.6, 1.9, 4.6);
    controls.target.set(0, .98, 0);
    controls.update();
  };
  resetCamera();
  lights(scene);
  const generator = new THREE.PMREMGenerator(renderer);
  const room = new RoomEnvironment();
  const environment = generator.fromScene(room);
  scene.environment = environment.texture;
  room.dispose();
  generator.dispose();
  const state = { disposed: false, model: null, stage: null, sceneKind: null };
  const resize = new ResizeObserver(() => {
    const { width, height } = host.getBoundingClientRect();
    if (!width || !height) return;
    renderer.setSize(width, height);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  });
  resize.observe(host);
  const contextLost = (event) => {
    event.preventDefault();
    renderer.setAnimationLoop(null);
    onError(new Error("3D 图形上下文已丢失，请重新载入页面。"));
  };
  renderer.domElement.addEventListener("webglcontextlost", contextLost);
  renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); });
  const ready = new GLTFLoader().loadAsync(`${import.meta.env.BASE_URL}digital-human/mannequin.glb`).then((gltf) => {
    if (state.disposed) { disposeTree(gltf.scene); return; }
    state.model = gltf.scene;
    state.model.traverse((node) => {
      if (node.name.startsWith("joint_")) node.userData.restRotation = node.quaternion.clone();
      if (node.isMesh) { node.castShadow = true; node.receiveShadow = true; }
    });
    scene.add(state.model);
  });
  return {
    ready, resetCamera,
    update(look) {
      if (state.disposed || !state.model) return;
      dress(state.model, look);
      if (state.sceneKind === look.scene) return;
      if (state.stage) { scene.remove(state.stage); disposeTree(state.stage); }
      state.sceneKind = look.scene;
      state.stage = makeStage(scene, look.scene);
      scene.add(state.stage);
    },
    async exportImage() {
      renderer.render(scene, camera);
      const blob = await new Promise((resolve) => renderer.domElement.toBlob(resolve, "image/png"));
      if (!blob) throw new Error("图片导出失败");
      download(blob, "fashion-scope-look.png");
    },
    async exportScene(look, product) {
      const { GLTFExporter } = await import("three/addons/exporters/GLTFExporter.js");
      scene.userData = { look, reference: product ? { store: product.store_id, id: product.product_id, title: product.title } : null,
        garmentType: "illustrative-template", generator: "Fashion Scope / Blender" };
      const data = await new GLTFExporter().parseAsync(scene, { binary: true, onlyVisible: true });
      download(new Blob([data], { type: "model/gltf-binary" }), "fashion-scope-look.glb");
    },
    dispose() {
      state.disposed = true;
      resize.disconnect();
      renderer.setAnimationLoop(null);
      renderer.domElement.removeEventListener("webglcontextlost", contextLost);
      controls.dispose();
      disposeTree(scene);
      environment.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}
