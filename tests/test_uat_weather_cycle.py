import tempfile
import unittest
from pathlib import Path

from tools import uat_weather_cycle


class UatWeatherCycleTests(unittest.TestCase):
    def test_extracts_direct_tile_record(self):
        message = {
            "type": "nexrad",
            "lat_min": 40.0,
            "lon_min": -74.0,
            "lat_max": 40.1,
            "lon_max": -73.9,
            "intensity": 3,
        }

        self.assertEqual(
            uat_weather_cycle.extract_tiles(message),
            [(40.0, -74.0, 40.1, -73.9, 3)],
        )

    def test_extracts_nested_tile_records(self):
        message = {
            "fisb": {
                "product": "NEXRAD",
                "tiles": [
                    {
                        "south": 41.0,
                        "west": -75.0,
                        "north": 41.2,
                        "east": -74.8,
                        "level": "heavy",
                    }
                ],
            }
        }

        self.assertEqual(
            uat_weather_cycle.extract_tiles(message),
            [(41.0, -75.0, 41.2, -74.8, 3)],
        )

    def test_write_tiles_preserves_existing_when_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "radar_tiles.csv"
            output.write_text("existing\n", encoding="utf-8")

            count = uat_weather_cycle.write_tiles(output, [])

            self.assertEqual(count, 0)
            self.assertEqual(output.read_text(encoding="utf-8"), "existing\n")

    def test_write_tiles_outputs_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "radar_tiles.csv"
            count = uat_weather_cycle.write_tiles(output, [(40.0, -74.0, 40.1, -73.9, 2)])

            self.assertEqual(count, 1)
            lines = output.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[1], "40.000000,-74.000000,40.100000,-73.900000,2")


if __name__ == "__main__":
    unittest.main()
