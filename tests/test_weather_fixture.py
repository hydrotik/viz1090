import tempfile
import unittest
from pathlib import Path

from tools import generate_weather_fixture


class WeatherFixtureTests(unittest.TestCase):
    def test_generate_tiles_writes_intensity_grid(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "radar_tiles.csv"
            count = generate_weather_fixture.generate_tiles(40.7, -73.8, output)

            self.assertGreater(count, 0)
            lines = [line for line in output.read_text().splitlines() if line and not line.startswith("#")]
            self.assertEqual(count, len(lines))
            first = lines[0].split(",")
            self.assertEqual(len(first), 5)
            self.assertIn(int(first[4]), (1, 2, 3, 4))


if __name__ == "__main__":
    unittest.main()
