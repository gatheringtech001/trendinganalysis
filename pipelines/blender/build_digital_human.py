"""Adapt the user-supplied SANHUA presenter for Fashion Scope.
Run Blender --background --python pipelines/blender/build_digital_human.py --
--source path/to/presenter.glb. The source file is read only.
Garments are illustrative; no SKU reconstruction or cloth simulation is performed.
"""
import argparse
import hashlib
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from presenter_garments import bind, build_wardrobe, material, split_character

OUTPUT = Path(__file__).resolve().parents[2] / "app/public/digital-human"


def load_source(path):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(path))
    body = bpy.data.objects.get("SanhuaPresenter")
    if body is None or body.find_armature() is None:
        raise ValueError("Expected the skinned SanhuaPresenter source character")
    rig = body.find_armature()
    rig.animation_data_clear()
    for bone in rig.pose.bones:
        bone.matrix_basis.identity()
    for obj in list(bpy.context.scene.objects):
        if obj not in (body, rig):
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.context.view_layer.update()
    return split_character(body), rig


def accessory(name, center, options):
    if options.get("ring"):
        bpy.ops.mesh.primitive_torus_add(major_radius=options["scale"][0], minor_radius=.004,
                                       major_segments=48, minor_segments=12, location=center,
                                       rotation=(math.pi / 2, 0, 0))
    else:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=20, location=center)
        bpy.context.object.scale = options["scale"]
    obj = bpy.context.object
    obj.name = "accessory_" + name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    obj.data.materials.append(options["material"])
    for face in obj.data.polygons:
        face.use_smooth = True
    bind(obj, options["rig"], lambda _: {options["bone"]: 1})


def build_accessories(rig):
    gold = material("Brass", (.75, .48, .16))
    gold.node_tree.nodes.get("Principled BSDF").inputs["Metallic"].default_value = .75
    dark = material("Sunglasses", (.014, .018, .025))
    straw = material("Straw", (.65, .45, .24))
    leather = material("Leather", (.15, .055, .025))
    head = {"rig": rig, "bone": "Head"}
    for side in [-1, 1]:
        accessory("glasses_lens", (side * .045 + .015, -.147, 1.592),
                  {**head, "scale": (.044, .014, .027), "material": dark})
        accessory("earrings_hoop", (side * .112 + .008, -.03, 1.536),
                  {**head, "scale": (.022, 0, 0), "ring": True, "material": gold})
    accessory("glasses_bridge", (.015, -.151, 1.596),
              {**head, "scale": (.025, .008, .004), "material": gold})
    accessory("hat_brim", (0, .016, 1.778),
              {**head, "scale": (.23, .21, .012), "material": straw})
    accessory("hat_crown", (0, .016, 1.828),
              {**head, "scale": (.115, .104, .065), "material": straw})
    accessory("necklace", (0, -.082, 1.322),
              {"rig": rig, "bone": "Chest", "scale": (.033, 0, 0), "ring": True, "material": gold})
    hand = {"rig": rig, "bone": "Hand_L"}
    accessory("bag_handle", (.336, -.047, .652),
              {**hand, "scale": (.05, 0, 0), "ring": True, "material": gold})
    accessory("bag_body", (.336, -.047, .55),
              {**hand, "scale": (.096, .04, .085), "material": leather})


def prepare_preview():
    for obj in bpy.context.scene.objects:
        hidden = obj.name.startswith(("garment_dress", "garment_skirt", "accessory_"))
        obj.hide_set(hidden)
        obj.hide_render = hidden
    bpy.ops.mesh.primitive_plane_add(size=200)
    bpy.context.object.name = "PreviewGround"
    bpy.context.object.data.materials.append(material("PreviewGround", (.65, .65, .6)))
    bpy.ops.object.camera_add(location=(1.9, -4.3, 1.9))
    camera = bpy.context.object
    camera.rotation_euler = (Vector((0, 0, .95)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = 58
    bpy.context.scene.camera = camera
    for position, energy in [((-3, -4, 5), 500), ((3, 1, 4), 650)]:
        bpy.ops.object.light_add(type="AREA", location=position)
        light = bpy.context.object
        light.data.energy, light.data.shape, light.data.size = energy, "DISK", 5
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if not args.source.is_file():
        raise FileNotFoundError(args.source)
    source_hash = hashlib.sha256(args.source.read_bytes()).hexdigest()
    parts, rig = load_source(args.source)
    build_wardrobe(parts, rig)
    build_accessories(rig)
    bpy.context.scene["asset_note"] = "Adapted user-supplied Hi3D cartoon businesswoman from SANHUA presenter; original texture and 20-bone skin retained. Region-separated clothing; generated dress/skirt templates."
    bpy.context.scene["source_sha256"] = source_hash
    OUTPUT.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.export_scene.gltf(filepath=str(OUTPUT / "mannequin.glb"), export_format="GLB",
                             export_yup=True, export_animations=False)
    prepare_preview()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT / "mannequin.blend"))
    print(f"DIGITAL_HUMAN_ASSETS_OK source_sha256={source_hash}")


if __name__ == "__main__":
    main()
