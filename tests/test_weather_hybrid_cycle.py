import argparse
import unittest
from unittest import mock

from tools import weather_hybrid_cycle


class WeatherHybridCycleTests(unittest.TestCase):
    def test_run_network_forwards_fidelity_options(self):
        args = argparse.Namespace(
            lat=40.7,
            lon=-73.8,
            weather_file="weather/radar_tiles.csv",
            network_script="tools/network_weather.py",
            network_zoom=8,
            network_size=512,
            network_cell_pixels=3,
            network_min_coverage=0.08,
            network_smooth=1,
            weather_bbox="-75,39.8,-71.8,42.2",
            network_preserve_empty=True,
        )

        with mock.patch.object(weather_hybrid_cycle, "run_command", return_value=0) as run_command:
            status = weather_hybrid_cycle.run_network(args)

        self.assertEqual(status, 0)
        command = run_command.call_args.args[0]
        self.assertIn("--zoom", command)
        self.assertIn("8", command)
        self.assertIn("--cell-pixels", command)
        self.assertIn("3", command)
        self.assertIn("--min-coverage", command)
        self.assertIn("0.08", command)
        self.assertIn("--bbox=-75,39.8,-71.8,42.2", command)
        self.assertIn("--preserve-empty", command)


if __name__ == "__main__":
    unittest.main()
