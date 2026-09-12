#!/usr/bin/env python3
"""Export a scientific Binary Shock scene from IBSEn to GLB.

The generated scene is intended for the Binary Shock browser viewer. Positions
are expressed in units of the instantaneous star--pulsar separation. The shock
surface and its Doppler field come from IBSEn; display radii, materials, and
explanatory layers are explicitly documented as visual choices in the metadata
file.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from ibsen import IBS3D, OpticalStar, Orbit, Pulsar, Winds


DAY_SECONDS = 86_400.0
AU_CM = 1.496e13
PULSAR_VIEWING_ANGLE_DEG = 134.0
PULSAR_VIEWING_ANGLE_UNCERTAINTY_DEG = 6.0
PULSAR_MAGNETIC_OBLIQUITY_DEG = 137.0
PULSAR_MAGNETIC_OBLIQUITY_UNCERTAINTY_DEG = 0.3


@dataclass(frozen=True)
class SceneData:
    orbit: Orbit
    star: OpticalStar
    pulsar: Pulsar
    winds: Winds
    shock: IBS3D
    time_seconds: float
    separation_cm: float
    shock_vertices: np.ndarray
    shock_faces: np.ndarray
    doppler: np.ndarray
    doppler_normalized: np.ndarray
    shock_rgba: np.ndarray


def _grid_faces(n_phi: int, n_theta: int) -> np.ndarray:
    """Triangulate a periodic (azimuth, arclength) surface grid."""
    faces: list[tuple[int, int, int]] = []
    for phi_index in range(n_phi):
        next_phi = (phi_index + 1) % n_phi
        for theta_index in range(n_theta - 1):
            a = phi_index * n_theta + theta_index
            b = next_phi * n_theta + theta_index
            c = b + 1
            d = a + 1
            faces.append((a, b, d))
            faces.append((b, c, d))
    return np.asarray(faces, dtype=np.int64)


def _normalize_field(values: np.ndarray) -> tuple[np.ndarray, float, float]:
    finite = np.asarray(values, dtype=float)[np.isfinite(values)]
    if finite.size == 0:
        raise ValueError("The selected field contains no finite values.")
    low, high = np.percentile(finite, (2.0, 98.0))
    if np.isclose(low, high):
        low, high = float(finite.min()), float(finite.max() + 1.0)
    normalized = np.clip((values - low) / (high - low), 0.0, 1.0)
    return normalized, float(low), float(high)


def _rgba_from_doppler(normalized: np.ndarray) -> np.ndarray:
    rgba = matplotlib.colormaps["plasma"](normalized)
    # Preserve structure in faint regions while letting boosted regions read as
    # a luminous rim. Alpha is a display mapping, not a physical opacity.
    rgba[..., 3] = 0.34 + 0.58 * np.power(normalized, 0.65)
    return np.rint(rgba * 255.0).astype(np.uint8)


def calculate_scene(
    *,
    system: str = "psrb",
    days_after_periastron: float = 20.0,
    disk_strength: float = 100.0,
    s_max: float = 2.0,
    n_theta: int = 121,
    n_phi: int = 160,
) -> tuple[SceneData, dict[str, float]]:
    time_seconds = days_after_periastron * DAY_SECONDS
    orbit = Orbit(system)
    star = OpticalStar(sys_name=system, f_d=disk_strength)
    pulsar = Pulsar(b_ref=1.0, r_b_ref=1e13, r_p_ref=star.R_s)
    winds = Winds(orbit=orbit, star=star, pulsar=pulsar)
    shock = IBS3D(
        winds=winds,
        t_to_calculate_beta_eff=time_seconds,
        s_max=s_max,
        n=n_theta,
        n_phi=n_phi,
    )

    separation_cm = float(np.asarray(orbit.r(time_seconds)))
    # IBSEn >= 0.5.13 stores ``r_vec`` in barycentric coordinates.  Preserve
    # that native frame for the paper-reference scene.
    vertices_grid = np.asarray(shock.r_vec, dtype=float) / separation_cm
    doppler = np.asarray(shock.dopl, dtype=float)
    normalized, display_low, display_high = _normalize_field(doppler)
    rgba = _rgba_from_doppler(normalized)
    faces = _grid_faces(n_phi, n_theta)

    data = SceneData(
        orbit=orbit,
        star=star,
        pulsar=pulsar,
        winds=winds,
        shock=shock,
        time_seconds=time_seconds,
        separation_cm=separation_cm,
        shock_vertices=vertices_grid.reshape(-1, 3),
        shock_faces=faces,
        doppler=doppler,
        doppler_normalized=normalized,
        shock_rgba=rgba,
    )
    display_limits = {"percentile_02": display_low, "percentile_98": display_high}
    return data, display_limits


def _pbr_material(
    name: str,
    base_color: tuple[int, int, int, int],
    emissive: tuple[float, float, float],
    *,
    roughness: float,
    alpha_mode: str | None = None,
    double_sided: bool = False,
) -> trimesh.visual.material.PBRMaterial:
    return trimesh.visual.material.PBRMaterial(
        name=name,
        baseColorFactor=list(base_color),
        emissiveFactor=list(emissive),
        metallicFactor=0.0,
        roughnessFactor=float(roughness),
        alphaMode=alpha_mode,
        doubleSided=double_sided,
    )


def _set_material(mesh: trimesh.Trimesh, material: trimesh.visual.material.PBRMaterial) -> None:
    mesh.visual = trimesh.visual.TextureVisuals(uv=None, material=material)


def build_glb_scene(data: SceneData) -> tuple[trimesh.Scene, dict[str, float]]:
    separation = data.separation_cm
    star_radius = float(data.star.R_s / separation)
    star_position = np.asarray(data.orbit.vector_s(data.time_seconds), dtype=float) / separation
    pulsar_position = np.asarray(data.orbit.vector_p(data.time_seconds), dtype=float) / separation
    relative_pulsar_position = (
        np.asarray(data.orbit.vector_sp(data.time_seconds), dtype=float) / separation
    )

    shock_material = _pbr_material(
        "Shock — Doppler mapped",
        (255, 255, 255, 205),
        (0.12, 0.04, 0.30),
        roughness=0.32,
        alpha_mode="BLEND",
        double_sided=True,
    )
    shock_visual = trimesh.visual.TextureVisuals(uv=None, material=shock_material)
    # Trimesh exports this attribute as glTF COLOR_0 while retaining the PBR
    # material, so compatible viewers receive the scalar map and transparency.
    shock_visual.vertex_attributes = {"color": data.shock_rgba.reshape(-1, 4)}
    shock_mesh = trimesh.Trimesh(
        vertices=data.shock_vertices,
        faces=data.shock_faces,
        visual=shock_visual,
        process=False,
        metadata={
            "source": "IBSEn IBS3D.r_vec (barycentric)",
            "field": "IBSEn IBS3D.dopl",
            "coordinate_unit": "instantaneous star-pulsar separation",
        },
    )

    star_mesh = trimesh.creation.icosphere(subdivisions=4, radius=star_radius)
    star_mesh.apply_translation(star_position)
    _set_material(
        star_mesh,
        _pbr_material(
            "Be star",
            (255, 222, 158, 255),
            (1.0, 0.46, 0.12),
            roughness=0.62,
        ),
    )

    # A neutron star is far below the resolvable scale of this scene. This is
    # deliberately enlarged and recorded in the metadata sidecar.
    pulsar_display_radius = 0.026
    pulsar_mesh = trimesh.creation.icosphere(subdivisions=3, radius=pulsar_display_radius)
    pulsar_mesh.apply_translation(pulsar_position)
    _set_material(
        pulsar_mesh,
        _pbr_material(
            "Pulsar — display scale",
            (205, 235, 255, 255),
            (0.28, 0.68, 1.0),
            roughness=0.22,
        ),
    )

    disk_inner_radius = star_radius * 1.22
    disk_normal = np.asarray(data.star.n_disk, dtype=float)
    pulsar_height = float(np.dot(relative_pulsar_position, disk_normal))
    pulsar_in_plane = relative_pulsar_position - pulsar_height * disk_normal
    pulsar_in_plane_radius = float(np.linalg.norm(pulsar_in_plane))
    # IBSEn does not prescribe a hard disk edge. Extend the display volume
    # beyond the pulsar's projected disk-plane radius, then fade it smoothly in
    # the browser. This connects the rendered disk to the interaction region.
    disk_outer_radius = max(0.52, 1.35 * pulsar_in_plane_radius)
    disk_half_height = float(
        data.star.delta
        * disk_outer_radius
        * np.power(disk_outer_radius / star_radius, data.star.height_exp)
    )
    disk_height_at_pulsar_radius = float(
        data.star.delta
        * pulsar_in_plane_radius
        * np.power(pulsar_in_plane_radius / star_radius, data.star.height_exp)
    )

    scene = trimesh.Scene(base_frame="Binary Shock")
    scene.add_geometry(shock_mesh, geom_name="IBS shock surface", node_name="IBS shock surface")
    scene.add_geometry(star_mesh, geom_name="Be star", node_name="Be star")
    scene.add_geometry(pulsar_mesh, geom_name="Pulsar", node_name="Pulsar")

    display = {
        "star_radius_separation_units": star_radius,
        "pulsar_display_radius_separation_units": pulsar_display_radius,
        "disk_inner_radius_separation_units": disk_inner_radius,
        "disk_outer_radius_separation_units": disk_outer_radius,
        "disk_half_height_at_outer_edge_separation_units": disk_half_height,
        "pulsar_height_from_disk_plane_separation_units": pulsar_height,
        "pulsar_radius_in_disk_plane_separation_units": pulsar_in_plane_radius,
        "disk_half_height_at_pulsar_radius_separation_units": disk_height_at_pulsar_radius,
    }
    return scene, display


def _git_revision(ibsen_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(ibsen_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def _model_informed_pulsar_axes(unit_los: np.ndarray) -> dict[str, np.ndarray]:
    """Construct one documented pulsar-axis realization for the frozen scene.

    Radio-polarization fits constrain the spin/line-of-sight angle and magnetic
    obliquity, but not the spin-axis position angle on the sky.  We place the
    spin axis in the line-of-sight/orbital-normal plane, selecting the solution
    with the smallest spin--orbit misalignment.  The snapshot phase is then the
    closest approach of the magnetic axis to the line of sight.
    """
    line_of_sight = np.asarray(unit_los, dtype=float)
    line_of_sight /= np.linalg.norm(line_of_sight)
    orbital_normal = np.array([0.0, 0.0, 1.0])

    toward_orbital_normal = orbital_normal - np.dot(
        orbital_normal, line_of_sight
    ) * line_of_sight
    toward_orbital_normal /= np.linalg.norm(toward_orbital_normal)

    viewing_angle = np.deg2rad(PULSAR_VIEWING_ANGLE_DEG)
    spin_axis = (
        np.cos(viewing_angle) * line_of_sight
        + np.sin(viewing_angle) * toward_orbital_normal
    )
    spin_axis /= np.linalg.norm(spin_axis)

    toward_line_of_sight = line_of_sight - np.dot(
        line_of_sight, spin_axis
    ) * spin_axis
    toward_line_of_sight /= np.linalg.norm(toward_line_of_sight)

    magnetic_obliquity = np.deg2rad(PULSAR_MAGNETIC_OBLIQUITY_DEG)
    magnetic_axis = (
        np.cos(magnetic_obliquity) * spin_axis
        + np.sin(magnetic_obliquity) * toward_line_of_sight
    )
    magnetic_axis /= np.linalg.norm(magnetic_axis)

    return {
        "line_of_sight": line_of_sight,
        "orbital_normal": orbital_normal,
        "spin_axis": spin_axis,
        "magnetic_axis": magnetic_axis,
    }


def build_metadata(
    data: SceneData,
    display_limits: dict[str, float],
    display: dict[str, float],
    *,
    system: str,
    days_after_periastron: float,
    disk_strength: float,
    s_max: float,
    ibsen_root: Path,
) -> dict:
    doppler = data.doppler[np.isfinite(data.doppler)]
    orbit_times = np.linspace(-0.5 * data.orbit.T, 0.5 * data.orbit.T, 361)
    star_barycentric_now = np.asarray(
        data.orbit.vector_s(data.time_seconds), dtype=float
    )
    star_orbit_scene = (
        np.asarray(data.orbit.vector_s(orbit_times), dtype=float).T
        / data.separation_cm
    )
    pulsar_orbit_scene = (
        np.asarray(data.orbit.vector_p(orbit_times), dtype=float).T
        / data.separation_cm
    )
    barycenter_scene = np.zeros(3, dtype=float)
    star_position_scene = star_barycentric_now / data.separation_cm
    pulsar_position_scene = (
        np.asarray(data.orbit.vector_p(data.time_seconds), dtype=float)
        / data.separation_cm
    )
    apex_ring_scene = (
        np.asarray(data.shock.r_vec, dtype=float)[:, 0, :]
        / data.separation_cm
    )
    apex_scene = (
        np.asarray(data.shock.vec_p, dtype=float)
        - np.asarray(data.shock.symm_ax, dtype=float) * float(data.shock.r_pe)
    ) / data.separation_cm
    first_ring_apex_offset = float(
        np.max(np.linalg.norm(apex_ring_scene - apex_scene, axis=1))
    )
    pulsar_axes = _model_informed_pulsar_axes(data.shock.unit_los)
    closest_approach_deg = float(
        np.rad2deg(
            np.arccos(
                np.clip(
                    np.dot(
                        pulsar_axes["magnetic_axis"],
                        pulsar_axes["line_of_sight"],
                    ),
                    -1.0,
                    1.0,
                )
            )
        )
    )
    return {
        "title": "Binary Shock — PSR B1259−63 prototype",
        "scene_version": "0.2.0",
        "classification": "Scientific visualization derived from an analytic axisymmetric model",
        "physical_model": {
            "software": "IBSEn",
            "repository": "https://github.com/juliagouveamamprim/IBSEn",
            "git_revision": _git_revision(ibsen_root),
            "system_preset": system,
            "time_after_periastron_days": days_after_periastron,
            "time_after_periastron_seconds": data.time_seconds,
            "separation_cm": data.separation_cm,
            "separation_au": data.separation_cm / AU_CM,
            "effective_wind_momentum_ratio_beta": float(data.shock.beta),
            "shock_opening_angle_radians": float(data.shock.thetainf),
            "disk_pressure_strength_f_d": disk_strength,
            "shock_arclength_cutoff_s_max": s_max,
            "coordinate_origin": "Binary barycenter",
            "coordinate_unit": "instantaneous star-pulsar separation",
            "scene_positions": {
                "be_star": star_position_scene.tolist(),
                "pulsar": pulsar_position_scene.tolist(),
            },
            "reference_geometry": {
                "classification": "direct model geometry and coordinate annotations",
                "coordinate_origin": "Binary barycenter",
                "coordinate_unit": "instantaneous star-pulsar separation",
                "coordinate_axes": {
                    "origin_scene_coordinates": [0.0, 0.0, 0.0],
                    "x_unit_vector": [1.0, 0.0, 0.0],
                    "y_unit_vector": [0.0, 1.0, 0.0],
                    "meaning": "Cartesian axes of the exported IBSEn scene",
                },
                "disk_normal": {
                    "unit_vector": (
                        np.asarray(data.star.n_disk, dtype=float)
                        / np.linalg.norm(data.star.n_disk)
                    ).tolist(),
                    "source": "IBSEn OpticalStar.n_disk",
                    "meaning": "Normal to the Be-star decretion-disk midplane",
                },
                "line_of_sight": {
                    "unit_vector": pulsar_axes["line_of_sight"].tolist(),
                    "source": "IBSEn IBS3D.unit_los",
                    "meaning": (
                        "Line-of-sight direction used by IBSEn for viewing-angle "
                        "dependent calculations"
                    ),
                },
                "vector_display_note": (
                    "Arrow lengths are viewer scales; only their origins and directions "
                    "carry model meaning"
                ),
                "apex": {
                    "scene_coordinates": apex_scene.tolist(),
                    "source": "IBS3D.vec_p - IBS3D.symm_ax * IBS3D.r_pe",
                    "first_surface_ring_max_offset_scene_units": (
                        first_ring_apex_offset
                    ),
                    "meaning": (
                        "Analytic intrabinary-shock stagnation point where the "
                        "opposing pressures balance on the symmetry axis"
                    ),
                },
                "barycenter": {
                    "scene_coordinates": barycenter_scene.tolist(),
                    "source": "origin of the IBSEn barycentric coordinate frame",
                    "meaning": "Center of mass of the binary system",
                },
            },
            "orbit_display": {
                "source": "IBSEn Orbit.vector_s and Orbit.vector_p",
                "bodies": ["Be star", "pulsar"],
                "period_days": float(data.orbit.T / DAY_SECONDS),
                "eccentricity": float(data.orbit.e),
                "be_star_mass_g": float(data.orbit.M_s),
                "pulsar_mass_g": float(data.orbit.M_p),
                "be_star_barycentric_fraction": float(
                    data.orbit.M_p / data.orbit.M
                ),
                "samples": int(len(star_orbit_scene)),
                "coordinate_frame": (
                    "Native IBSEn barycentric frame scaled by the instantaneous "
                    "star-pulsar separation"
                ),
                "be_star_path_scene_coordinates": star_orbit_scene.tolist(),
                "pulsar_path_scene_coordinates": pulsar_orbit_scene.tolist(),
                "barycenter_scene_coordinates": barycenter_scene.tolist(),
                "current_be_star_scene_coordinates": star_position_scene.tolist(),
                "current_pulsar_scene_coordinates": (
                    pulsar_position_scene
                ).tolist(),
            },
            "pulsar_radio_beam_display": {
                "classification": "model-informed artistic layer",
                "emission_band": "radio",
                "line_of_sight_source": "IBSEn IBS3D.unit_los",
                "unit_line_of_sight_scene_coordinates": pulsar_axes[
                    "line_of_sight"
                ].tolist(),
                "orbital_normal_scene_coordinates": pulsar_axes[
                    "orbital_normal"
                ].tolist(),
                "spin_axis_scene_coordinates": pulsar_axes["spin_axis"].tolist(),
                "magnetic_axis_scene_coordinates": pulsar_axes[
                    "magnetic_axis"
                ].tolist(),
                "counter_beam_axis_scene_coordinates": (
                    -pulsar_axes["magnetic_axis"]
                ).tolist(),
                "radio_polarization_geometry": {
                    "spin_line_of_sight_angle_zeta_deg": PULSAR_VIEWING_ANGLE_DEG,
                    "spin_line_of_sight_uncertainty_deg": (
                        PULSAR_VIEWING_ANGLE_UNCERTAINTY_DEG
                    ),
                    "magnetic_spin_angle_alpha_deg": (
                        PULSAR_MAGNETIC_OBLIQUITY_DEG
                    ),
                    "magnetic_spin_uncertainty_deg": (
                        PULSAR_MAGNETIC_OBLIQUITY_UNCERTAINTY_DEG
                    ),
                    "closest_magnetic_line_of_sight_approach_deg": (
                        closest_approach_deg
                    ),
                    "source": {
                        "citation": (
                            "Shannon, Johnston & Manchester (2014), MNRAS 437, "
                            "3255–3264"
                        ),
                        "doi": "10.1093/mnras/stt2123",
                        "url": (
                            "https://academic.oup.com/mnras/article/437/4/3255/1001679"
                        ),
                    },
                },
                "unconstrained_choices": {
                    "spin_axis_sky_position_angle": (
                        "Not measured; placed in the line-of-sight/orbital-normal "
                        "plane to minimize spin–orbit misalignment"
                    ),
                    "rotational_phase": (
                        "Frozen at the closest magnetic-axis passage to the model "
                        "line of sight"
                    ),
                    "sheet_shape": (
                        "Parallel translucent laminae are an artistic depiction of a "
                        "radio lighthouse beam, not an IBSEn-calculated emissivity volume"
                    ),
                },
                "visual_geometry": {
                    "lamina_count": 11,
                    "length_each_direction_separation_units": 8.0,
                    "bundle_radius_pulsar_display_radii": 0.13,
                    "cross_section": "constant along the displayed length",
                    "palette": (
                        "cyan with a near-white cyan core and longitudinal "
                        "brightness striations"
                    ),
                    "endpoint": (
                        "Placed far outside the binary framing so the beam crosses the "
                        "viewport without a visible terminal cap"
                    ),
                    "scale_note": (
                        "Length and width are artistic display scales and do not encode "
                        "a calculated radio-emission distance or opening angle"
                    ),
                },
            },
            "flow_model": {
                "stellar_polar_wind": {
                    "geometry": "isotropic radial flow",
                    "constant_velocity_cm_s": float(data.star.v_polar_wind),
                    "pressure_normalization_f_w": float(data.star.f_w),
                    "pressure_reference_radius_cm": float(data.star.R_s),
                    "pressure_radial_power_law_index": 2.0,
                },
                "pulsar_wind": {
                    "geometry": "isotropic radial flow",
                    "pressure_normalization_f_p": float(data.pulsar.f_p),
                    "pressure_reference_radius_cm": float(data.pulsar.r_p_ref),
                    "pressure_radial_power_law_index": 2.0,
                },
                "decretion_disk": {
                    "normal_scene_coordinates": np.asarray(
                        data.star.n_disk, dtype=float
                    ).tolist(),
                    "velocity_model": "Keplerian rotation in the disk plane",
                    "pressure_normalization_f_d": float(data.star.f_d),
                    "pressure_radial_power_law_index": float(data.star.np_disk),
                    "scale_height_ratio_at_stellar_surface": float(data.star.delta),
                    "scale_height_exponent": float(data.star.height_exp),
                    "vertical_pressure_profile": str(data.star.vert_prof),
                    "pulsar_height_from_disk_plane_separation_units": display[
                        "pulsar_height_from_disk_plane_separation_units"
                    ],
                    "pulsar_radius_in_disk_plane_separation_units": display[
                        "pulsar_radius_in_disk_plane_separation_units"
                    ],
                    "scale_height_at_pulsar_radius_separation_units": display[
                        "disk_half_height_at_pulsar_radius_separation_units"
                    ],
                },
            },
        },
        "shock_surface": {
            "vertices": int(len(data.shock_vertices)),
            "triangles": int(len(data.shock_faces)),
            "color_field": "Doppler factor toward the IBSEn line of sight",
            "field_min": float(doppler.min()),
            "field_max": float(doppler.max()),
            "display_normalization": {
                "method": "linear clipping between percentiles 2 and 98",
                **display_limits,
            },
            "colormap": "matplotlib plasma",
        },
        "visual_interpretation": {
            **display,
            "shock_alpha": "Display mapping derived from normalized Doppler factor; not physical opacity",
            "body_lighting": (
                "Low-intensity browser point lights are artistic visibility cues; "
                "no extended stellar or pulsar halo is exported; the browser adds "
                "only a compact, smoothly fading white glow around the pulsar surface"
            ),
            "pulsar_scale": "Strongly enlarged; a physical neutron-star radius is unresolved at this scale",
            "pulsar_surface_texture": (
                "Original artistic thermal-emissivity texture with subtle cool mottling "
                "and a few sparse low-emissivity spots; not an observed surface map or "
                "an IBSEn output"
            ),
            "pulsar_radio_beam": (
                "Optional antipodal radio-beam layer aligned with a model-informed "
                "magnetic axis. Its orientation uses the IBSEn line of sight and "
                "published radio-polarization angles; its laminar sheet geometry, "
                "unmeasured sky azimuth, and frozen rotational phase are documented "
                "visual choices"
            ),
            "star_orbit": (
                "Model-derived barycentric path in the native IBSEn coordinate frame"
            ),
            "pulsar_orbit": (
                "Model-derived barycentric path shown in the same native frame and "
                "physical scale as the Be-star orbit"
            ),
            "pressure_fields": (
                "Smooth browser volumes use the IBSEn pressure laws with contrast compression; "
                "both winds share one monotonic brightness mapping and spatial display window; "
                "brightness and opacity are display mappings, not gas density or physical opacity"
            ),
            "disk_geometry": (
                "Diffuse browser volume sampled from the IBSEn radial pressure and vertical "
                "scale-height laws; no hard disk surface is stored in the GLB"
            ),
            "disk_extent": (
                "IBSEn supplies no hard outer edge; the display radius is 1.35 times the "
                "pulsar's projected disk-plane radius and fades smoothly at the edge"
            ),
            "turbulence": "None added; the exported shock retains the axisymmetric IBSEn geometry",
        },
    }


def render_preview(data: SceneData, output: Path) -> None:
    """Render a lightweight QA preview for inspecting the exported geometry."""
    grid = data.shock_vertices.reshape(data.shock.n_phi, data.shock.n, 3)
    rgba = data.shock_rgba.astype(float) / 255.0
    star_radius = float(data.star.R_s / data.separation_cm)
    star_position = (
        np.asarray(data.orbit.vector_s(data.time_seconds)) / data.separation_cm
    )
    pulsar_position = (
        np.asarray(data.orbit.vector_p(data.time_seconds)) / data.separation_cm
    )
    relative_pulsar_position = (
        np.asarray(data.orbit.vector_sp(data.time_seconds)) / data.separation_cm
    )

    fig = plt.figure(figsize=(13.2, 8.0), facecolor="#02030a")
    ax = fig.add_subplot(111, projection="3d", facecolor="#02030a")
    ax.plot_surface(
        grid[..., 0],
        grid[..., 1],
        grid[..., 2],
        facecolors=rgba,
        rstride=2,
        cstride=2,
        linewidth=0,
        antialiased=True,
        shade=False,
    )

    u = np.linspace(0.0, 2.0 * np.pi, 72)
    v = np.linspace(0.0, np.pi, 36)
    sx = star_position[0] + star_radius * np.outer(np.cos(u), np.sin(v))
    sy = star_position[1] + star_radius * np.outer(np.sin(u), np.sin(v))
    sz = star_position[2] + star_radius * np.outer(np.ones_like(u), np.cos(v))
    ax.plot_surface(sx, sy, sz, color="#ffd59a", linewidth=0, shade=True)

    pulsar_radius = 0.026
    px = pulsar_position[0] + pulsar_radius * np.outer(np.cos(u), np.sin(v))
    py = pulsar_position[1] + pulsar_radius * np.outer(np.sin(u), np.sin(v))
    pz = pulsar_position[2] + pulsar_radius * np.outer(np.ones_like(u), np.cos(v))
    ax.plot_surface(px, py, pz, color="#bfe9ff", linewidth=0, shade=True)

    orbit_times = np.linspace(-0.5 * data.orbit.T, 0.5 * data.orbit.T, 361)
    star_orbit = (
        np.asarray(data.orbit.vector_s(orbit_times)).T / data.separation_cm
    )
    ax.plot(
        star_orbit[:, 0],
        star_orbit[:, 1],
        star_orbit[:, 2],
        color="#ff9d58",
        linewidth=1.0,
        alpha=0.72,
    )

    # Draw a diffuse gaseous volume rather than a pair of disk boundary faces.
    # Its scale height and pressure weighting follow the IBSEn laws; the random
    # points are only a display sampling of that continuous analytic field.
    normal = np.asarray(data.star.n_disk, dtype=float)
    helper = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(normal, helper))) > 0.92:
        helper = np.array([1.0, 0.0, 0.0])
    basis_u = np.cross(normal, helper)
    basis_u /= np.linalg.norm(basis_u)
    basis_v = np.cross(normal, basis_u)
    pulsar_height = float(np.dot(relative_pulsar_position, normal))
    pulsar_plane_radius = float(
        np.linalg.norm(relative_pulsar_position - pulsar_height * normal)
    )
    disk_outer_radius = max(0.52, 1.35 * pulsar_plane_radius)
    disk_inner_radius = star_radius * 1.22
    random = np.random.default_rng(9137)
    sample_count = 12_000
    # A logarithmic draw is a contrast-compressed display choice: it preserves
    # the low-pressure outer disk without pretending that point density is gas
    # density.
    radii = disk_inner_radius * np.power(
        disk_outer_radius / disk_inner_radius, random.random(sample_count)
    )
    angles = random.uniform(0.0, 2.0 * np.pi, sample_count)
    scale_height = (
        data.star.delta
        * radii
        * np.power(radii / star_radius, data.star.height_exp)
    )
    heights = np.clip(random.normal(size=sample_count), -2.8, 2.8) * scale_height
    disk_points = (
        radii[:, None] * np.cos(angles)[:, None] * basis_u
        + radii[:, None] * np.sin(angles)[:, None] * basis_v
        + heights[:, None] * normal
        + star_position
    )
    edge_start = 0.72 * disk_outer_radius
    edge_t = np.clip(
        (radii - edge_start) / (disk_outer_radius - edge_start), 0.0, 1.0
    )
    edge_fade = 1.0 - edge_t**2 * (3.0 - 2.0 * edge_t)
    pressure = np.power(disk_inner_radius / radii, data.star.np_disk)
    pressure *= np.exp(-0.5 * np.square(heights / scale_height))
    brightness = np.power(pressure, 0.16) * edge_fade
    disk_rgba = np.zeros((sample_count, 4), dtype=float)
    disk_rgba[:, :3] = matplotlib.colors.to_rgb("#e84420")
    disk_rgba[:, 3] = 0.015 + 0.14 * brightness
    ax.scatter(
        disk_points[:, 0],
        disk_points[:, 1],
        disk_points[:, 2],
        s=1.1,
        c=disk_rgba,
        linewidths=0,
        depthshade=False,
    )

    mins = data.shock_vertices.min(axis=0)
    maxs = data.shock_vertices.max(axis=0)
    center = 0.5 * (mins + maxs)
    half_extent = float(np.max(maxs - mins) * 0.56)
    ax.set_xlim(center[0] - half_extent, center[0] + half_extent)
    ax.set_ylim(center[1] - half_extent, center[1] + half_extent)
    ax.set_zlim(center[2] - half_extent, center[2] + half_extent)
    ax.set_box_aspect((1.0, 1.0, 1.0))
    ax.view_init(elev=17.0, azim=-126.0, roll=0.0)
    ax.set_axis_off()
    ax.text2D(
        0.035,
        0.94,
        "BINARY SHOCK  /  FIRST PHYSICAL PROTOTYPE",
        transform=ax.transAxes,
        color="#f1f4ff",
        fontsize=13,
        fontweight="medium",
    )
    ax.text2D(
        0.037,
        0.905,
        "PSR B1259−63 · t = +20 d · shock color = Doppler factor",
        transform=ax.transAxes,
        color="#9aa8c8",
        fontsize=8.5,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)


def export_scene(args: argparse.Namespace) -> tuple[Path, Path, Path | None]:
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data, display_limits = calculate_scene(
        system=args.system,
        days_after_periastron=args.days_after_periastron,
        disk_strength=args.disk_strength,
        s_max=args.s_max,
        n_theta=args.n_theta,
        n_phi=args.n_phi,
    )
    scene, display = build_glb_scene(data)
    output.write_bytes(trimesh.exchange.gltf.export_glb(scene, include_normals=True))

    metadata_path = output.with_suffix(".metadata.json")
    metadata = build_metadata(
        data,
        display_limits,
        display,
        system=args.system,
        days_after_periastron=args.days_after_periastron,
        disk_strength=args.disk_strength,
        s_max=args.s_max,
        ibsen_root=args.ibsen_root.resolve(),
    )
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    preview_path: Path | None = None
    if args.preview is not None:
        preview_path = args.preview.resolve()
        render_preview(data, preview_path)

    print(f"GLB:      {output}")
    print(f"Metadata: {metadata_path}")
    if preview_path is not None:
        print(f"Preview:  {preview_path}")
    print(f"Geometry: {len(data.shock_vertices):,} shock vertices, {len(data.shock_faces):,} triangles")
    print(f"Doppler:  {np.nanmin(data.doppler):.6g} .. {np.nanmax(data.doppler):.6g}")
    return output, metadata_path, preview_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", default="psrb", help="IBSEn system preset (default: psrb)")
    parser.add_argument("--days-after-periastron", type=float, default=20.0)
    parser.add_argument("--disk-strength", type=float, default=100.0)
    parser.add_argument("--s-max", type=float, default=2.0)
    parser.add_argument("--n-theta", type=int, default=121)
    parser.add_argument("--n-phi", type=int, default=160)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("public/models/binary-shock-v0.1.glb"),
    )
    parser.add_argument(
        "--preview",
        type=Path,
        default=Path("public/previews/binary-shock-v0.1.png"),
    )
    parser.add_argument("--ibsen-root", type=Path, default=Path("IBSEn"))
    return parser.parse_args()


if __name__ == "__main__":
    export_scene(parse_args())
