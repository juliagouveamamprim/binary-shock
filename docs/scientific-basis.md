# Scientific basis and visual interpretation

Binary Shock is a physics-informed visualization of the analytic intrabinary
shock implemented by [IBSEn](https://github.com/juliagouveamamprim/IBSEn). It is
not presented as a three-dimensional hydrodynamic or magnetohydrodynamic
simulation.

## First prototype

- System preset: PSR B1259−63 (`psrb`)
- Epoch: 20 days after periastron
- Stellar disk pressure strength: `f_d = 100`
- Shock geometry: star-relative `IBS3D.vec_sIBS`
- Surface color: Doppler factor `IBS3D.dopl` toward the model line of sight
- Coordinate unit: instantaneous star–pulsar separation
- Shock arclength cutoff: `s_max = 2`

The shock is the axisymmetric surface of revolution calculated by IBSEn. No
turbulence, clumps, or non-axisymmetric instabilities are added to the exported
geometry.

IBSEn 0.5.13 introduced barycentric point coordinates in `IBS3D.r_vec`.
Binary Shock uses the model's explicit `IBS3D.vec_sIBS` displacement vectors so
that the Be-star center remains the documented origin of every exported scene.

## Deliberate visual choices

The neutron star is enlarged because its physical radius is unresolvable on the
binary scale. Transparent stellar and pulsar halos are visibility cues, not
physical boundaries. Shock transparency is mapped from the normalized Doppler
factor and is not physical opacity. The Be decretion disk uses the orientation
and flaring prescription in the model, but has a finite display cutoff chosen
for composition.

Exact values for every generated asset are written next to the GLB in its
`*.metadata.json` sidecar.
