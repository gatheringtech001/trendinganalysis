import { Euler, Quaternion } from "three";
import { jointRotation } from "./digitalHuman.js";

export function createRigPose(model) {
  const bones = [];
  model.updateMatrixWorld(true);
  model.traverse((node) => {
    if (!node.isBone) return;
    const world = node.getWorldQuaternion(new Quaternion());
    bones.push({ node, rest: node.quaternion.clone(), world, inverse: world.clone().invert() });
  });
  if (!bones.some(({ node }) => node.name === "Head")) throw new Error("数字人缺少可用的人体骨骼");
  return (look) => {
    for (const { node, rest, world, inverse } of bones) {
      const delta = new Quaternion().setFromEuler(new Euler(...jointRotation(node.name, look)));
      // 将画布轴上的动作转换到原角色的骨骼局部轴，保留骨骼静止姿态。
      node.quaternion.copy(rest).multiply(inverse).multiply(delta).multiply(world);
    }
    model.updateMatrixWorld(true);
    model.traverse((node) => { if (node.isSkinnedMesh) node.skeleton.update(); });
  };
}
