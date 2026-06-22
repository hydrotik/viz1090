import struct
import tempfile
import unittest
import zlib

from tools import network_weather


def make_rgba_png(width, height, pixels):
    raw_rows = []
    for y in range(height):
        row = bytearray()
        row.append(0)
        for x in range(width):
            row.extend(pixels[y][x])
        raw_rows.append(bytes(row))

    def chunk(kind, payload):
        body = kind + payload
        crc = zlib.crc32(body) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", crc)

    return (
        network_weather.PNG_SIGNATURE
        + chunk("IHDR".encode("ascii"), struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk("IDAT".encode("ascii"), zlib.compress(b"".join(raw_rows)))
        + chunk("IEND".encode("ascii"), b"")
    )


def make_indexed_png(width, height, bit_depth, palette, rows):
    def chunk(kind, payload):
        body = kind + payload
        crc = zlib.crc32(body) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", crc)

    packed_rows = []
    pixels_per_byte = 8 // bit_depth
    for row in rows:
        out = bytearray([0])
        for start in range(0, width, pixels_per_byte):
            packed = 0
            for value in row[start : start + pixels_per_byte]:
                packed = (packed << bit_depth) | value
            missing = pixels_per_byte - len(row[start : start + pixels_per_byte])
            packed <<= missing * bit_depth
            out.append(packed)
        packed_rows.append(bytes(out))

    palette_bytes = b"".join(bytes(rgb) for rgb in palette)
    return (
        network_weather.PNG_SIGNATURE
        + chunk("IHDR".encode("ascii"), struct.pack(">IIBBBBB", width, height, bit_depth, 3, 0, 0, 0))
        + chunk("PLTE".encode("ascii"), palette_bytes)
        + chunk("IDAT".encode("ascii"), zlib.compress(b"".join(packed_rows)))
        + chunk("IEND".encode("ascii"), b"")
    )


class NetworkWeatherTests(unittest.TestCase):
    def test_latest_radar_frame_uses_newest_past_or_nowcast(self):
        metadata = {
            "radar": {
                "past": [{"time": 10, "path": "/old"}],
                "nowcast": [{"time": 20, "path": "/new"}],
            }
        }

        self.assertEqual(network_weather.latest_radar_frame(metadata)["path"], "/new")

    def test_rainviewer_tile_url_uses_coordinate_tile(self):
        metadata = {"host": "https://tilecache.rainviewer.com/"}
        frame = {"path": "/v2/radar/example"}

        url = network_weather.rainviewer_tile_url(metadata, frame, 40.7, -73.8, 7, 512, 2, 1, 1)

        self.assertEqual(
            url,
            "https://tilecache.rainviewer.com/v2/radar/example/512/7/40.70000/-73.80000/2/1_1.png",
        )

    def test_rainviewer_xyz_tile_url_uses_standard_tile(self):
        metadata = {"host": "https://tilecache.rainviewer.com/"}
        frame = {"path": "/v2/radar/example"}

        url = network_weather.rainviewer_xyz_tile_url(metadata, frame, 18, 23, 6, 512, 2, 1, 1)

        self.assertEqual(
            url,
            "https://tilecache.rainviewer.com/v2/radar/example/512/6/18/23/2/1_1.png",
        )

    def test_tile_ranges_for_bbox_include_cleveland_area(self):
        x_range, y_range = network_weather.tile_ranges_for_bbox((-125, 24, -66, 50), 5)
        cleveland_x, cleveland_y = network_weather.tile_xy_for_lon_lat(-81.6944, 41.4993, 5)

        self.assertIn(cleveland_x, list(x_range))
        self.assertIn(cleveland_y, list(y_range))

    def test_decode_png_rgba(self):
        png = make_rgba_png(1, 1, [[(10, 20, 30, 40)]])

        width, height, pixels = network_weather.decode_png_rgba(png)

        self.assertEqual((width, height), (1, 1))
        self.assertEqual(pixels[0][0], (10, 20, 30, 40))

    def test_decode_png_indexed_4bit(self):
        palette = [(0, 0, 0), (0, 180, 60), (230, 205, 38), (220, 55, 42)]
        png = make_indexed_png(4, 1, 4, palette, [[0, 1, 2, 3]])

        width, height, pixels = network_weather.decode_png_rgba(png)

        self.assertEqual((width, height), (4, 1))
        self.assertEqual(
            pixels[0],
            [(0, 0, 0, 255), (0, 180, 60, 255), (230, 205, 38, 255), (220, 55, 42, 255)],
        )

    def test_tiles_from_image_extracts_precipitation_cells(self):
        pixels = [
            [(0, 0, 0, 0), (0, 180, 60, 180)],
            [(0, 0, 0, 0), (0, 180, 60, 180)],
        ]

        tiles = network_weather.tiles_from_image(2, 2, pixels, 40.0, -75.0, 7, 512, 1, 0.5)

        self.assertEqual(len(tiles), 2)
        self.assertTrue(all(tile[4] == 1 for tile in tiles))

    def test_placeholder_tile_detection_ignores_error_labels(self):
        pixels = [[(0, 0, 0, 0) for _ in range(10)] for _ in range(10)]
        for y in range(2, 7):
            for x in range(1, 9):
                pixels[y][x] = (0, 0, 0, 255)
        for y in range(3, 6):
            for x in range(3, 7):
                pixels[y][x] = (255, 255, 255, 255)

        self.assertTrue(network_weather.is_placeholder_tile(10, 10, pixels))

    def test_placeholder_tile_detection_keeps_radar(self):
        pixels = [[(0, 0, 0, 0) for _ in range(10)] for _ in range(10)]
        for y in range(2, 7):
            for x in range(1, 9):
                pixels[y][x] = (0, 180, 60, 160)

        self.assertFalse(network_weather.is_placeholder_tile(10, 10, pixels))

    def test_tiles_from_image_at_origin_uses_tile_origin(self):
        pixels = [[(0, 180, 60, 180)]]
        x, y = network_weather.tile_xy_for_lon_lat(-81.6944, 41.4993, 5)

        tiles = network_weather.tiles_from_image_at_origin(1, 1, pixels, x * 512, y * 512, 5, 512, 1, 0.5)

        self.assertEqual(len(tiles), 1)
        self.assertGreaterEqual(tiles[0][1], -90.0)
        self.assertLessEqual(tiles[0][1], -75.0)

    def test_clip_tiles_to_bbox(self):
        tiles = [
            (23.5, -80.0, 24.5, -79.0, 1),
            (51.0, -80.0, 52.0, -79.0, 1),
        ]

        clipped = network_weather.clip_tiles_to_bbox(tiles, (-125, 24, -66, 50))

        self.assertEqual(clipped, [(24, -80.0, 24.5, -79.0, 1)])

    def test_fetch_rainviewer_falls_back_from_placeholder_zoom(self):
        metadata = {"host": "https://tiles.example", "radar": {"past": [{"time": 1, "path": "/radar"}]}}
        placeholder_pixels = [[(0, 0, 0, 255) for _ in range(4)] for _ in range(4)]
        radar_pixels = [[(0, 180, 60, 180) for _ in range(4)] for _ in range(4)]
        placeholder_png = make_rgba_png(4, 4, placeholder_pixels)
        radar_png = make_rgba_png(4, 4, radar_pixels)
        original_fetch = network_weather.fetch_url

        def fake_fetch(url, timeout):
            if url == network_weather.RAINVIEWER_API:
                return __import__("json").dumps(metadata).encode("utf-8")
            if "/8/" in url:
                return placeholder_png
            if "/7/" in url:
                return radar_png
            raise AssertionError("unexpected URL %s" % url)

        try:
            network_weather.fetch_url = fake_fetch
            with tempfile.TemporaryDirectory() as tmp:
                output = "%s/radar.csv" % tmp
                args = network_weather.build_parser().parse_args(
                    [
                        "--lat",
                        "40.7",
                        "--lon",
                        "-73.8",
                        "--output",
                        output,
                        "--zoom",
                        "8",
                        "--min-zoom",
                        "7",
                        "--cell-pixels",
                        "4",
                        "--min-coverage",
                        "0.1",
                    ]
                )

                count = network_weather.fetch_rainviewer(args)

                self.assertEqual(count, 1)
                with open(output, "r", encoding="utf-8") as handle:
                    contents = handle.read()
                self.assertIn("/7/", contents)
                self.assertIn(",1\n", contents)
        finally:
            network_weather.fetch_url = original_fetch


if __name__ == "__main__":
    unittest.main()
