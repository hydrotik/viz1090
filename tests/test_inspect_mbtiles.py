import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools import inspect_mbtiles


PNG_PIXEL = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89"
    b"\x00\x00\x00\x0bIDATx\x9cc``\x00\x00\x00\x04\x00\x01"
    b"\x0b\xe7\x02\x9d"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def make_mbtiles(path, tile_format, blob):
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE metadata (name TEXT, value TEXT)")
        conn.execute("CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB)")
        conn.execute("INSERT INTO metadata VALUES (?, ?)", ("name", "test tiles"))
        conn.execute("INSERT INTO metadata VALUES (?, ?)", ("format", tile_format))
        conn.execute("INSERT INTO tiles VALUES (?, ?, ?, ?)", (3, 1, 2, blob))
        conn.commit()
    finally:
        conn.close()


class InspectMbtilesTests(unittest.TestCase):
    def test_raster_mbtiles_is_usable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "raster.mbtiles"
            make_mbtiles(path, "png", PNG_PIXEL)

            result = inspect_mbtiles.inspect_mbtiles(path)

            self.assertTrue(result["usable"])
            self.assertEqual(result["kind"], "raster")
            self.assertEqual(result["effective_format"], "png")

    def test_vector_mbtiles_is_not_usable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "vector.mbtiles"
            make_mbtiles(path, "pbf", b"\x1f\x8bcompressed-vector")

            result = inspect_mbtiles.inspect_mbtiles(path)

            self.assertFalse(result["usable"])
            self.assertEqual(result["kind"], "vector")
            self.assertEqual(result["effective_format"], "pbf")

    def test_normalized_mbtiles_view_is_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "normalized.mbtiles"
            conn = sqlite3.connect(path)
            try:
                conn.execute("CREATE TABLE metadata (name TEXT, value TEXT)")
                conn.execute("CREATE TABLE images (tile_id TEXT, tile_data BLOB)")
                conn.execute("CREATE TABLE map (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_id TEXT)")
                conn.execute(
                    "CREATE VIEW tiles AS "
                    "SELECT map.zoom_level AS zoom_level, map.tile_column AS tile_column, "
                    "map.tile_row AS tile_row, images.tile_data AS tile_data "
                    "FROM map JOIN images ON map.tile_id = images.tile_id"
                )
                conn.execute("INSERT INTO metadata VALUES (?, ?)", ("format", "pbf"))
                conn.execute("INSERT INTO images VALUES (?, ?)", ("tile-1", b"\x1f\x8bcompressed-vector"))
                conn.execute("INSERT INTO map VALUES (?, ?, ?, ?)", (3, 1, 2, "tile-1"))
                conn.commit()
            finally:
                conn.close()

            result = inspect_mbtiles.inspect_mbtiles(path)

            self.assertFalse(result["usable"])
            self.assertEqual(result["kind"], "vector")
            self.assertEqual(result["count"], 1)

    def test_missing_tiles_table_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.mbtiles"
            sqlite3.connect(path).close()

            with self.assertRaises(inspect_mbtiles.InspectionError):
                inspect_mbtiles.inspect_mbtiles(path)


if __name__ == "__main__":
    unittest.main()
