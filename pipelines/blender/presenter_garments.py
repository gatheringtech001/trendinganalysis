"""Separate supplied clothing regions and bind wardrobe meshes to its real rig."""
import math

import bmesh
import bpy


def material(name, color):
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    shader = result.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Roughness"].default_value = .7
    return result


def region(source, face):
    center = face.center
    x, y, z = center
    if z > 1.405 or (z > 1.35 and y > .018) or z < .075 or (abs(x) > .278 and .66 < z < .805):
        return "Character"
    if z < .825 and abs(x) < .23:
        return "garment_trousers"
    arm_groups = {g.index for g in source.vertex_groups if g.name.startswith(("UpperArm_", "Forearm_", "Hand_"))}
    arm = sum(g.weight for i in face.vertices for g in source.data.vertices[i].groups if g.group in arm_groups)
    if arm / len(face.vertices) > .5 and z < 1.315:
        return "garment_top_sleeves"
    return "garment_top_body"


def split_character(source):
    source.shape_key_clear()
    labels = [region(source, face) for face in source.data.polygons]
    parts = {}
    for name in sorted(set(labels)):
        obj = source.copy()
        obj.data = source.data.copy()
        obj.name = name
        bpy.context.collection.objects.link(obj)
        mesh = bmesh.new()
        mesh.from_mesh(obj.data)
        bmesh.ops.delete(mesh, geom=[face for face in mesh.faces if labels[face.index] != name], context="FACES")
        mesh.to_mesh(obj.data)
        mesh.free()
        obj.data.update()
        assert len(obj.data.polygons) > 20, name
        parts[name] = obj
    assert sum(len(obj.data.polygons) for obj in parts.values()) == len(source.data.polygons)
    bpy.data.objects.remove(source, do_unlink=True)
    return parts


def bind(obj, rig, weights):
    obj.parent = rig
    modifier = obj.modifiers.new("WardrobeSkin", "ARMATURE")
    modifier.object = rig
    groups = {bone.name: obj.vertex_groups.new(name=bone.name) for bone in rig.data.bones}
    for vertex in obj.data.vertices:
        for name, value in weights(vertex.co).items():
            if value > 0:
                groups[name].add([vertex.index], value, "REPLACE")


def dress_weights(point):
    z = point.z
    stages = [("Hips", "Spine", 1.0, 1.08), ("Spine", "Chest", 1.15, 1.23),
              ("Chest", "Neck", 1.33, 1.38)]
    for lower, upper, start, end in stages:
        if z <= end:
            t = max(0, min(1, (z - start) / (end - start)))
            return {lower: 1 - t, upper: t}
    return {"Neck": 1}


def loft(name, rings, options):
    segments, subdivisions = 64, 5
    rows = []
    for lower, upper in zip(rings, rings[1:]):
        for step in range(subdivisions):
            t = step / subdivisions
            rows.append(tuple(a + (b - a) * t for a, b in zip(lower, upper)))
    rows.append(rings[-1])
    vertices = []
    for z, width, depth in rows:
        for i in range(segments):
            angle = i * math.tau / segments
            pleat = 1 + .025 * math.cos(angle * 12) * max(0, 1 - z)
            vertices.append((width * math.cos(angle) * pleat, depth * math.sin(angle) * pleat, z))
    faces = []
    for row in range(len(rows) - 1):
        for i in range(segments):
            a, b = row * segments + i, row * segments + (i + 1) % segments
            faces.append((a, b, b + segments, a + segments))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(options["material"])
    for face in mesh.polygons:
        face.use_smooth = True
    bind(obj, options["rig"], dress_weights)
    return obj


def build_wardrobe(parts, rig):
    jacket = parts["garment_top_body"].data.materials[0].copy()
    jacket.name = "JacketTexture"
    pants = jacket.copy()
    pants.name = "TrouserTexture"
    for name, obj in parts.items():
        if name == "Character":
            continue
        obj.data.materials.clear()
        obj.data.materials.append(pants if name == "garment_trousers" else jacket)
    cloth = material("GarmentColor", (1, 1, 1))
    bottom = material("BottomColor", (1, 1, 1))
    for part in ["body", "sleeves"]:
        obj = parts["garment_top_" + part].copy()
        obj.data = obj.data.copy()
        obj.name = "garment_dress_" + part
        obj.data.materials.clear()
        obj.data.materials.append(cloth)
        bpy.context.collection.objects.link(obj)
    loft("garment_dress", [(.11, .30, .19), (.38, .26, .17), (.7, .215, .145),
                          (.86, .19, .13), (.95, .158, .118)],
         {"material": cloth, "rig": rig})
    loft("garment_skirt", [(.11, .28, .19), (.4, .24, .16), (.7, .205, .14),
                          (.86, .19, .128), (.95, .158, .118)], {"material": bottom, "rig": rig})
