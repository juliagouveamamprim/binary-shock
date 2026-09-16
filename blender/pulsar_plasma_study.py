"""Independent Blender look-development study for a luminous cyan pulsar.

Run with Blender 5.1 from the repository root:
    blender --background --python blender/pulsar_plasma_study.py

This is an artistic surface/atmosphere experiment, not an IBSEn output or a
physical neutron-star surface model. It intentionally excludes a radio beam,
flares, and explosive coronas.
"""

from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "blender" / "output"
OUT.mkdir(parents=True, exist_ok=True)


def node(tree, kind, name, location):
    item = tree.nodes.new(kind)
    item.label = name
    item.location = location
    return item


def wire(tree, a, output, b, input_name):
    tree.links.new(a.outputs[output], b.inputs[input_name])


def math_node(tree, operation, name, location, *values):
    item = node(tree, "ShaderNodeMath", name, location)
    item.operation = operation
    for index, value in enumerate(values):
        item.inputs[index].default_value = value
    return item


def make_coordinates(tree):
    tex = node(tree, "ShaderNodeTexCoord", "Stable 3D coordinates", (-1400, 150))
    warp = node(tree, "ShaderNodeTexNoise", "Warp the plasma pattern", (-1200, -160))
    warp.inputs["Scale"].default_value = 8.0
    warp.inputs["Detail"].default_value = 4.0
    warp.inputs["Roughness"].default_value = 0.7
    wire(tree, tex, "Generated", warp, "Vector")

    scale = node(tree, "ShaderNodeVectorMath", "Warp amplitude", (-990, -150))
    scale.operation = "SCALE"
    scale.inputs[3].default_value = 0.15
    wire(tree, warp, "Color", scale, 0)
    add = node(tree, "ShaderNodeVectorMath", "Distorted coordinates", (-780, 120))
    add.operation = "ADD"
    wire(tree, tex, "Generated", add, 0)
    wire(tree, scale, "Vector", add, 1)
    return add


def make_filaments(tree, coordinates):
    large_cell = node(tree, "ShaderNodeTexVoronoi", "Sweeping plasma arcs", (-550, 580))
    large_cell.feature = "DISTANCE_TO_EDGE"
    large_cell.inputs["Scale"].default_value = 15.0
    wire(tree, coordinates, "Vector", large_cell, "Vector")
    large_edge = node(tree, "ShaderNodeValToRGB", "Bright, broad arcs", (-310, 570))
    large_edge.color_ramp.elements[0].position = 0.020
    large_edge.color_ramp.elements[0].color = (1, 1, 1, 1)
    large_edge.color_ramp.elements[1].position = 0.11
    large_edge.color_ramp.elements[1].color = (0, 0, 0, 1)
    wire(tree, large_cell, "Distance", large_edge, "Fac")

    cell = node(tree, "ShaderNodeTexVoronoi", "Interlocking luminous threads", (-550, 300))
    cell.feature = "DISTANCE_TO_EDGE"
    cell.distance = "EUCLIDEAN"
    cell.inputs["Scale"].default_value = 42.0
    wire(tree, coordinates, "Vector", cell, "Vector")

    edge = node(tree, "ShaderNodeValToRGB", "Thin bright plasma threads", (-320, 310))
    edge.color_ramp.elements[0].position = 0.012
    edge.color_ramp.elements[0].color = (1, 1, 1, 1)
    edge.color_ramp.elements[1].position = 0.075
    edge.color_ramp.elements[1].color = (0, 0, 0, 1)
    wire(tree, cell, "Distance", edge, "Fac")

    fine = node(tree, "ShaderNodeTexNoise", "Granular bright microstructure", (-540, -30))
    fine.inputs["Scale"].default_value = 155.0
    fine.inputs["Detail"].default_value = 4.0
    fine.inputs["Roughness"].default_value = 0.82
    wire(tree, coordinates, "Vector", fine, "Vector")
    fine_ramp = node(tree, "ShaderNodeValToRGB", "Sparse white microstructure", (-300, -30))
    fine_ramp.color_ramp.elements[0].position = 0.46
    fine_ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    fine_ramp.color_ramp.elements[1].position = 0.72
    fine_ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    wire(tree, fine, "Fac", fine_ramp, "Fac")

    combined = math_node(tree, "MULTIPLY_ADD", "Threads plus grain", (-60, 170), 0.54, 0.0, 0.0)
    wire(tree, edge, "Color", combined, 0)
    combined.inputs[1].default_value = 0.54
    wire(tree, fine_ramp, "Color", combined, 2)
    combined_large = math_node(tree, "MULTIPLY_ADD", "Add sweeping arcs", (140, 310), 0.0, 0.48, 0.0)
    wire(tree, large_edge, "Color", combined_large, 0)
    wire(tree, combined, "Value", combined_large, 2)
    return combined_large, fine_ramp


