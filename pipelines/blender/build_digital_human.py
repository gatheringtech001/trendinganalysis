"""Build original articulated mannequin assets. Run with Blender --background --python.

Output: app/public/digital-human/{mannequin.glb,mannequin.blend}.
The garments are design templates, not reconstructions of catalog photographs.
"""
import math
from pathlib import Path

import bpy
from mathutils import Vector


OUTPUT = Path(__file__).resolve().parents[2] / "app/public/digital-human"
SEGMENTS = 48


def material(name, color, metallic=0, roughness=0.55):
    value = bpy.data.materials.new(name)
    value.diffuse_color = (*color, 1)
    value.use_nodes = True
    shader = value.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    return value


def finish(obj, name, mat, parent=None):
    obj.name = name
    if mat:
        obj.data.materials.append(mat)
    if obj.type == "MESH":
        for face in obj.data.polygons:
            face.use_smooth = True
    if parent:
        world = obj.matrix_world.copy()
        obj.parent = parent
        obj.matrix_world = world
    return obj


def ellipsoid(name, center, scale, mat, parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=20, location=center)
    obj = bpy.context.object
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj, name, mat, parent)


def joint(name, location, parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    bpy.context.view_layer.update()
    return finish(obj, name, None, parent)


def limb(name, start, end, radius, mat, parent):
    a, b = Vector(start), Vector(end)
    obj = ellipsoid(name, (a + b) / 2, (radius, radius, (b - a).length / 2 + radius * .4), mat)
    obj.rotation_euler = (b - a).to_track_quat("Z", "Y").to_euler()
    bpy.context.view_layer.update()
    return finish(obj, name, None, parent)


def loft(name, rings, mat, parent, x=0):
    vertices = []
    for z, width, depth in rings:
        vertices.extend((x + width * math.cos(i * math.tau / SEGMENTS),
                         depth * math.sin(i * math.tau / SEGMENTS), z)
                        for i in range(SEGMENTS))
    faces = []
    for row in range(len(rings) - 1):
        for i in range(SEGMENTS):
            a, b = row * SEGMENTS + i, row * SEGMENTS + (i + 1) % SEGMENTS
            faces.append((a, b, b + SEGMENTS, a + SEGMENTS))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return finish(obj, name, mat, parent)


def ring(name, center, radius, thickness, mat, parent, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=radius, minor_radius=thickness,
                                   major_segments=40, minor_segments=10, location=center,
                                   rotation=rotation)
    return finish(bpy.context.object, name, mat, parent)


def make_head(root, mats):
    head = joint("joint_head", (0, 0, 1.62), root)
    ellipsoid("neck", (0, 0, 1.58), (.058, .058, .10), mats["skin"], head)
    ellipsoid("face", (0, -.004, 1.76), (.105, .088, .143), mats["skin"], head)
    ellipsoid("hair_cap", (0, .026, 1.81), (.112, .087, .11), mats["hair"], head)
    ellipsoid("hair_bun", (0, .12, 1.81), (.074, .07, .075), mats["hair"], head)
    ellipsoid("nose", (0, -.088, 1.752), (.018, .025, .027), mats["skin"], head)
    for side in [-1, 1]:
        ellipsoid("eye", (side * .041, -.083, 1.781), (.016, .008, .008), mats["dark"], head)
        ellipsoid("ear", (side * .103, 0, 1.75), (.018, .025, .032), mats["skin"], head)
        ellipsoid("accessory_glasses_lens", (side * .044, -.102, 1.78), (.038, .012, .028), mats["dark"], head)
        ring("accessory_earrings", (side * .117, -.005, 1.694), .026, .005,
             mats["gold"], head, (math.pi / 2, 0, 0))
    limb("accessory_glasses_bridge", (-.02, -.108, 1.785), (.02, -.108, 1.785), .004, mats["gold"], head)
    ellipsoid("lips", (0, -.084, 1.702), (.026, .007, .006), mats["lip"], head)
    ellipsoid("accessory_hat_brim", (0, 0, 1.88), (.22, .20, .015), mats["straw"], head)
    ellipsoid("accessory_hat_crown", (0, 0, 1.94), (.115, .105, .075), mats["straw"], head)


def make_limbs(root, mats):
    for side, label in [(-1, "R"), (1, "L")]:
        shoulder = (side * .205, 0, 1.46)
        elbow = (side * .285, 0, 1.19)
        wrist = (side * .32, -.015, .94)
        arm = joint("joint_shoulder_" + label, shoulder, root)
        forearm = joint("joint_elbow_" + label, elbow, arm)
        hand = joint("joint_wrist_" + label, wrist, forearm)
        ellipsoid("shoulder", shoulder, (.071, .075, .073), mats["skin"], arm)
        limb("upper_arm", shoulder, elbow, .052, mats["skin"], arm)
        limb("forearm", elbow, wrist, .040, mats["skin"], forearm)
        ellipsoid("hand", (wrist[0], -.016, .893), (.034, .024, .065), mats["skin"], hand)
        limb("garment_top_sleeve", shoulder, (side * .245, 0, 1.33), .081, mats["cloth"], arm)
        hip, knee, ankle = (side * .09, 0, .93), (side * .105, 0, .53), (side * .11, 0, .12)
        thigh = joint("joint_hip_" + label, hip, root)
        shin = joint("joint_knee_" + label, knee, thigh)
        limb("thigh", hip, knee, .083, mats["skin"], thigh)
        limb("shin", knee, ankle, .055, mats["skin"], shin)
        ellipsoid("shoe", (side * .11, -.06, .075), (.057, .125, .065), mats["dark"], shin)
        loft("garment_trousers_upper", [(.95, .106, .134), (.76, .10, .12), (.52, .092, .104)], mats["pants"], thigh, hip[0])
        loft("garment_trousers_lower", [(.54, .093, .104), (.3, .096, .108), (.10, .102, .112)], mats["pants"], shin, knee[0])
        if label == "L":
            ring("accessory_bag_handle", (wrist[0], -.012, .83), .060, .009, mats["gold"], hand, (math.pi / 2, 0, 0))
            ellipsoid("accessory_bag_body", (wrist[0], -.012, .715), (.1, .042, .1), mats["bag"], hand)


def make_body(root, mats):
    loft("body", [(.87, .12, .09), (.96, .177, .114), (1.06, .14, .093),
                  (1.18, .115, .085), (1.34, .174, .109), (1.45, .18, .084),
                  (1.5, .125, .07), (1.56, .055, .052)], mats["skin"], root)
    loft("garment_dress", [(.65, .28, .174), (.84, .222, .148), (1.0, .184, .13),
                          (1.18, .133, .105), (1.33, .188, .127), (1.40, .176, .11)], mats["cloth"], root)
    for side in [-1, 1]:
        limb("garment_dress_strap", (side * .127, -.09, 1.38),
             (side * .142, 0, 1.49), .012, mats["cloth"], root)
    loft("garment_top", [(1.07, .159, .121), (1.2, .15, .12), (1.34, .197, .132),
                        (1.46, .204, .10), (1.52, .06, .063)], mats["cloth"], root)
    loft("garment_skirt", [(.64, .30, .18), (.80, .23, .151), (.96, .19, .14),
                          (1.08, .153, .115)], mats["pants"], root)
    loft("garment_trousers_waist", [(.89, .18, .132), (.98, .19, .141),
                                  (1.09, .154, .12)], mats["pants"], root)
    ring("accessory_necklace", (0, 0, 1.51), .078, .005, mats["gold"], root)


def prepare_blend_preview():
    for obj in bpy.context.scene.objects:
        hidden = (obj.name.startswith("garment_") and not obj.name.startswith("garment_dress"))
        hidden |= obj.name.startswith("accessory_") and not obj.name.startswith("accessory_earrings")
        obj.hide_set(hidden)
        obj.hide_render = hidden
    bpy.ops.mesh.primitive_plane_add(size=200)
    bpy.context.object.name = "PreviewGround"
    bpy.context.object.data.materials.append(material("PreviewGround", (.65, .65, .6)))
    bpy.ops.object.camera_add(location=(2.5, -4.3, 2.2))
    camera = bpy.context.object
    camera.rotation_euler = (Vector((0, 0, 1)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = 52
    bpy.context.scene.camera = camera
    for position, energy, size in [((-3, -4, 5), 500, 5), ((3, 1, 4), 650, 4)]:
        bpy.ops.object.light_add(type="AREA", location=position)
        light = bpy.context.object
        light.data.energy, light.data.shape, light.data.size = energy, "DISK", size
        light.rotation_euler = (Vector((0, 0, 1)) - light.location).to_track_quat("-Z", "Y").to_euler()
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 32
    scene.render.resolution_x, scene.render.resolution_y = 900, 1100
    scene.world.color = (.35, .35, .35)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.region_3d.view_perspective = "CAMERA"


def main():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    mats = {
        "skin": material("Skin", (.61, .39, .27), roughness=.68),
        "hair": material("Hair", (.032, .022, .02)),
        "dark": material("Obsidian", (.023, .028, .036), roughness=.26),
        "cloth": material("GarmentColor", (.27, .36, .26), roughness=.8),
        "pants": material("BottomColor", (.18, .23, .29), roughness=.82),
        "gold": material("Brass", (.75, .48, .16), metallic=.75, roughness=.25),
        "straw": material("Straw", (.69, .48, .25), roughness=.9),
        "lip": material("Lip", (.28, .085, .06)),
        "bag": material("Leather", (.19, .07, .035)),
    }
    root = joint("Mannequin", (0, 0, 0))
    make_body(root, mats)
    make_head(root, mats)
    make_limbs(root, mats)
    bpy.context.scene["asset_note"] = "Original procedural mannequin; articulated object rig; template garments, no cloth simulation."
    OUTPUT.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.export_scene.gltf(filepath=str(OUTPUT / "mannequin.glb"), export_format="GLB", export_yup=True)
    prepare_blend_preview()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / "mannequin.blend"))
    print(f"DIGITAL_HUMAN_ASSETS_OK: {OUTPUT}")


if __name__ == "__main__":
    main()
