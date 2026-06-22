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


if __name__ == "__main__":
    unittest.main()