def make_core_material():
    material = bpy.data.materials.new("Pulsar | living cyan plasma")
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()
    coords = make_coordinates(tree)
    threads, fine = make_filaments(tree, coords)

    broad = node(tree, "ShaderNodeTexNoise", "Subtle broad variation, not dark continents", (-550, -400))
    broad.inputs["Scale"].default_value = 5.2
    broad.inputs["Detail"].default_value = 4.0
    wire(tree, coords, "Vector", broad, "Vector")
    broad_map = node(tree, "ShaderNodeMapRange", "Keep the base luminous everywhere", (-300, -370))
    broad_map.inputs["From Min"].default_value = 0.2
    broad_map.inputs["From Max"].default_value = 0.8
    broad_map.inputs["To Min"].default_value = 0.16
    broad_map.inputs["To Max"].default_value = 0.85
    wire(tree, broad, "Fac", broad_map, "Value")

    white_mix = math_node(tree, "MULTIPLY_ADD", "Luminous detail", (130, 160), 0.0, 0.62, 0.0)
    wire(tree, threads, "Value", white_mix, 0)
    white_mix.inputs[1].default_value = 0.24
    wire(tree, broad_map, "Result", white_mix, 2)

    color = node(tree, "ShaderNodeValToRGB", "Deep cyan to white-hot emission", (350, 250))
    stops = color.color_ramp.elements
    stops.remove(stops[1])
    stops[0].position = 0.0
    stops[0].color = (0.005, 0.20, 0.46, 1)
    for position, rgba in [
        (0.48, (0.02, 0.52, 0.78, 1)),
        (0.68, (0.19, 0.85, 1.0, 1)),
        (0.86, (0.74, 0.98, 1.0, 1)),
        (1.0, (1, 1, 1, 1)),
    ]:
        stop = stops.new(position)
        stop.color = rgba
    wire(tree, white_mix, "Value", color, "Fac")

    layer = node(tree, "ShaderNodeLayerWeight", "Thin illuminated limb", (130, -380))
    layer.inputs["Blend"].default_value = 0.26
    rim = node(tree, "ShaderNodeMapRange", "Gentle limb contribution", (350, -260))
    rim.inputs["From Min"].default_value = 0.64
    rim.inputs["From Max"].default_value = 1.0
    rim.inputs["To Min"].default_value = 0.0
    rim.inputs["To Max"].default_value = 1.6
    wire(tree, layer, "Fresnel", rim, "Value")

    gain = math_node(tree, "MULTIPLY_ADD", "Emission strength from structure", (560, -80), 0.0, 1.8, 0.55)
    wire(tree, threads, "Value", gain, 0)
    add_rim = math_node(tree, "ADD", "Brighten the very edge", (780, -70), 0.0, 0.0)
    wire(tree, gain, "Value", add_rim, 0)
    wire(tree, rim, "Result", add_rim, 1)

    emission = node(tree, "ShaderNodeEmission", "Not a lit, painted sphere", (990, 200))
    wire(tree, color, "Color", emission, "Color")
    wire(tree, add_rim, "Value", emission, "Strength")
    output = node(tree, "ShaderNodeOutputMaterial", "Core surface", (1200, 200))
    wire(tree, emission, "Emission", output, "Surface")
    return material


