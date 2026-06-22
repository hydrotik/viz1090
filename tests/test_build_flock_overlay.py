import tempfile
import unittest
from pathlib import Path

from tools import build_flock_overlay


class BuildFlockOverlayTests(unittest.TestCase):
    def test_feature_points_classifies_flock_alpr_and_camera(self):
        payload = {
            "features": [
                {
                    "geometry": {"type": "Point", "coordinates": [-73.1, 40.2]},
                    "properties": {"manufacturer": "Flock Safety", "surveillance:type": "ALPR"},
                },
                {
                    "geometry": {"type": "Point", "coordinates": [-73.2, 40.3]},
                    "properties": {"surveillance:type": "ALPR"},
                },
                {
                    "geometry": {"type": "Point", "coordinates": [-73.3, 40.4]},
                    "properties": {"surveillance:type": "camera"},
                },
            ]
        }

        self.assertEqual(
            list(build_flock_overlay.feature_points(payload)),
            [(40.2, -73.1, 2), (40.3, -73.2, 1), (40.4, -73.3, 0)],
        )

    def test_write_csv_tile(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "6" / "18" / "25.csv"

            build_flock_overlay.write_csv_tile(path, [(40.2, -73.1, 2)])

            self.assertIn("40.2000000,-73.1000000,2", path.read_text(encoding="utf-8"))

    def test_deflockhopper_points(self):
        payload = [
            {"lat": 35.1, "lon": -101.9, "brand": "Flock Safety"},
            {"lat": 37.6, "lon": -122.1, "surveillanceType": "ALPR"},
            {"lat": "bad", "lon": -122.1},
        ]

        self.assertEqual(
            list(build_flock_overlay.deflockhopper_points(payload)),
            [(35.1, -101.9, 2), (37.6, -122.1, 1)],
        )

    def test_group_points_by_tile_filters_bbox(self):
        points = [(35.1, -101.9, 2), (10.0, -101.9, 2)]

        grouped = build_flock_overlay.group_points_by_tile(points, (-125, 24, -66, 50), 6)

        self.assertEqual(sum(len(value) for value in grouped.values()), 1)


if __name__ == "__main__":
    unittest.main()
