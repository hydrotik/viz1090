import unittest

from tools import gps_fix


class GpsFixTests(unittest.TestCase):
    def test_nmea_coord_converts_lat_lon(self):
        self.assertAlmostEqual(gps_fix.nmea_coord("4043.4383", "N"), 40.723972, places=5)
        self.assertAlmostEqual(gps_fix.nmea_coord("07350.7083", "W"), -73.845138, places=5)

    def test_parse_gga_fix(self):
        fix = gps_fix.parse_nmea_fix(
            "$GPGGA,123519,4043.4383,N,07350.7083,W,1,08,0.9,545.4,M,46.9,M,,*47"
        )

        self.assertIsNotNone(fix)
        self.assertAlmostEqual(fix[0], 40.723972, places=5)
        self.assertAlmostEqual(fix[1], -73.845138, places=5)

    def test_parse_rmc_ignores_void_fix(self):
        self.assertIsNone(
            gps_fix.parse_nmea_fix("$GPRMC,123519,V,4043.4383,N,07350.7083,W,022.4,084.4,230394,,*1C")
        )


if __name__ == "__main__":
    unittest.main()
