#!/usr/bin/env python3
"""Build the first Blender blockout of the static 3D paper figure.

Run with Blender, from the repository root:

    blender --background --python blender/build_paper_figure.py

The script reads the presentation-neutral system state and shock GLB generated
by ``generator/generate_system_state.py``.  Scientific coordinates are kept in
the native barycentric frame; display radii, line widths, colors, label offsets,
and the orthographic camera are explicit diagrammatic choices made here.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = REPOSITORY_ROOT / "public/data/representative-system-state.json"
DEFAULT_BLEND = REPOSITORY_ROOT / "blender/output/paper-figure-blockout.blend"
DEFAULT_RENDER = REPOSITORY_ROOT / "public/previews/paper-figure-blockout.png"

# Diagrammatic display scales. They do not represent physical body radii or
# vector magnitudes.
STAR_DISPLAY_RADIUS = 0.14
PULSAR_DISPLAY_RADIUS = 0.075
APEX_MARKER_RADIUS = 0.028
BARYCENTER_MARKER_RADIUS = 0.024
LINE_RADIUS = 0.012
ARROW_SHAFT_RADIUS = 0.016
TEXT_SIZE = 0.062


COLORS = {
    "ink": (0.025, 0.035, 0.050, 1.0),
    "axis": (0.12, 0.14, 0.17, 1.0),
    "orbit": (0.10, 0.42, 0.13, 1.0),
    "orbit_plane": (0.35, 0.70, 0.32, 0.12),
    "star": (0.95, 0.08, 0.035, 1.0),
    "pulsar": (0.06, 0.32, 0.95, 1.0),
    "disk_outer": (1.0, 0.62, 0.10, 0.10),
    "disk_middle": (1.0, 0.45, 0.035, 0.13),
    "disk_inner": (1.0, 0.26, 0.015, 0.17),
    "shock": (0.20, 0.48, 0.95, 0.28),
    "shock_line": (0.045, 0.18, 0.50, 1.0),
    "disk_vector": (0.78, 0.49, 0.02, 1.0),
}


def _script_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--output-blend", type=Path, default=DEFAULT_BLEND)
    parser.add_argument("--output-render", type=Path, default=DEFAULT_RENDER)
    parser.add_argument("--resolution-x", type=int, default=1600)
    parser.add_argument("--resolution-y", type=int, default=1000)
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(arguments)


def _clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (
        bpy.data.curves,
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)


def _material(
    name: str,
    color: tuple[float, float, float, float],
    *,
    emission_strength: float = 0.0,
    roughness: float = 0.55,
) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = color
    nodes = material.node_tree.nodes
    principled = nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = color
    principled.inputs["Roughness"].default_value = roughness
    principled.inputs["Alpha"].default_value = color[3]
    if emission_strength > 0.0:
        emission_input = principled.inputs.get("Emission Color") or principled.inputs.get(
            "Emission"
        )
        if emission_input is not None:
            emission_input.default_value = color
        strength_input = principled.inputs.get("Emission Strength")
        if strength_input is not None:
            strength_input.default_value = emission_strength
    if color[3] < 1.0:
        if hasattr(material, "surface_render_method"):
            material.surface_render_method = "DITHERED"
        elif hasattr(material, "blend_method"):
            material.blend_method = "BLEND"
        material.use_transparency_overlap = False
    return material


def _assign_material(obj: bpy.types.Object, material: bpy.types.Material) -> None:
    obj.data.materials.clear()
    obj.data.materials.append(material)


def _sphere(
    name: str,
    location: Vector,
    radius: float,
    material: bpy.types.Material,
    *,
    segments: int = 64,
    rings: int = 32,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=rings,
        radius=radius,
        location=location,
    )
    obj = bpy.context.object
    obj.name = name
    bpy.ops.object.shade_smooth()
    _assign_material(obj, material)
    return obj


def _curve(
    name: str,
    points: list[Vector],
    material: bpy.types.Material,
    *,
    radius: float = LINE_RADIUS,
    cyclic: bool = False,
) -> bpy.types.Object:
    curve_data = bpy.data.curves.new(name, type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.resolution_u = 2
    curve_data.bevel_depth = radius
    curve_data.bevel_resolution = 3
    spline = curve_data.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for index, point in enumerate(points):
        spline.points[index].co = (*point, 1.0)
    spline.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, curve_data)
    bpy.context.collection.objects.link(obj)
    _assign_material(obj, material)
    return obj


def _arrow(
    name: str,
    start: Vector,
    end: Vector,
    material: bpy.types.Material,
    *,
    shaft_radius: float = ARROW_SHAFT_RADIUS,
    head_radius: float | None = None,
    head_length: float | None = None,
) -> list[bpy.types.Object]:
    direction = end - start
    length = direction.length
    if length <= 1e-9:
        raise ValueError(f"Arrow {name!r} has zero length.")
    unit = direction.normalized()
    head_length = head_length or min(0.11, 0.28 * length)
    head_radius = head_radius or 2.4 * shaft_radius
    shaft_end = end - unit * head_length
    shaft_vector = shaft_end - start

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=24,
        radius=shaft_radius,
        depth=shaft_vector.length,
        location=(start + shaft_end) * 0.5,
    )
    shaft = bpy.context.object
    shaft.name = f"{name} — shaft"
    shaft.rotation_mode = "QUATERNION"
    shaft.rotation_quaternion = Vector((0.0, 0.0, 1.0)).rotation_difference(
        shaft_vector.normalized()
    )
    _assign_material(shaft, material)

    bpy.ops.mesh.primitive_cone_add(
        vertices=32,
        radius1=head_radius,
        radius2=0.0,
        depth=head_length,
        location=end - unit * head_length * 0.5,
    )
    head = bpy.context.object
    head.name = f"{name} — head"
    head.rotation_mode = "QUATERNION"
    head.rotation_quaternion = Vector((0.0, 0.0, 1.0)).rotation_difference(unit)
    _assign_material(head, material)
    return [shaft, head]


def _orbit_plane(
    name: str,
    path: list[Vector],
    material: bpy.types.Material,
) -> bpy.types.Object:
    points = path[:-1] if (path[0] - path[-1]).length < 1e-6 else path
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(point) for point in points], [], [list(range(len(points)))])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    _assign_material(obj, material)
    return obj


def _disk_volume(
    center: Vector,
    normal: Vector,
    materials: list[bpy.types.Material],
) -> list[bpy.types.Object]:
    # Nested oblate shells provide a first qualitative pressure gradient:
    # warmer and more visible toward the star, faint toward the display edge.
    shells = [
        (0.78, 0.115, materials[0]),
        (0.58, 0.082, materials[1]),
        (0.39, 0.050, materials[2]),
    ]
    objects: list[bpy.types.Object] = []
    orientation = Vector((0.0, 0.0, 1.0)).rotation_difference(normal.normalized())
    for index, (radius, half_height, material) in enumerate(shells):
        obj = _sphere(
            f"Decretion disk pressure shell {index + 1}",
            center,
            1.0,
            material,
            segments=96,
            rings=48,
        )
        obj.scale = (radius, radius, half_height)
        obj.rotation_mode = "QUATERNION"
        obj.rotation_quaternion = orientation
        objects.append(obj)
    return objects


def _angle_arc(
    name: str,
    center: Vector,
    first: Vector,
    second: Vector,
    radius: float,
    material: bpy.types.Material,
    *,
    samples: int = 32,
) -> tuple[bpy.types.Object, Vector]:
    first = first.normalized()
    second = second.normalized()
    points = [
        center + first.slerp(second, index / (samples - 1)) * radius
        for index in range(samples)
    ]
    curve = _curve(name, points, material, radius=0.009)
    return curve, points[len(points) // 2]


def _text(
    name: str,
    body: str,
    location: Vector,
    camera: bpy.types.Object,
    material: bpy.types.Material,
    *,
    size: float = TEXT_SIZE,
    align: str = "CENTER",
) -> bpy.types.Object:
    curve_data = bpy.data.curves.new(name, type="FONT")
    curve_data.body = body
    curve_data.align_x = align
    curve_data.align_y = "CENTER"
    curve_data.size = size
    curve_data.extrude = 0.0
    curve_data.offset = 0.002
    obj = bpy.data.objects.new(name, curve_data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    direction = camera.location - location
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.to_track_quat("Z", "Y")
    _assign_material(obj, material)
    return obj


def _camera_for_composition(
    all_points: list[Vector],
    resolution_x: int,
    resolution_y: int,
) -> tuple[bpy.types.Object, Vector, Vector]:
    # Camera basis chosen so native +X projects left/down, +Y right/down,
    # and +Z up, matching the hand-drawn schematic's visual grammar.
    screen_right = Vector((-math.sqrt(0.5), math.sqrt(0.5), 0.0))
    screen_up = Vector((-0.18, -0.18, 0.967))
    screen_up.normalize()
    camera_back = screen_right.cross(screen_up).normalized()

    horizontal = [point.dot(screen_right) for point in all_points]
    vertical = [point.dot(screen_up) for point in all_points]
    horizontal_center = 0.5 * (min(horizontal) + max(horizontal))
    vertical_center = 0.5 * (min(vertical) + max(vertical))
    target = screen_right * horizontal_center + screen_up * vertical_center

    width = max(horizontal) - min(horizontal)
    height = max(vertical) - min(vertical)
    aspect = resolution_x / resolution_y
    ortho_scale = 1.38 * max(height, width / aspect)

    camera_data = bpy.data.cameras.new("Paper figure orthographic camera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = ortho_scale
    camera = bpy.data.objects.new("Paper figure orthographic camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = target + camera_back * 16.0
    camera.rotation_mode = "QUATERNION"
    # Explicitly set the camera's local X, Y, and Z axes in world space. This
    # keeps the framing calculation and Blender's actual camera roll identical.
    camera.rotation_quaternion = Matrix(
        (screen_right, screen_up, camera_back)
    ).transposed().to_quaternion()
    bpy.context.scene.camera = camera
    return camera, screen_right, screen_up


def _screen_offset(
    point: Vector,
    screen_right: Vector,
    screen_up: Vector,
    x: float,
    y: float,
) -> Vector:
    return point + screen_right * x + screen_up * y


def _import_shock(path: Path, material: bpy.types.Material) -> bpy.types.Object:
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    imported = [obj for obj in bpy.context.scene.objects if obj not in before and obj.type == "MESH"]
    if len(imported) != 1:
        raise RuntimeError(f"Expected one shock mesh in {path}, imported {len(imported)}.")
    shock = imported[0]
    shock.name = "Intrabinary shock — IBSEn surface"
    _assign_material(shock, material)
    for polygon in shock.data.polygons:
        polygon.use_smooth = True
    return shock


def _configure_scene(resolution_x: int, resolution_y: int) -> None:
    scene = bpy.context.scene
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    scene.render.resolution_x = resolution_x
    scene.render.resolution_y = resolution_y
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.world.color = (0.96, 0.965, 0.975)
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.96, 0.965, 0.975, 1.0)
    background.inputs["Strength"].default_value = 0.65

    scene.view_settings.look = "AgX - Medium High Contrast"

    bpy.ops.object.light_add(type="AREA", location=(3.5, 1.0, 6.0))
    key = bpy.context.object
    key.name = "Soft key light"
    key.data.energy = 650.0
    key.data.shape = "DISK"
    key.data.size = 5.0

    bpy.ops.object.light_add(type="AREA", location=(-4.0, -2.0, 3.0))
    fill = bpy.context.object
    fill.name = "Soft fill light"
    fill.data.energy = 350.0
    fill.data.size = 4.0


def build(args: argparse.Namespace) -> tuple[Path, Path]:
    state_path = args.state.resolve()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    geometry_path = (state_path.parent / state["shock"]["geometry_file"]).resolve()
    if not geometry_path.is_file():
        raise FileNotFoundError(f"Shock GLB not found: {geometry_path}")

    _clear_scene()
    _configure_scene(args.resolution_x, args.resolution_y)

    materials = {
        "ink": _material("Ink", COLORS["ink"], emission_strength=0.05),
        "axis": _material("Axes", COLORS["axis"], emission_strength=0.03),
        "orbit": _material("Orbit", COLORS["orbit"], emission_strength=0.05),
        "orbit_plane": _material("Orbital plane", COLORS["orbit_plane"]),
        "star": _material("Be star", COLORS["star"], emission_strength=0.14, roughness=0.35),
        "pulsar": _material("Pulsar", COLORS["pulsar"], emission_strength=0.18, roughness=0.28),
        "shock": _material("Shock surface", COLORS["shock"], roughness=0.28),
        "shock_line": _material("Shock annotations", COLORS["shock_line"], emission_strength=0.04),
        "disk_vector": _material("Disk annotations", COLORS["disk_vector"], emission_strength=0.04),
        "disk_outer": _material("Disk low relative pressure", COLORS["disk_outer"]),
        "disk_middle": _material("Disk medium relative pressure", COLORS["disk_middle"]),
        "disk_inner": _material("Disk high relative pressure", COLORS["disk_inner"]),
    }

    star = Vector(state["bodies"]["be_star"]["position"])
    pulsar = Vector(state["bodies"]["pulsar"]["position"])
    barycenter = Vector(state["bodies"]["barycenter"]["position"])
    apex = Vector(state["shock"]["apex"]["position"])
    disk_normal = Vector(state["decretion_disk"]["equatorial_plane_normal"])
    pulsar_orbit = [Vector(point) for point in state["orbit"]["pulsar_path"]]
    periastron = Vector(state["orbit"]["periastron"]["pulsar_position"])
    shock_reference = state["shock"]["reference_surface_point"]
    shock_point = Vector(shock_reference["scene_coordinates"])
    shock_normal = Vector(shock_reference["normal_unit_vector"])
    shock_meridian = [
        Vector(point)
        for point in state["shock"]["arclength_coordinate"]["meridian_scene_coordinates"]
    ]
    shock_opposite_meridian = [
        Vector(point)
        for point in state["shock"]["arclength_coordinate"][
            "opposite_meridian_scene_coordinates"
        ]
    ]
    shock_terminal_ring = [
        Vector(point) for point in state["shock"]["terminal_ring_scene_coordinates"]
    ]

    _orbit_plane("Orbital plane", pulsar_orbit, materials["orbit_plane"])
    _curve("Pulsar orbit", pulsar_orbit, materials["orbit"], radius=0.018, cyclic=True)
    _disk_volume(
        star,
        disk_normal,
        [materials["disk_outer"], materials["disk_middle"], materials["disk_inner"]],
    )
    shock_object = _import_shock(geometry_path, materials["shock"])
    _curve("Shock arclength s", shock_meridian, materials["shock_line"], radius=0.010)
    _curve(
        "Opposite shock meridian",
        shock_opposite_meridian,
        materials["shock_line"],
        radius=0.007,
    )
    _curve(
        "Shock terminal ring",
        shock_terminal_ring,
        materials["shock_line"],
        radius=0.010,
        cyclic=True,
    )

    _sphere("Be star (display scale)", star, STAR_DISPLAY_RADIUS, materials["star"])
    _sphere("Pulsar (display scale)", pulsar, PULSAR_DISPLAY_RADIUS, materials["pulsar"])
    _sphere("Shock apex", apex, APEX_MARKER_RADIUS, materials["ink"], segments=32, rings=16)
    _sphere(
        "Barycenter",
        barycenter,
        BARYCENTER_MARKER_RADIUS,
        materials["ink"],
        segments=32,
        rings=16,
    )
    _sphere("Periastron marker", periastron, 0.040, materials["orbit"], segments=32, rings=16)

    # Scientific and annotation vectors.
    axis_length = 0.72
    x_end = barycenter + Vector((axis_length, 0.0, 0.0))
    y_end = barycenter + Vector((0.0, axis_length, 0.0))
    z_end = barycenter + Vector((0.0, 0.0, axis_length))
    _arrow("X axis", barycenter, x_end, materials["axis"], shaft_radius=0.012)
    _arrow("Y axis", barycenter, y_end, materials["axis"], shaft_radius=0.012)
    _arrow("Z axis", barycenter, z_end, materials["axis"], shaft_radius=0.012)

    disk_normal_end = star + disk_normal.normalized() * 0.78
    _arrow("Disk normal", star, disk_normal_end, materials["disk_vector"])
    disk_flow = state["decretion_disk"]["keplerian_flow"]
    disk_flow_start = Vector(disk_flow["reference_point"]) * 0.48 + star * 0.52
    disk_flow_end = disk_flow_start + Vector(disk_flow["flow_unit_vector"]).normalized() * 0.48
    _arrow("Keplerian disk flow", disk_flow_start, disk_flow_end, materials["disk_vector"])

    motion_end = pulsar + Vector(state["orbit"]["current_pulsar_motion_unit_vector"]).normalized() * 0.52
    _arrow("Direction of pulsar motion", pulsar, motion_end, materials["orbit"])
    shock_normal_end = shock_point + shock_normal.normalized() * 0.46
    _arrow("Shock normal", shock_point, shock_normal_end, materials["shock_line"])
    _arrow(
        "r(s)",
        pulsar,
        shock_point,
        materials["ink"],
        shaft_radius=0.010,
        head_radius=0.028,
    )

    _, alpha_label_point = _angle_arc(
        "Disk inclination alpha_d",
        star,
        Vector((0.0, 0.0, 1.0)),
        disk_normal,
        0.34,
        materials["disk_vector"],
    )
    phi_data = state["shock"]["azimuthal_coordinate"]
    phi_axis = Vector(phi_data["axis_unit_vector"])
    phi_zero = Vector(phi_data["zero_direction_unit_vector"])
    phi_positive = Vector(phi_data["positive_direction_unit_vector"])
    phi_center = pulsar + phi_axis.normalized() * 0.48
    phi_second = (phi_zero * math.cos(math.radians(58.0)) + phi_positive * math.sin(math.radians(58.0))).normalized()
    _, phi_label_point = _angle_arc(
        "Shock azimuth phi",
        phi_center,
        phi_zero,
        phi_second,
        0.26,
        materials["shock_line"],
    )

    # Include the full orbit and all principal geometry when fitting the camera.
    shock_bounds = [
        shock_object.matrix_world @ Vector(corner) for corner in shock_object.bound_box
    ]
    fit_points = pulsar_orbit + shock_bounds + [
        star,
        pulsar,
        apex,
        periastron,
        disk_normal_end,
        motion_end,
        shock_normal_end,
        x_end,
        y_end,
        z_end,
    ]
    camera, screen_right, screen_up = _camera_for_composition(
        fit_points, args.resolution_x, args.resolution_y
    )

    labels = [
        ("Star label", "Star (S)", star, -0.20, 0.18, 0.074),
        ("Pulsar label", "Pulsar (P)", pulsar, 0.14, 0.14, 0.072),
        ("Barycenter label", "barycenter", barycenter, -0.08, -0.17, 0.052),
        ("Periastron label", "Periastron", periastron, -0.05, 0.14, 0.060),
        ("Apex label", "Apex (A), s = 0", apex, 0.02, 0.18, 0.058),
        ("Orbit label", "Pulsar orbit", pulsar_orbit[len(pulsar_orbit) // 5], 0.0, -0.13, 0.060),
        ("Disk label", "Decretion-disc equatorial plane", star, 0.05, 0.52, 0.058),
        ("Shock label", "Intrabinary shock", shock_meridian[-1], 0.12, 0.06, 0.060),
        ("Motion label", "Direction of pulsar motion", motion_end, 0.08, 0.10, 0.050),
        ("Disk normal label", "n_disc", disk_normal_end, 0.05, 0.05, 0.060),
        ("Disk flow label", "v_d", disk_flow_end, 0.05, 0.03, 0.060),
        ("Shock normal label", "n_IBS", shock_normal_end, 0.05, 0.04, 0.060),
        ("Radius label", "r(s)", (pulsar + shock_point) * 0.5, 0.05, 0.03, 0.060),
        ("Arclength label", "s", shock_meridian[len(shock_meridian) // 3], -0.05, 0.01, 0.064),
        ("Alpha label", "α_d", alpha_label_point, -0.01, 0.06, 0.064),
        ("Phi label", "φ", phi_label_point, 0.02, 0.04, 0.068),
        ("X label", "X", x_end, 0.0, 0.07, 0.064),
        ("Y label", "Y", y_end, 0.0, 0.07, 0.064),
        ("Z label", "Z", z_end, 0.0, 0.07, 0.064),
    ]
    for name, body, anchor, offset_x, offset_y, size in labels:
        _text(
            name,
            body,
            _screen_offset(anchor, screen_right, screen_up, offset_x, offset_y),
            camera,
            materials["ink"],
            size=size,
        )

    args.output_blend.parent.mkdir(parents=True, exist_ok=True)
    args.output_render.parent.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.filepath = str(args.output_render.resolve())
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend.resolve()))
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend.resolve()))
    print(f"Blend file: {args.output_blend.resolve()}")
    print(f"Rendered blockout: {args.output_render.resolve()}")
    return args.output_blend.resolve(), args.output_render.resolve()


if __name__ == "__main__":
    build(_script_args())
