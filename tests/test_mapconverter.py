import struct
import tempfile
import unittest
from pathlib import Path

import mapconverter


class FakeCoordinateSequence:
    def __init__(self, xs, ys):
        self.xy = (xs, ys)


class FakeLineString:
    def __init__(self, points):
        xs, ys = zip(*points)
        self.coords = FakeCoordinateSequence(xs, ys)


class MapConverterTests(unittest.TestCase):
    def test_convert_linestring_appends_segment_terminator(self):
        converted = mapconverter.convertLinestring(
            FakeLineString([(-122.0, 47.0), (-121.5, 47.25)])
        )

        self.assertEqual(converted, [-122.0, 47.0, -121.5, 47.25, 0, 0])

    def test_write_float_bin_uses_single_precision(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "points.bin"
            mapconverter.writeFloatBin(output, [1.0, 2.5, -3.25])

            self.assertEqual(
                output.read_bytes(),
                struct.pack("fff", 1.0, 2.5, -3.25),
            )

    def test_bbox_parser_rejects_inverted_bounds(self):
        with self.assertRaises(Exception):
            mapconverter.parseBbox("-73,40,-74,41")

    def test_bbox_filter_includes_only_points_inside_bounds(self):
        bbox = [-74.1, 40.5, -73.7, 40.9]

        self.assertTrue(mapconverter.inBbox(-73.9, 40.7, bbox))
        self.assertFalse(mapconverter.inBbox(-75.0, 40.7, bbox))

    def test_write_runway_csv_outputs_centerline_segments(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "runways.csv"
            output = Path(tmp) / "airportdata.bin"
            csv_path.write_text(
                "le_latitude_deg,le_longitude_deg,he_latitude_deg,he_longitude_deg\n"
                "40.1,-73.9,40.2,-73.8\n"
                "41.1,-75.9,41.2,-75.8\n"
            )

            count = mapconverter.writeRunwayCsv(output, csv_path, [-74.0, 40.0, -73.0, 41.0])

            self.assertEqual(count, 1)
            self.assertEqual(
                output.read_bytes(),
                struct.pack("ffffff", -73.9, 40.1, -73.8, 40.2, 0, 0),
            )


if __name__ == "__main__":
    unittest.main()
