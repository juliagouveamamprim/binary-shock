from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import trimesh

from export_scene import (
    _grid_faces,
    _model_informed_pulsar_axes,
    build_glb_scene,
    calculate_scene,
)


class ExportSceneTests(unittest.TestCase):
    def test_periodic_grid_is_triangulated(self) -> None:
        faces = _grid_faces(n_phi=4, n_theta=5)
        self.assertEqual(faces.shape, (32, 3))
        self.assertGreaterEqual(int(faces.min()), 0)
        self.assertLess(int(faces.max()), 20)

    def test_small_scene_round_trips_through_glb(self) -> None:
        data, _ = calculate_scene(n_theta=25, n_phi=32, s_max=1.0)
        expected_star_relative = (
            np.asarray(data.shock.vec_sIBS, dtype=float) / data.separation_cm
        )
        np.testing.assert_allclose(
            data.shock_vertices.reshape(expected_star_relative.shape),
            expected_star_relative,
        )
        scene, _ = build_glb_scene(data)
        blob = trimesh.exchange.gltf.export_glb(scene, include_normals=True)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scene.glb"
            path.write_bytes(blob)
            loaded = trimesh.load(path, force="scene")

        self.assertEqual(len(loaded.geometry), 3)
        self.assertFalse(any("halo" in name.lower() for name in loaded.geometry))
        self.assertFalse(any("atmosphere" in name.lower() for name in loaded.geometry))
        self.assertTrue(np.isfinite(data.shock_vertices).all())
        self.assertTrue(np.isfinite(data.doppler).all())
        self.assertEqual(len(data.shock_rgba.reshape(-1, 4)), len(data.shock_vertices))

    def test_model_informed_pulsar_axes_preserve_published_angles(self) -> None:
        data, _ = calculate_scene(n_theta=25, n_phi=32, s_max=1.0)
        axes = _model_informed_pulsar_axes(data.shock.unit_los)

        for axis in axes.values():
            self.assertAlmostEqual(float(np.linalg.norm(axis)), 1.0, places=12)

        spin_los = np.rad2deg(
            np.arccos(np.clip(np.dot(axes["spin_axis"], axes["line_of_sight"]), -1, 1))
        )
        magnetic_spin = np.rad2deg(
            np.arccos(np.clip(np.dot(axes["magnetic_axis"], axes["spin_axis"]), -1, 1))
        )
        magnetic_los = np.rad2deg(
            np.arccos(
                np.clip(
                    np.dot(axes["magnetic_axis"], axes["line_of_sight"]),
                    -1,
                    1,
                )
            )
        )
        self.assertAlmostEqual(float(spin_los), 134.0, places=10)
        self.assertAlmostEqual(float(magnetic_spin), 137.0, places=10)
        self.assertAlmostEqual(float(magnetic_los), 3.0, places=10)


if __name__ == "__main__":
    unittest.main()
