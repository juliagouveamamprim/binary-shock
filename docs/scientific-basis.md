# Scientific basis — 3D paper figure (draft)

## Current scope

This branch develops a static three-dimensional explanatory figure for an
intrabinary-shock paper. Its composition is based on a schematic supplied by
the model author: it is intended to make the spatial relationships in that
schematic legible in three dimensions.

It is **not**, at this stage, a direct export of one particular IBSEn epoch or
a hydrodynamic simulation. The earlier interactive Three.js scene and its
artistic layers are not the scientific product documented here.

## Representative model state

The first implementation uses the IBSEn `psrb` preset at 100 days after
periastron, with `f_d = 100` and the shock cropped at `s = 1`. This is a
scientifically calculated representative realization selected as a starting
point for a composition similar to the hand-drawn schematic. The schematic
does not determine this preset or epoch, and the figure must not imply that it
does.

`generator/generate_system_state.py` exports the model state independently of
any renderer. Its JSON contains the barycentric bodies and orbit, disk model,
winds, shock apex and reference geometry, and the vectors and coordinates
needed by the paper annotations. Its companion GLB contains only the analytic
shock mesh, without a presentation-specific material.

## Intended content

The planned figure will show, in a fixed camera view:

- the Be star and neutron star;
- the barycenter, coordinate axes, pulsar orbit, direction of motion, and
  periastron reference;
- the decretion-disk equatorial plane, its normal vector, and a disk-flow
  direction;
- the intrabinary-shock surface, its apex, shock arclength coordinate, and
  normal direction;
- the geometrical angles and labels required by the paper.

## Scientific and graphical status

The initial spatial composition is schematic. As the scene is implemented,
each element will be documented as one of the following:

1. a quantity or relation supplied by IBSEn or by the analytic model;
2. a conventional geometrical construction used to explain the model; or
3. a graphical choice such as color, display scale, label placement, or camera
   framing.

Only the first category will be presented as a direct model result. The source
for every physical angle, vector, or dimensional relation used in the final
figure will be added here before the figure is treated as paper-ready.

## Documentation policy

This document will be expanded together with the figure-generation code. It
should describe the implemented figure, rather than preserve claims belonging
to the previous interactive visualization.
