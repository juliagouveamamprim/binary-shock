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
binary scale. Its original equirectangular surface texture is an artistic proxy
for subtle thermal-emissivity variation, including a few sparse cool spots; it
is neither an observed neutron-star surface map nor an IBSEn output. The bodies
have no extended halo meshes or large
glow sprites. A compact, smoothly fading white glow remains immediately around
the pulsar surface; it and the low-intensity point lights are visibility cues,
not physical fields. Shock transparency is mapped from the normalized Doppler
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

The optional stellar and pulsar orbits are sampled directly from
`IBSEn Orbit.vector_s` and `Orbit.vector_p`, their barycentric Keplerian
positions. Because the frozen scene uses the current Be-star center as its
origin, both complete orbits and the barycenter are translated by the star's
current barycentric position. This changes only the coordinate origin: their
model-derived shapes, shared focus, and physical scales are preserved.

## Model-informed pulsar radio beam

The optional laminar beam is a **radio lighthouse-beam representation**, not a
gamma-ray jet and not a structure calculated by IBSEn. It is antipodal: the
viewer draws the same bundle along both directions of one magnetic axis. Each
bundle is assembled from thin, parallel, translucent sheets. This sheet
construction, the beam length, width, colors, and opacity are artistic choices
intended to suggest a luminous volume without pretending that the model
supplies a filled cone or a physical emissivity map.

For legibility, the displayed bundle has a constant, laser-like cross-section
only 13% of the enlarged pulsar radius and extends eight instantaneous binary
separations in each direction. Its endpoint therefore lies outside ordinary
camera framing, avoiding the false impression that the radio beam narrows or
terminates within the binary. These dimensions do not represent a calculated
opening angle or radio-emission distance. Eleven closely spaced sheets and
subtle longitudinal brightness striations create the laminar appearance while
the outer envelope remains narrow and parallel.

Its orientation is nevertheless tied to the system rather than chosen freely:

- The observer direction is exactly `IBS3D.unit_los`, the line of sight that
  IBSEn already uses to calculate the shock Doppler factor.
- Radio-polarization fits interpreted with the rotating-vector model give a
  favored geometry of `ζ = 134° ± 6°` between the spin axis and line of sight
  and `α = 137° ± 0.3°` between the magnetic and spin axes. Because axes are
  unoriented lines, these are visually equivalent to 46° and 43°,
  respectively. At closest passage, one magnetic pole is therefore 3° from the
  line of sight.
- The spin-axis position angle on the sky has not been measured. For this one
  reproducible realization, the spin axis is placed in the plane containing
  the IBSEn line of sight and the orbital normal, choosing the orientation with
  the smallest spin–orbit misalignment. This is an explicit assumption, not an
  observational result.
- Pulsar rotational phase is not part of the frozen IBSEn scene. The displayed
  snapshot is set at the closest magnetic-axis passage to the line of sight,
  the phase at which the radio pulse would be seen most directly. No time
  animation or pulse light curve is implied.

The derived line-of-sight, spin, magnetic, and counter-beam vectors, the input
angles, and all unconstrained choices are written to
`physical_model.pulsar_radio_beam_display` in the JSON sidecar. Future magnetic
field lines may reuse the same axis convention, but the magnetic-field method
currently present in IBSEn supplies a field-strength law with distance, not a
unique three-dimensional magnetospheric topology.

### Sources for this layer

- R. M. Shannon, S. Johnston & R. N. Manchester (2014),
  [*The kinematics and orbital dynamics of the PSR B1259−63/LS 2883 system
  from 23 yr of pulsar timing*](https://doi.org/10.1093/mnras/stt2123).
  Section 5.3 reports the favored radio-polarization angles and explicitly
  states that the pulsar spin-axis position angle on the sky is unconstrained.
- J. C. A. Miller-Jones et al. (2018),
  [*The geometric distance and binary orbit of PSR B1259−63*](https://doi.org/10.1093/mnras/sty1775).
  This provides the measured orbital orientation and discusses the equivalent
  46° pulsar-spin inclination to the line of sight.
- A. A. Abdo et al. (2011),
  [*Discovery of High-Energy Gamma-Ray Emission from the Binary System PSR
  B1259−63/LS 2883 Around Periastron with Fermi*](https://arxiv.org/abs/1103.4108).
  The beam layer is deliberately not labeled as this system's gamma-ray
  emission; the latter belongs to the binary-interaction context.
- P. Kaaret et al. (2024),
  [*Magnetic field geometry of the gamma-ray binary PSR B1259−63 revealed via
  X-ray polarization*](https://arxiv.org/abs/2409.16116).
  Its polarization constraint concerns the intrabinary shock region, so it is
  not used here as a measurement of the compact magnetospheric dipole axis.

Exact values for every generated scene are written next to the GLB in its
`*.metadata.json` sidecar.
