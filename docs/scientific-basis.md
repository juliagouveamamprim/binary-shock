# Scientific basis and visual interpretation

Binary Shock is a scientific visualization derived from the analytic intrabinary
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
factor and is not physical opacity.

The browser distinguishes static pressure fields from moving flow tracers. The
stellar and pulsar wind fields use the model's radial inverse-square pressure
laws. The Be decretion-disk volume uses the model's orientation, radial pressure
law, scale height, and vertical profile; its moving tracers use Keplerian
rotation. Volume brightness and opacity are contrast-compressed display choices,
not physical opacity or gas density. Visible particles are reserved for the
moving flow tracers.

The two spherical wind-pressure volumes use the same spatial display window,
opacity gain, and monotonic contrast mapping. Their relative brightness is
calculated from the IBSEn normalizations and inverse-square laws. The common
outer fade is only a viewing limit: neither analytic wind has a hard physical
edge there.

IBSEn does not prescribe a hard outer edge for this disk model. The viewer
therefore extends the visible volume beyond the pulsar's projected radius in the
disk plane and fades it smoothly. At the selected epoch the pulsar lies within
one model scale height of the disk midplane, so the overlap is physically
meaningful even though its visual strength is deliberately enhanced.

Exact values for every generated scene are written next to the GLB in its
`*.metadata.json` sidecar.