def make_atmosphere_material():
    material = bpy.data.materials.new("Pulsar | fine optically thin atmosphere")
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()
    coords = make_coordinates(tree)
    threads, _ = make_filaments(tree, coords)
    layer = node(tree, "ShaderNodeLayerWeight", "Mostly near the limb", (100, -300))
    layer.inputs["Blend"].default_value = 0.28
    limb_only = node(tree, "ShaderNodeMapRange", "Restrict wisps to the outer limb", (290, -350))
    limb_only.inputs["From Min"].default_value = 0.70
    limb_only.inputs["From Max"].default_value = 0.97
    limb_only.inputs["To Min"].default_value = 0.0
    limb_only.inputs["To Max"].default_value = 1.0
    wire(tree, layer, "Fresnel", limb_only, "Value")
    density = math_node(tree, "MULTIPLY", "Sparse wisps", (380, -100), 0.0, 0.0)
    wire(tree, threads, "Value", density, 0)
    wire(tree, limb_only, "Result", density, 1)
    faint = math_node(tree, "MULTIPLY", "Keep the atmosphere translucent", (600, -90), 0.0, 0.14)
    wire(tree, density, "Value", faint, 0)

    transparent = node(tree, "ShaderNodeBsdfTransparent", "See through the shell", (630, -360))
    emission = node(tree, "ShaderNodeEmission", "Cyan-white atmospheric threads", (610, 180))
    emission.inputs["Color"].default_value = (0.30, 0.88, 1.0, 1)
    emission.inputs["Strength"].default_value = 2.3
    mix = node(tree, "ShaderNodeMixShader", "Only sparse emitting wisps", (850, 100))
    wire(tree, faint, "Value", mix, 0)
    wire(tree, transparent, "BSDF", mix, 1)
    wire(tree, emission, "Emission", mix, 2)
    output = node(tree, "ShaderNodeOutputMaterial", "Atmospheric shell", (1080, 100))
    wire(tree, mix, 0, output, "Surface")
    return material


def make_sphere(name, radius, material):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=224, ring_count=112, radius=radius)
    sphere = bpy.context.object
    sphere.name = name
    bpy.ops.object.shade_smooth()
    sphere.data.materials.append(material)
    return sphere


def setup_compositor(scene):
    comp = bpy.data.node_groups.new("Pulsar | local optical bloom", "CompositorNodeTree")
    comp.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    scene.compositing_node_group = comp
    source = node(comp, "CompositorNodeRLayers", "Render", (-300, 0))
    glare = node(comp, "CompositorNodeGlare", "Soft glow, no giant halo", (0, 0))
    glare.inputs["Type"].default_value = "Bloom"
    glare.inputs["Quality"].default_value = "High"
    glare.inputs["Threshold"].default_value = 1.0
    glare.inputs["Size"].default_value = 0.17
    glare.inputs["Strength"].default_value = 0.72
    output = node(comp, "NodeGroupOutput", "Final", (300, 0))
    wire(comp, source, "Image", glare, "Image")
    wire(comp, glare, "Image", output, "Image")


def build():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    make_sphere("Pulsar | emissive plasma", 1.0, make_core_material())

    bpy.ops.object.camera_add(location=(0, -5.2, 1.5))
    camera = bpy.context.object
    camera.name = "Study camera"
    camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 2.75

    scene = bpy.context.scene
    scene.camera = camera
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 64
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(OUT / "pulsar-plasma-study.png")
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = -0.30
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0, 0, 0, 1)
    background.inputs["Strength"].default_value = 0
    setup_compositor(scene)

    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "pulsar-plasma-study.blend"))
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    build()
