#!/usr/bin/env python3
"""Generate presentation-neutral Binary Shock system data.

This generator is the common scientific boundary for future paper, scientific
viewer, and artistic presentations.  It writes:

* a JSON document containing model quantities, reference geometry, orbit
  samples, and the annotations required by the hand-drawn paper schematic;
* a GLB containing only the analytic intrabinary-shock surface.

The default IBSEn configuration is a representative realization selected for
clear visual composition.  It is not inferred from the hand-drawn schematic
and must not be described as the unique physical configuration behind it.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import trimesh

from export_scene import AU_CM, DAY_SECONDS, SceneData, _git_revision, calculate_scene


SCHEMA_VERSION = "1.0.0"
DEFAULT_STATE_OUTPUT = Path("public/data/representative-system-state.json")
DEFAULT_GEOMETRY_OUTPUT = Path("public/models/representative-shock.glb")


def _unit(vector: np.ndarray) -> np.ndarray:
    """Return a finite unit vector."""
    vector = np.asarray(vector, dtype=float)
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm == 0.0:
        raise ValueError("Cannot normalize a zero or non-finite vector.")
    return vector / norm


def _vector(value: np.ndarray) -> list[float]:
    """Serialize one three-vector with ordinary Python floats."""
    result = np.asarray(value, dtype=float)
    if result.shape != (3,) or not np.isfinite(result).all():
        raise ValueError(f"Expected one finite three-vector, received {result.shape}.")
    return result.tolist()


def _path(value: np.ndarray) -> list[list[float]]:
    """Serialize an N-by-3 point path."""
    result = np.asarray(value, dtype=float)
    if result.ndim != 2 or result.shape[1] != 3 or not np.isfinite(result).all():
        raise ValueError(f"Expected a finite N-by-3 path, received {result.shape}.")
    return result.tolist()


def _angle_degrees(first: np.ndarray, second: np.ndarray) -> float:
    cosine = float(np.clip(np.dot(_unit(first), _unit(second)), -1.0, 1.0))
    return float(np.rad2deg(np.arccos(cosine)))


def _shock_reference_geometry(data: SceneData) -> dict:
    """Extract one annotated meridian and a local surface normal."""
    grid = np.asarray(data.shock.r_vec, dtype=float) / data.separation_cm
    arclength = np.asarray(data.shock.s, dtype=float) / data.separation_cm
    phi_index = 0
    s_index = max(1, min(data.shock.n - 2, int(round(0.18 * (data.shock.n - 1)))))

    tangent_s = grid[phi_index, s_index + 1] - grid[phi_index, s_index - 1]
    tangent_phi = (
        grid[(phi_index + 1) % data.shock.n_phi, s_index]
        - grid[(phi_index - 1) % data.shock.n_phi, s_index]
    )
    normal = _unit(np.cross(tangent_phi, tangent_s))

    pulsar_position = (
        np.asarray(data.orbit.vector_p(data.time_seconds), dtype=float)
        / data.separation_cm
    )
    axis = _unit(np.asarray(data.shock.symm_ax, dtype=float))
    point = grid[phi_index, s_index]
    point_from_pulsar = point - pulsar_position
    radial = point_from_pulsar - np.dot(point_from_pulsar, axis) * axis
    if np.dot(normal, radial) < 0.0:
        normal = -normal
    radial = _unit(radial)
    azimuth_basis_v = _unit(np.cross(axis, radial))

    return {
        "arclength_coordinate": {
            "symbol": "s",
            "unit": "instantaneous star-pulsar separation",
            "sample_values": np.asarray(arclength[phi_index], dtype=float).tolist(),
            "meridian_scene_coordinates": _path(grid[phi_index]),
            "opposite_meridian_scene_coordinates": _path(
                grid[(phi_index + data.shock.n_phi // 2) % data.shock.n_phi]
            ),
        },
        "terminal_ring_scene_coordinates": _path(grid[:, -1]),
        "reference_surface_point": {
            "scene_coordinates": _vector(point),
            "arclength_s": float(arclength[phi_index, s_index]),
            "normal_unit_vector": _vector(normal),
            "normal_symbol": "n_IBS",
        },
        "radius_vector_r_of_s": {
            "symbol": "r(s)",
            "origin_scene_coordinates": _vector(pulsar_position),
            "tip_scene_coordinates": _vector(point),
        },
        "azimuthal_coordinate": {
            "symbol": "phi",
            "axis_unit_vector": _vector(axis),
            "zero_direction_unit_vector": _vector(radial),
            "positive_direction_unit_vector": _vector(azimuth_basis_v),
        },
    }


def _build_state(
    data: SceneData,
    *,
    system: str,
    days_after_periastron: float,
    disk_strength: float,
    s_max: float,
    orbit_samples: int,
    geometry_path: Path,
    ibsen_root: Path,
) -> dict:
    separation = data.separation_cm
    time_seconds = data.time_seconds
    star_position = np.asarray(data.orbit.vector_s(time_seconds), dtype=float) / separation
    pulsar_position = np.asarray(data.orbit.vector_p(time_seconds), dtype=float) / separation
    relative_position = pulsar_position - star_position
    pulsar_velocity = np.asarray(data.orbit.vector_v_p(time_seconds), dtype=float)
    orbit_times = np.linspace(-0.5 * data.orbit.T, 0.5 * data.orbit.T, orbit_samples)
    star_orbit = np.asarray(data.orbit.vector_s(orbit_times), dtype=float).T / separation
    pulsar_orbit = np.asarray(data.orbit.vector_p(orbit_times), dtype=float).T / separation
    star_periastron = np.asarray(data.orbit.vector_s(0.0), dtype=float) / separation
    pulsar_periastron = np.asarray(data.orbit.vector_p(0.0), dtype=float) / separation

    apex = (
        np.asarray(data.shock.vec_p, dtype=float)
        - np.asarray(data.shock.symm_ax, dtype=float) * float(data.shock.r_pe)
    ) / separation
    apex_physical = apex * separation
    apex_from_star = apex_physical - np.asarray(
        data.orbit.vector_s(time_seconds), dtype=float
    )
    apex_from_pulsar = apex_physical - np.asarray(
        data.orbit.vector_p(time_seconds), dtype=float
    )
    true_anomaly = float(data.orbit.true_an(time_seconds))
    external_pressure = float(
        data.star.polar_wind_pressure(np.linalg.norm(apex_from_star))
        + data.star.decr_disk_pressure(apex_from_star, true_an=true_anomaly)
    )
    pulsar_pressure = float(
        data.pulsar.wind_pressure(np.linalg.norm(apex_from_pulsar))
    )

    disk_normal = _unit(np.asarray(data.star.n_disk, dtype=float))
    orbital_normal = np.array([0.0, 0.0, 1.0])
    relative_in_disk = relative_position - np.dot(relative_position, disk_normal) * disk_normal
    if np.linalg.norm(relative_in_disk) < 1e-12:
        relative_in_disk = np.cross(disk_normal, orbital_normal)
    disk_radial_direction = _unit(relative_in_disk)
    disk_flow_direction = _unit(np.cross(disk_normal, disk_radial_direction))
    disk_reference_point = star_position + disk_radial_direction

    shock_reference = _shock_reference_geometry(data)
    doppler = np.asarray(data.doppler, dtype=float)
    finite_doppler = doppler[np.isfinite(doppler)]

    return {
        "schema": {
            "name": "binary-shock-system-state",
            "version": SCHEMA_VERSION,
        },
        "classification": {
            "kind": "representative analytic-model realization",
            "purpose": (
                "Shared scientific state for the static paper figure, the interactive "
                "scientific viewer, and the artistic scene."
            ),
            "selection_note": (
                "The model parameters were selected to support a clear composition "
                "similar to the hand-drawn schematic. The schematic itself does not "
                "determine a unique system preset or orbital epoch."
            ),
            "not_a_claim": (
                "This state is not presented as the unique physical configuration "
                "encoded by the hand-drawn schematic."
            ),
        },
        "source_model": {
            "software": "IBSEn",
            "repository": "https://github.com/juliagouveamamprim/IBSEn",
            "git_revision": _git_revision(ibsen_root),
            "system_preset": system,
            "time_after_periastron_days": days_after_periastron,
            "time_after_periastron_seconds": time_seconds,
            "disk_pressure_strength_f_d": disk_strength,
            "shock_arclength_cutoff_s_max": s_max,
        },
        "coordinate_frame": {
            "origin": "binary barycenter",
            "length_unit": "instantaneous star-pulsar separation",
            "separation_cm": separation,
            "separation_au": separation / AU_CM,
            "x_unit_vector": [1.0, 0.0, 0.0],
            "y_unit_vector": [0.0, 1.0, 0.0],
            "z_unit_vector": [0.0, 0.0, 1.0],
            "orbital_plane_normal": _vector(orbital_normal),
        },
        "bodies": {
            "be_star": {
                "position": _vector(star_position),
                "mass_g": float(data.orbit.M_s),
                "radius_cm": float(data.star.R_s),
                "radius_separation_units": float(data.star.R_s / separation),
            },
            "pulsar": {
                "position": _vector(pulsar_position),
                "mass_g": float(data.orbit.M_p),
                "physical_radius": "not supplied by the IBSEn system preset",
            },
            "barycenter": {
                "position": [0.0, 0.0, 0.0],
            },
        },
        "orbit": {
            "period_days": float(data.orbit.T / DAY_SECONDS),
            "eccentricity": float(data.orbit.e),
            "samples": orbit_samples,
            "be_star_path": _path(star_orbit),
            "pulsar_path": _path(pulsar_orbit),
            "periastron": {
                "be_star_position": _vector(star_periastron),
                "pulsar_position": _vector(pulsar_periastron),
            },
            "current_pulsar_motion_unit_vector": _vector(_unit(pulsar_velocity)),
        },
        "decretion_disk": {
            "center": _vector(star_position),
            "equatorial_plane_normal": _vector(disk_normal),
            "tilt_from_orbital_plane_deg": _angle_degrees(
                disk_normal, orbital_normal
            ),
            "radial_pressure_profile": str(data.star.rad_prof),
            "pressure_normalization_f_d": float(data.star.f_d),
            "pressure_radial_power_law_index": float(data.star.np_disk),
            "scale_height_ratio_at_stellar_surface": float(data.star.delta),
            "scale_height_exponent": float(data.star.height_exp),
            "vertical_pressure_profile": str(data.star.vert_prof),
            "outer_edge": "not prescribed by IBSEn",
            "keplerian_flow": {
                "direction_definition": "unit(n_disk cross radial_direction)",
                "reference_point": _vector(disk_reference_point),
                "radial_unit_vector": _vector(disk_radial_direction),
                "flow_unit_vector": _vector(disk_flow_direction),
                "symbol": "v_d",
            },
        },
        "winds": {
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
        },
        "shock": {
            "geometry_file": geometry_path.as_posix(),
            "geometry_name": "IBS shock surface",
            "vertices": int(len(data.shock_vertices)),
            "triangles": int(len(data.shock_faces)),
            "surface_grid": {
                "azimuth_samples": int(data.shock.n_phi),
                "arclength_samples": int(data.shock.n),
            },
            "apex": {
                "position": _vector(apex),
                "arclength_s": 0.0,
            },
            "symmetry_axis_unit_vector": _vector(
                _unit(np.asarray(data.shock.symm_ax, dtype=float))
            ),
            "effective_wind_momentum_ratio_beta": float(data.shock.beta),
            "asymptotic_opening_angle_rad": float(data.shock.thetainf),
            "pressure_balance_at_apex": {
                "stellar_polar_plus_disk": external_pressure,
                "pulsar_wind": pulsar_pressure,
                "relative_mismatch": float(
                    abs(external_pressure - pulsar_pressure) / pulsar_pressure
                ),
            },
            "doppler_factor": {
                "minimum": float(finite_doppler.min()),
                "maximum": float(finite_doppler.max()),
                "line_of_sight_unit_vector": _vector(
                    _unit(np.asarray(data.shock.unit_los, dtype=float))
                ),
                "note": (
                    "The scalar is summarized here but is not mapped to a material "
                    "in the neutral GLB."
                ),
            },
            **shock_reference,
        },
        "paper_schematic_elements": {
            "required_labels": [
                "Be star (S)",
                "pulsar (P)",
                "barycenter",
                "periastron",
                "decretion-disk equatorial plane",
                "intrabinary shock",
                "apex (A), s = 0",
            ],
            "required_vectors": [
                "X, Y, Z coordinate axes",
                "direction of pulsar motion",
                "n_disc",
                "v_d",
                "n_IBS",
                "r(s)",
            ],
            "required_angles": ["alpha_d", "phi"],
            "status": (
                "These are annotation requirements for the paper renderer; their "
                "geometry is supplied above where it is model-defined."
            ),
        },
    }


def _build_neutral_shock_scene(data: SceneData) -> trimesh.Scene:
    """Create a GLB scene containing only the model-derived shock mesh."""
    mesh = trimesh.Trimesh(
        vertices=np.asarray(data.shock_vertices, dtype=float),
        faces=np.asarray(data.shock_faces, dtype=np.int64),
        process=False,
        metadata={
            "source": "IBSEn IBS3D.r_vec",
            "coordinate_origin": "binary barycenter",
            "coordinate_unit": "instantaneous star-pulsar separation",
        },
    )
    scene = trimesh.Scene(base_frame="Binary Shock system state")
    scene.add_geometry(
        mesh,
        geom_name="IBS shock surface",
        node_name="IBS shock surface",
    )
    return scene


def generate(args: argparse.Namespace) -> tuple[Path, Path]:
    state_output = args.state_output.resolve()
    geometry_output = args.geometry_output.resolve()
    state_output.parent.mkdir(parents=True, exist_ok=True)
    geometry_output.parent.mkdir(parents=True, exist_ok=True)

    data, _ = calculate_scene(
        system=args.system,
        days_after_periastron=args.days_after_periastron,
        disk_strength=args.disk_strength,
        s_max=args.s_max,
        n_theta=args.n_theta,
        n_phi=args.n_phi,
    )
    scene = _build_neutral_shock_scene(data)
    geometry_output.write_bytes(
        trimesh.exchange.gltf.export_glb(scene, include_normals=True)
    )

    geometry_reference = Path(os.path.relpath(geometry_output, state_output.parent))
    state = _build_state(
        data,
        system=args.system,
        days_after_periastron=args.days_after_periastron,
        disk_strength=args.disk_strength,
        s_max=args.s_max,
        orbit_samples=args.orbit_samples,
        geometry_path=geometry_reference,
        ibsen_root=args.ibsen_root.resolve(),
    )
    state_output.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"System state: {state_output}")
    print(f"Shock geometry: {geometry_output}")
    print(
        f"Geometry: {len(data.shock_vertices):,} vertices, "
        f"{len(data.shock_faces):,} triangles"
    )
    return state_output, geometry_output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", default="psrb")
    parser.add_argument("--days-after-periastron", type=float, default=100.0)
    parser.add_argument("--disk-strength", type=float, default=100.0)
    parser.add_argument("--s-max", type=float, default=1.0)
    parser.add_argument("--n-theta", type=int, default=121)
    parser.add_argument("--n-phi", type=int, default=160)
    parser.add_argument("--orbit-samples", type=int, default=361)
    parser.add_argument("--state-output", type=Path, default=DEFAULT_STATE_OUTPUT)
    parser.add_argument("--geometry-output", type=Path, default=DEFAULT_GEOMETRY_OUTPUT)
    parser.add_argument("--ibsen-root", type=Path, default=Path("IBSEn"))
    return parser.parse_args()


if __name__ == "__main__":
    generate(parse_args())
