import struct
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

    def test_tiles_from_image_extracts_precipitation_cells(self):
        pixels = [
            [(0, 0, 0, 0), (0, 180, 60, 180)],
            [(0, 0, 0, 0), (0, 180, 60, 180)],
        ]

        tiles = network_weather.tiles_from_image(2, 2, pixels, 40.0, -75.0, 7, 512, 1, 0.5)

        self.assertEqual(len(tiles), 2)
        self.assertTrue(all(tile[4] == 1 for tile in tiles))

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


if __name__ == "__main__":
    unittest.main()
