import tempfile
import unittest
from pathlib import Path

from tools import coverage_profiles


class CoverageProfilesTests(unittest.TestCase):
    def test_select_map_prefers_existing_smallest_high_priority_region(self):
        with tempfile.TemporaryDirectory() as tmp:
            tiles_dir = Path(tmp)
            (tiles_dir / "conus-overview-raster.mbtiles").write_bytes(b"overview")
            (tiles_dir / "northeast-raster.mbtiles").write_bytes(b"regional")
            (tiles_dir / "nyc-raster.mbtiles").write_bytes(b"city")

            name, path = coverage_profiles.select_map_profile(40.723972, -73.845139, tiles_dir)

            self.assertEqual(name, "nyc")
            self.assertEqual(path.name, "nyc-raster.mbtiles")

    def test_select_map_falls_back_to_overview_when_outside_existing_regions(self):
        with tempfile.TemporaryDirectory() as tmp:
            tiles_dir = Path(tmp)
            (tiles_dir / "conus-overview-raster.mbtiles").write_bytes(b"overview")

            name, path = coverage_profiles.select_map_profile(39.7392, -104.9903, tiles_dir)

            self.assertEqual(name, "conus-overview")
            self.assertEqual(path.name, "conus-overview-raster.mbtiles")

    def test_regional_weather_uses_region_covering_location(self):
        bbox = coverage_profiles.regional_weather_bbox(41.4993, -81.6944)

        self.assertEqual(bbox, coverage_profiles.MAP_PROFILES["northeast"]["bbox"])

    def test_select_map_prefers_arizona_hd_over_broad_western_region(self):
        with tempfile.TemporaryDirectory() as tmp:
            tiles_dir = Path(tmp)
            (tiles_dir / "mountain-west-hd-raster.mbtiles").write_bytes(b"regional")
            (tiles_dir / "arizona-hd-raster.mbtiles").write_bytes(b"arizona")

            name, path = coverage_profiles.select_map_profile(33.4484, -112.0740, tiles_dir)

            self.assertEqual(name, "arizona-hd")
            self.assertEqual(path.name, "arizona-hd-raster.mbtiles")

    def test_select_map_prefers_tri_state_ultra_over_nyc(self):
        with tempfile.TemporaryDirectory() as tmp:
            tiles_dir = Path(tmp)
            (tiles_dir / "nyc-raster.mbtiles").write_bytes(b"nyc")
            (tiles_dir / "tri-state-ultra-raster.mbtiles").write_bytes(b"tri-state")

            name, path = coverage_profiles.select_map_profile(40.723972, -73.845139, tiles_dir)

            self.assertEqual(name, "tri-state-ultra")
            self.assertEqual(path.name, "tri-state-ultra-raster.mbtiles")

    def test_select_map_prefers_nyc_west_li_ultra_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            tiles_dir = Path(tmp)
            (tiles_dir / "tri-state-ultra-raster.mbtiles").write_bytes(b"tri-state")
            (tiles_dir / "nyc-west-li-ultra-raster.mbtiles").write_bytes(b"nyc-li")

            name, path = coverage_profiles.select_map_profile(40.723972, -73.845139, tiles_dir)

            self.assertEqual(name, "nyc-west-li-ultra")
            self.assertEqual(path.name, "nyc-west-li-ultra-raster.mbtiles")

    def test_focused_hd_group_includes_targeted_high_detail_without_midwest(self):
        names = coverage_profiles.profile_names_for_group("focused-hd")

        self.assertIn("nyc-west-li-ultra", names)
        self.assertIn("tri-state-ultra", names)
        self.assertIn("arizona-hd", names)
        self.assertNotIn("midwest", names)
        self.assertNotIn("south-central", names)

    def test_local_weather_bbox_is_centered_near_location(self):
        bbox = coverage_profiles.local_weather_bbox(40.0, -75.0)

        self.assertLess(bbox[0], -75.0)
        self.assertGreater(bbox[2], -75.0)
        self.assertLess(bbox[1], 40.0)
        self.assertGreater(bbox[3], 40.0)


if __name__ == "__main__":
    unittest.main()
