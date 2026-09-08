#!/usr/bin/env python3
"""Export a physics-informed Binary Shock scene from IBSEn to GLB.

The generated asset is intended as a first visual test in Sketchfab. Positions
are expressed in units of the instantaneous star--pulsar separation. The shock
surface and its Doppler field come from IBSEn; the display radii and materials
are explicitly documented as visual choices in the metadata sidecar.
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
    # IBSEn >= 0.5.13 stores ``r_vec`` in barycentric coordinates.  Binary
    # Shock deliberately keeps the Be star at the scene origin, so use the
    # explicitly star-relative displacement vectors instead.
    vertices_grid = np.asarray(shock.vec_sIBS, dtype=float) / separation_cm
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
    pulsar_position = np.asarray(data.orbit.vector_sp(data.time_seconds), dtype=float) / separation

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
    # material, so Sketchfab receives both the scalar map and transparency.
    shock_visual.vertex_attributes = {"color": data.shock_rgba.reshape(-1, 4)}
    shock_mesh = trimesh.Trimesh(
        vertices=data.shock_vertices,
        faces=data.shock_faces,
        visual=shock_visual,
        process=False,
        metadata={
            "source": "IBSEn IBS3D.vec_sIBS (star-relative)",
            "field": "IBSEn IBS3D.dopl",
            "coordinate_unit": "instantaneous star-pulsar separation",
        },
    )

    star_mesh = trimesh.creation.icosphere(subdivisions=4, radius=star_radius)
    _set_material(
        star_mesh,
        _pbr_material(
            "Be star",
            (255, 222, 158, 255),
            (1.0, 0.46, 0.12),
            roughness=0.62,
        ),
    )

    star_halo = trimesh.creation.icosphere(subdivisions=3, radius=star_radius * 1.22)
    _set_material(
        star_halo,
        _pbr_material(
            "Be star atmosphere — visual",
            (255, 126, 45, 42),
            (0.62, 0.12, 0.02),
            roughness=1.0,
            alpha_mode="BLEND",
            double_sided=True,
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

    pulsar_halo = trimesh.creation.icosphere(
        subdivisions=3, radius=pulsar_display_radius * 2.25
    )
    pulsar_halo.apply_translation(pulsar_position)
    _set_material(
        pulsar_halo,
        _pbr_material(
            "Pulsar halo — visual",
            (68, 172, 255, 30),
            (0.05, 0.22, 0.80),
            roughness=1.0,
            alpha_mode="BLEND",
            double_sided=True,
        ),
    )

    disk_inner_radius = star_radius * 1.22
    disk_outer_radius = 0.52
    disk_half_height = float(
        data.star.delta
        * disk_outer_radius
        * np.power(disk_outer_radius / star_radius, data.star.height_exp)
    )
    disk_mesh = trimesh.creation.annulus(
        r_min=disk_inner_radius,
        r_max=disk_outer_radius,
        height=2.0 * disk_half_height,
        sections=192,
    )
    align_disk = trimesh.geometry.align_vectors([0.0, 0.0, 1.0], data.star.n_disk)
    disk_mesh.apply_transform(align_disk)
    _set_material(
        disk_mesh,
        _pbr_material(
            "Be decretion disk — visual cutoff",
            (245, 72, 24, 102),
            (0.72, 0.055, 0.012),
            roughness=0.76,
            alpha_mode="BLEND",
            double_sided=True,
        ),
    )

    scene = trimesh.Scene(base_frame="Binary Shock")
    scene.add_geometry(shock_mesh, geom_name="IBS shock surface", node_name="IBS shock surface")
    scene.add_geometry(star_mesh, geom_name="Be star", node_name="Be star")
    scene.add_geometry(star_halo, geom_name="Be star atmosphere", node_name="Be star atmosphere")
    scene.add_geometry(pulsar_mesh, geom_name="Pulsar", node_name="Pulsar")
    scene.add_geometry(pulsar_halo, geom_name="Pulsar halo", node_name="Pulsar halo")
    scene.add_geometry(disk_mesh, geom_name="Be decretion disk", node_name="Be decretion disk")

    display = {
        "star_radius_separation_units": star_radius,
        "pulsar_display_radius_separation_units": pulsar_display_radius,
        "disk_inner_radius_separation_units": disk_inner_radius,
        "disk_outer_radius_separation_units": disk_outer_radius,
        "disk_half_height_at_outer_edge_separation_units": disk_half_height,
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
    return {
        "title": "Binary Shock — PSR B1259−63 prototype",
        "asset_version": "0.1.1",
        "classification": "Physics-informed visualization of an analytic axisymmetric model",
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
            "coordinate_origin": "Be star center",
            "coordinate_unit": "instantaneous star-pulsar separation",
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
            "emission_and_halos": "Artistic cues for visibility; Sketchfab bloom is not baked into the asset",
            "pulsar_scale": "Strongly enlarged; a physical neutron-star radius is unresolved at this scale",
            "disk_extent": "Finite visual cutoff; the analytic pressure prescription has no rendered hard edge",
            "turbulence": "None added; the exported shock retains the axisymmetric IBSEn geometry",
        },
    }


def render_preview(data: SceneData, output: Path) -> None:
    """Render a lightweight QA preview; Sketchfab remains the target renderer."""
    grid = data.shock_vertices.reshape(data.shock.n_phi, data.shock.n, 3)
    rgba = data.shock_rgba.astype(float) / 255.0
    star_radius = float(data.star.R_s / data.separation_cm)
    pulsar_position = np.asarray(data.orbit.vector_sp(data.time_seconds)) / data.separation_cm

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
    sx = star_radius * np.outer(np.cos(u), np.sin(v))
    sy = star_radius * np.outer(np.sin(u), np.sin(v))
    sz = star_radius * np.outer(np.ones_like(u), np.cos(v))
    ax.plot_surface(sx, sy, sz, color="#ffd59a", linewidth=0, shade=True)

    pulsar_radius = 0.026
    px = pulsar_position[0] + pulsar_radius * np.outer(np.cos(u), np.sin(v))
    py = pulsar_position[1] + pulsar_radius * np.outer(np.sin(u), np.sin(v))
    pz = pulsar_position[2] + pulsar_radius * np.outer(np.ones_like(u), np.cos(v))
    ax.plot_surface(px, py, pz, color="#bfe9ff", linewidth=0, shade=True)

    # Draw the disk midplane using an orthonormal basis perpendicular to n_disk.
    normal = np.asarray(data.star.n_disk, dtype=float)
    helper = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(normal, helper))) > 0.92:
        helper = np.array([1.0, 0.0, 0.0])
    basis_u = np.cross(normal, helper)
    basis_u /= np.linalg.norm(basis_u)
    basis_v = np.cross(normal, basis_u)
    radii = np.linspace(star_radius * 1.22, 0.52, 34)
    angles = np.linspace(0.0, 2.0 * np.pi, 128)
    rr, aa = np.meshgrid(radii, angles)
    disk = (
        rr[..., None] * np.cos(aa)[..., None] * basis_u
        + rr[..., None] * np.sin(aa)[..., None] * basis_v
    )
    ax.plot_surface(
        disk[..., 0], disk[..., 1], disk[..., 2], color="#d83a18", alpha=0.26, linewidth=0
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
