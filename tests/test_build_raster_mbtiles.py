import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools import build_raster_mbtiles


class BuildRasterMbtilesTests(unittest.TestCase):
    def test_tile_ranges_for_bbox(self):
        bbox = build_raster_mbtiles.parse_bbox("-75,40,-73,41")
        x_range, y_range = build_raster_mbtiles.tile_ranges_for_bbox(bbox, 8)

        self.assertGreater(len(x_range), 0)
        self.assertGreater(len(y_range), 0)

    def test_insert_tile_stores_xyz_as_tms_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tiles.mbtiles"
            conn = build_raster_mbtiles.open_mbtiles(path, {"format": "png"})
            try:
                build_raster_mbtiles.insert_tile(conn, (4, 3, 5), b"tile", "xyz")
                row = conn.execute(
                    "SELECT zoom_level, tile_column, tile_row, tile_data FROM tiles"
                ).fetchone()
            finally:
                conn.close()

        self.assertEqual(row, (4, 3, 10, b"tile"))

    def test_build_from_file_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            tile_dir = tmp_path / "source" / "0" / "0"
            tile_dir.mkdir(parents=True)
            (tile_dir / "0.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            output = tmp_path / "out.mbtiles"

            rc = build_raster_mbtiles.main(
                [
                    "--tile-url",
                    "file://" + str(tmp_path / "source/{z}/{x}/{y}.png"),
                    "--bbox=-1,-1,1,1",
                    "--min-zoom",
                    "0",
                    "--max-zoom",
                    "0",
                    "--output",
                    str(output),
                ]
            )

            self.assertEqual(rc, 0)
            conn = sqlite3.connect(output)
            try:
                count = conn.execute("SELECT COUNT(*) FROM tiles").fetchone()[0]
                tile_format = conn.execute("SELECT value FROM metadata WHERE name='format'").fetchone()[0]
            finally:
                conn.close()

        self.assertEqual(count, 1)
        self.assertEqual(tile_format, "png")


if __name__ == "__main__":
    unittest.main()
