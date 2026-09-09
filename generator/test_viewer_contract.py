from __future__ import annotations

import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "public/models/binary-shock-v0.1.glb"
METADATA_PATH = PROJECT_ROOT / "public/models/binary-shock-v0.1.metadata.json"
VIEWER_PATH = PROJECT_ROOT / "viewer"


class ViewerContractTests(unittest.TestCase):
    def test_viewer_references_the_generated_scene(self) -> None:
        source = (VIEWER_PATH / "app.js").read_text(encoding="utf-8")
        self.assertIn("../public/models/binary-shock-v0.1.glb", source)
        self.assertIn("../public/models/binary-shock-v0.1.metadata.json", source)
        self.assertIn("createRadialPressureGlow", source)
        self.assertIn("createDiskPressureVolume", source)
        self.assertTrue(MODEL_PATH.is_file())
        self.assertGreater(MODEL_PATH.stat().st_size, 0)

    def test_metadata_supplies_flow_model(self) -> None:
        metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        physical = metadata["physical_model"]
        flows = physical["flow_model"]

        self.assertEqual(
            flows["stellar_polar_wind"]["geometry"],
            "isotropic radial flow",
        )
        self.assertEqual(
            flows["pulsar_wind"]["geometry"],
            "isotropic radial flow",
        )
        self.assertEqual(
            flows["decretion_disk"]["velocity_model"],
            "Keplerian rotation in the disk plane",
        )
        self.assertEqual(len(flows["decretion_disk"]["normal_scene_coordinates"]), 3)
        self.assertEqual(len(physical["scene_positions"]["pulsar"]), 3)
        orbit = physical["orbit_display"]
        self.assertEqual(
            orbit["source"],
            "IBSEn Orbit.vector_s and Orbit.vector_p",
        )
        self.assertEqual(orbit["bodies"], ["Be star", "pulsar"])
        self.assertEqual(orbit["samples"], 361)
        self.assertLess(orbit["be_star_barycentric_fraction"], 0.1)
        self.assertEqual(len(orbit["be_star_path_scene_coordinates"]), 361)
        self.assertEqual(len(orbit["pulsar_path_scene_coordinates"]), 361)
        self.assertEqual(len(orbit["barycenter_scene_coordinates"]), 3)
        self.assertEqual(orbit["current_be_star_scene_coordinates"], [0.0, 0.0, 0.0])
        self.assertEqual(len(orbit["current_pulsar_scene_coordinates"]), 3)
        disk = flows["decretion_disk"]
        self.assertLess(
            abs(disk["pulsar_height_from_disk_plane_separation_units"]),
            disk["scale_height_at_pulsar_radius_separation_units"],
        )


if __name__ == "__main__":
    unittest.main()
