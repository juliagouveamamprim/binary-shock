from __future__ import annotations

import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "public/models/binary-shock-v0.1.glb"
METADATA_PATH = PROJECT_ROOT / "public/models/binary-shock-v0.1.metadata.json"
PULSAR_TEXTURE_PATH = PROJECT_ROOT / "public/textures/neutron-star-thermal-v0.3.png"
VIEWER_PATH = PROJECT_ROOT / "viewer"


class ViewerContractTests(unittest.TestCase):
    def test_viewer_references_the_generated_scene(self) -> None:
        source = (VIEWER_PATH / "app.js").read_text(encoding="utf-8")
        self.assertIn("../public/models/binary-shock-v0.1.glb", source)
        self.assertIn("../public/models/binary-shock-v0.1.metadata.json", source)
        self.assertIn("../public/textures/neutron-star-thermal-v0.3.png", source)
        self.assertIn("createRadialPressureGlow", source)
        self.assertIn("createDiskPressureVolume", source)
        self.assertIn("createTexturedPulsar", source)
        self.assertIn("createLaminarBeam", source)
        self.assertIn("layerObjects.pulsarBeam", source)
        self.assertTrue(MODEL_PATH.is_file())
        self.assertGreater(MODEL_PATH.stat().st_size, 0)
        self.assertTrue(PULSAR_TEXTURE_PATH.is_file())
        self.assertGreater(PULSAR_TEXTURE_PATH.stat().st_size, 0)

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
        interpretation = metadata["visual_interpretation"]
        self.assertIn("no extended stellar or pulsar halo", interpretation["body_lighting"])
        self.assertIn("compact, smoothly fading white glow", interpretation["body_lighting"])
        self.assertIn("not an observed surface map", interpretation["pulsar_surface_texture"])
        self.assertIn("antipodal radio-beam", interpretation["pulsar_radio_beam"])
        beam = physical["pulsar_radio_beam_display"]
        self.assertEqual(beam["classification"], "model-informed artistic layer")
        self.assertEqual(beam["emission_band"], "radio")
        self.assertEqual(len(beam["unit_line_of_sight_scene_coordinates"]), 3)
        self.assertEqual(len(beam["spin_axis_scene_coordinates"]), 3)
        self.assertEqual(len(beam["magnetic_axis_scene_coordinates"]), 3)
        self.assertAlmostEqual(
            beam["radio_polarization_geometry"][
                "closest_magnetic_line_of_sight_approach_deg"
            ],
            3.0,
            places=10,
        )
        self.assertIn(
            "not an IBSEn-calculated emissivity volume",
            beam["unconstrained_choices"]["sheet_shape"],
        )
        geometry = beam["visual_geometry"]
        self.assertEqual(geometry["lamina_count"], 11)
        self.assertEqual(geometry["length_each_direction_separation_units"], 8.0)
        self.assertEqual(geometry["bundle_radius_pulsar_display_radii"], 0.13)
        self.assertIn("constant", geometry["cross_section"])
        disk = flows["decretion_disk"]
        self.assertLess(
            abs(disk["pulsar_height_from_disk_plane_separation_units"]),
            disk["scale_height_at_pulsar_radius_separation_units"],
        )


if __name__ == "__main__":
    unittest.main()
