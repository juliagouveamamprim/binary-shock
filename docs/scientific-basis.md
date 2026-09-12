# Scientific basis and visual interpretation

Binary Shock is a scientific visualization derived from the analytic intrabinary
shock implemented by [IBSEn](https://github.com/juliagouveamamprim/IBSEn). It is
not presented as a three-dimensional hydrodynamic or magnetohydrodynamic
simulation.

## First prototype

- System preset: PSR B1259−63 (`psrb`)
- Epoch: 20 days after periastron
- Stellar disk pressure strength: `f_d = 100`
- Shock geometry: barycentric `IBS3D.r_vec`
- Surface color: Doppler factor `IBS3D.dopl` toward the model line of sight
- Coordinate unit: instantaneous star–pulsar separation
- Shock arclength cutoff: `s_max = 2`

The shock is the axisymmetric surface of revolution calculated by IBSEn. No
turbulence, clumps, or non-axisymmetric instabilities are added to the exported
geometry.

IBSEn 0.5.13 introduced barycentric point coordinates in `IBS3D.r_vec`.
The paper-reference scene preserves this native coordinate frame: the binary
barycenter is the origin, the bodies use `Orbit.vector_s` and `Orbit.vector_p`,
and the shock uses `IBS3D.r_vec`. Star-relative and pulsar-relative vectors are
still used where the physical pressure laws require distances from a body.

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

The browser distinguishes static pressure fields from flow tracers. The
stellar and pulsar wind fields use the model's radial inverse-square pressure
laws. The Be decretion-disk volume uses the model's orientation, radial pressure
law, scale height, and vertical profile. In the artistic preset, the disk
tracers use Keplerian rotation and the radial-wind tracers move outward. In the
paper-reference preset, all tracer positions are frozen: they communicate model
flow directions but are not simulated particles or a time-dependent solution.
Volume brightness and opacity are contrast-compressed display choices, not
physical opacity or gas density.

In the artistic preset, the two spherical wind-pressure volumes use the same
spatial display window, opacity gain, and monotonic contrast mapping. Their
relative brightness is calculated from the IBSEn normalizations and
inverse-square laws. The common outer fade is only a viewing limit: neither
analytic wind has a hard physical edge there.

The paper-reference preset instead uses one thin isobaric shell for each radial
wind. Each shell radius is the model distance from its source body to the
analytic shock apex: about 0.842 instantaneous separations for the stellar wind
and 0.158 for the pulsar wind in the current scene. Because both winds are
isotropic and their pressure laws are monotonic in radius, each sphere is a
surface of constant pressure for that wind and passes through the apex. The two
spheres therefore touch there and make the geometric pressure-balance location
easy to read. This is a viewer-derived reference construction, not an
additional IBSEn shock surface. The two shell values must not be interpreted as
equal contributions by themselves: the effective balance can also include the
decretion-disk pressure. Shell opacity and limb emphasis are display choices,
and this pressure representation is explicitly provisional.

IBSEn does not prescribe a hard outer edge for this disk model. The viewer
therefore extends the visible volume beyond the pulsar's projected radius in the
disk plane and fades it smoothly. At the selected epoch the pulsar lies within
one model scale height of the disk midplane, so the overlap is physically
meaningful even though its visual strength is deliberately enhanced.

In the paper-reference preset, four faint radial contour sets accompany the
filled disk-pressure volume. The fill is the primary representation: its color
intensity and opacity increase monotonically with the analytic pressure after a
documented contrast compression, while the radial cutoff and vertical Gaussian
profile make it fade smoothly. The browser samples that same scalar function
with three orthogonal slice stacks and weights their projected contribution by
viewing angle. This triplanar display prevents a stack of disk-parallel slices
from disappearing when viewed edge-on; it changes the sampling method, not the
pressure function. Because the analytic midplane pressure depends
only on radius and decreases monotonically, every midplane circle is an
isobar. Companion rings at `z = +H(r)` and `z = -H(r)` mark one local model
scale height, where the Gaussian vertical-pressure factor is
`exp(-1/2)`. Sparse radial guide curves connect those rings and expose the
model's flaring scale height in three dimensions. These deliberately subdued
lines are sampling guides,
not upper and lower physical boundaries: the Gaussian disk has no hard vertical
surface. Their logarithmic radial spacing and opacity are diagrammatic choices
that avoid moving particles and a false hard outer edge.

The optional stellar and pulsar orbits are sampled directly from
`IBSEn Orbit.vector_s` and `Orbit.vector_p`, their barycentric Keplerian
positions. They are displayed directly in the IBSEn barycentric frame and
scaled by the instantaneous star–pulsar separation. Their shared focus and
physical relative scale are preserved.

## Paper-reference preset

The paper-reference preset is a static, lower-decoration view of the same GLB
and JSON scene. Its first version displays only the Be star, the textured
display-scale neutron star, the three pressure fields, the analytic shock, both
orbits, and explicit geometric annotations. Stellar-wind, pulsar-wind, and
Keplerian-disk particle tracers are all excluded, as is the radio beam.

Its visual language is intentionally diagrammatic: a black background, thin
non-glowing orbit lines, small reference markers, unboxed labels, and a control
panel collapsed by default. Each label is a camera-facing sprite anchored at a
fixed 3D offset from the quantity it identifies. Body and reference-point
labels also receive a short connector defined in the same 3D coordinate system,
with endpoints fixed to the annotated quantity and its label. Its projected
direction therefore updates correctly as the user rotates the camera; it is not
a screen-space line-placement heuristic. Direction labels sit at their arrow
tips and do not need an additional connector.
The line of sight is dashed to distinguish an observer direction from the
coordinate axes and disk-normal vector.

The shock-apex marker uses the analytic IBSEn construction
`IBS3D.vec_p - IBS3D.symm_ax * IBS3D.r_pe`: starting at the barycentric pulsar
position, it moves by the pulsar-to-apex distance opposite the shock symmetry
axis. The first sampled surface ring lies close to, but not exactly at, this
point; its maximum offset is recorded in the metadata as a generation
diagnostic. The barycenter is the origin of the native IBSEn frame.

The `x` and `y` arrows are the Cartesian axes of that exported frame and begin
at the barycenter. The disk normal is read directly from `OpticalStar.n_disk`
and begins at the Be star. The line-of-sight arrow uses `IBS3D.unit_los`, the
direction used by IBSEn in its viewing-angle-dependent calculations, and begins
at the barycenter. Their directions are model quantities; their displayed
lengths, widths, colors, arrowheads, and labels are annotation choices and do
not encode magnitudes.

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
