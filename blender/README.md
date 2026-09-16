# Pulsar look-development study

`output/pulsar-plasma-study.blend` and its PNG preview are an isolated material
study for the artistic branch. `pulsar_plasma_study.py` builds a cyan pulsar
from scratch: a warped network of bright procedural filaments, finer
granulation, broader emission variation, and restrained optical bloom. This is
not yet the final Sketchfab model.

Regenerate with Blender 5.1:

```bash
blender --background --python blender/pulsar_plasma_study.py
```

This is an isolated look-development experiment for the artistic branch. Open
the `.blend` files in Blender to inspect and edit the materials. Neither changes
the existing Three.js viewer or the IBSEn-derived binary geometry.

There are no corona meshes, solar flares, or beam in this study. The pattern,
colors, and enlarged radius are visual design choices, not an observed surface
map, magnetospheric simulation, or quantity calculated by IBSEn.

The Flatpak installation can be used in place of `blender`:

```bash
flatpak run org.blender.Blender --background --python "$PWD/blender/pulsar_plasma_study.py"
```

This material is still procedural in Blender. Exporting a GLB for Sketchfab
will require baking the visible variation to an emissive texture, then tuning
Sketchfab's bloom separately. That conversion is deliberately deferred until
the visual direction is approved.
