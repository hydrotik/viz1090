# viz1090

![image](https://media.giphy.com/media/dJnFpEDGi1swmb3L05/giphy.gif)

**This is a work in progress**

There are some major fixes and cleanup that need to happen before a release:
* Everything is a grab bag of C and C++, need to more consistently modernize
* A full refactor, especially View.cpp, necessary for many of the new features below.
* A working Android build, as this is the best way to run this on portable hardware.

There are also a lot of missing features:
* Map improvements
	* Labels, different colors/line weights for features
	* Tile prerenderer for improved performance
* In-application menus for view options and configuration
* Theming/colormaps (important as this is primarily intended to be eye candy!)
* Integration with handheld features like GPS, battery monitors, buttons/dials, etc. 

### BUILDING

Tested and working on Ubuntu 18.04, Raspbian Stretch / Buster, Windows Subsystem for Linux (with Ubuntu 18.04), and Mac

0. Install build essentials

```
sudo apt-get install build-essential
```

1. Install SDL and RTL-SDR libraries
```
sudo apt-get install libsdl2-dev libsdl2-ttf-dev libsdl2-gfx-dev librtlsdr-dev
```
1b. (Raspberry Pi only)
If you are running viz1090 on the Raspbian desktop (or any form of X) you can skip this step, but if you want to be able to start it directly from the command line, do the following to build SDL with KMS driver support. This is taken from [this stackoverflow question](https://stackoverflow.com/questions/57672568/sdl2-on-raspberry-pi-without-x)

```
git clone https://github.com/libsdl-org/SDL
sudo apt build-dep libsdl2
sudo apt install libdrm-dev libgbm-dev
cd ~/SDL
git checkout SDL2
./configure --enable-video-kmsdrm
make -j4 && sudo make install
```
Then download and build SDL2_gfx
```
wget http://www.ferzkopp.net/Software/SDL2_gfx/SDL2_gfx-1.0.4.tar.gz
tar -zxvf SDL2_gfx-1.0.4.tar.gz
cd SDL2_gfx-1.0.4
./configure --build=arm-linux-gnueabihf --disable-mmx
make -j4 && sudo make install
```
And finally SDL2_ttf
```
git clone https://github.com/libsdl-org/SDL_ttf.git
cd SDL_ttf
git checkout SDL2
./configure --disable-freetype-builtin --without-x --enable-harfbuzz=no
make -j4 && sudo make install
```
Now make sure that you are using the "Fake KMS" driver, not the newer "KMS" driver in /boot/config.txt:
```
dtoverlay=vc4-fkms-v3d
#dtoverlay=vc4-kms-v3d
```

2. Download and build viz1090
```
cd ~
git clone https://www.github.com/nmatsuda/viz1090
cd viz1090
make clean; make
```

3. Download and process offline map data

```
sudo apt install python3 python3-fiona python3-tqdm python3-shapely python3-numpy wget unzip
./getmap.sh --output-dir mapdata/generated/default
```

This will produce files for map and airport geometry, with labels, that viz1090 reads. If any of these files don't exist then visualizer will show planes and trails without any geography.

Optional raster basemap support uses SDL2_image and SQLite:

```
sudo apt install libsdl2-image-dev libsqlite3-dev
make clean && make viz1090
```

The default parameters for mapconverter should render reasonably quickly on a Raspberry Pi 4. See the mapconverter section below for other options and more information about map sources.

For portable/offline use, run the download once, then reuse the cached sources:

```
./getmap.sh --offline --output-dir mapdata/generated/default
```

For offline use across the United States, generate the high-detail national profile used by the uConsole wrapper:

```
./getmap.sh --output-dir mapdata/generated/us-hd --bbox -180,17,-52,72 --roads --water --tolerance 0.0005 --minpop 50000
```

On a ClockworkPi uConsole, the wrapper script builds if needed, generates this US map if missing, and launches the app with the recommended 1280x720 fullscreen settings:

```
./run_uconsole.sh
```

For the normal uConsole field workflow, use the station launcher instead. It builds the app, refreshes internet radar once, starts a background radar updater, launches the offline raster map/ADS-B UI, and stops the updater when the UI exits:

```
./run_uconsole_station.sh --tiles mapdata/tiles/nyc-raster.mbtiles
```

Use `--debug-weather` only while troubleshooting. Normal use should leave it off. If the weather layer is hard to see on the uConsole screen, the station launcher defaults to larger high-contrast radar cells; tune with `--weather-min-pixels`.

When syncing source code to the uConsole with `rsync --delete`, exclude local map data so offline caches and generated maps are not removed from the device:

```
rsync -av --delete \
  --exclude .git/ \
  --exclude __pycache__/ \
  --exclude '*.o' \
  --exclude viz1090 \
  --exclude tests/core_tests \
  --exclude mapdata/ \
  ./ \
  djdonovan@192.168.1.195:~/viz1090/
```

The wrapper tries to read GPS first, then falls back to configured coordinates. To skip GPS:

```
./run_uconsole.sh --no-gps
```

On HackerGadgets AIO V2 boards, GPS power is GPIO-controlled; the wrapper tries to enable GPIO 27 with `pinctrl` before reading GPS. Indoor GPS often fails to fix, especially after a cold start, so falling back to configured coordinates is expected indoors.

The default `us-hd` profile covers CONUS, Alaska, Hawaii, and Puerto Rico with one offline map at higher fidelity than the older `us` profile. Far Pacific territories and the far western Aleutians require future multi-bbox/dateline-aware map generation.

For a more detailed lower-48 map, use the `conus-hd` or `drive` profile:

```
./run_uconsole.sh --map-profile conus-hd --regen-map
./run_uconsole.sh --map-profile drive --regen-map
```

For a larger, more readable in-car view, use car mode. It selects the `drive` map profile, the daylight map theme, larger aircraft labels, larger status text, and a longer GPS timeout:

```
./run_uconsole.sh --car-mode
```

For a true street-map style base layer, use a local offline raster tile source. viz1090 supports MBTiles files and z/x/y tile directories when built with `SDL2_image`; MBTiles also needs `sqlite3`:

```
sudo apt install -y libsdl2-image-dev libsqlite3-dev
make clean && make viz1090
mkdir -p mapdata/tiles
./run_uconsole.sh --osm-mode --tiles mapdata/tiles/us.mbtiles
```

`--osm-mode` uses the map theme and overlays aircraft, weather, runways, labels, and controls over the raster basemap. It does not download map tiles. Put a legally generated or provider-licensed offline MBTiles file at `mapdata/tiles/us.mbtiles`, or pass a z/x/y tile directory:

```
./run_uconsole.sh --tiles mapdata/tiles/nyc --tiles-mode xyz --tile-max-zoom 16
```

Do not bulk-download tiles from `tile.openstreetmap.org` for offline use. Use self-hosted/generated tiles or a provider that explicitly permits offline MBTiles or tile packaging.

OpenMapTiles is a good source/style path, but the `.mbtiles` container can hold either raster tiles or vector PBF/MVT tiles. Current viz1090 renders raster tiles only. Before copying a large file to the uConsole, inspect it:

```
python3 tools/inspect_mbtiles.py path/to/downloaded.mbtiles
```

The result must say `usable raster MBTiles for viz1090`. If it says vector, render/export it to raster MBTiles first with MapTiler Engine, TileServer GL, or another OpenMapTiles-compatible renderer.

The repeatable OpenMapTiles workflow is:

1. Get an OpenMapTiles-compatible vector MBTiles extract for the region you want.
2. Run a local renderer such as TileServer GL on the Mac:

```
mkdir -p mapdata/tiles
docker run --rm -it \
  -v "$PWD/mapdata/tiles:/data" \
  -p 8080:8080 \
  maptiler/tileserver-gl:latest \
  --file /data/source/osm-2020-02-10-v3.11_north-america_us.mbtiles
```

Open `http://127.0.0.1:8080` and confirm the map renders. The stock TileServer GL raster endpoint is usually `http://127.0.0.1:8080/styles/basic-preview/{z}/{x}/{y}.png`; if the style name differs, use the style path shown by the TileServer GL page.

3. In another terminal, package the rendered raster tiles into a viz1090 MBTiles file:

```
python3 tools/build_raster_mbtiles.py \
  --tile-url 'http://127.0.0.1:8080/styles/basic-preview/{z}/{x}/{y}.png' \
  --bbox=-82,36,-65,48.5 \
  --min-zoom 0 \
  --max-zoom 12 \
  --output mapdata/tiles/northeast-raster.mbtiles \
  --name 'Northeast OpenMapTiles raster' \
  --force
```

Use `--dry-run` first to estimate tile count. Do not start with the whole US at high zoom; tile counts grow by roughly 4x per zoom level. Northeast zoom 0-12 is a reasonable first target. Zoom 13+ should be done region-by-region after confirming disk and render time.

For country-wide use, build one low-zoom overview pack and regional detail packs instead of one giant high-zoom national MBTiles file. The helper below uses the shared coverage profiles in `tools/coverage_profiles.py`:

```
python3 tools/build_map_tile_pack.py \
  --tile-url 'http://127.0.0.1:8080/styles/basic-preview/{z}/{x}/{y}.png' \
  --profiles all-us \
  --dry-run
```

When the dry run looks reasonable and your local tile renderer is running, remove `--dry-run`:

```
python3 tools/build_map_tile_pack.py \
  --tile-url 'http://127.0.0.1:8080/styles/basic-preview/{z}/{x}/{y}.png' \
  --profiles all-us \
  --force
```

The profile plan is tiered for uConsole performance: `conus-overview` covers the lower 48 at zoom 0-7, while `northeast`, `southeast`, `midwest`, `south-central`, `mountain-west`, and `west-coast` cover regional detail at zoom 0-12. Alaska, Hawaii, and Puerto Rico have smaller dedicated packs. The station launcher can auto-select the best installed pack for the configured/current location:

```
./run_uconsole_station.sh --map-tile-profile auto --weather-profile regional
```

To sync code and selected raster packs to the uConsole:

```
./deploy_uconsole.sh --tiles starter
./deploy_uconsole.sh --tiles conus-regions
```

`starter` syncs the national overview, Northeast, and NYC packs when present. `conus-regions` syncs the lower-48 overview and the six regional packs. `travel-hd` syncs the z14 West Coast, z14 Mountain West, z14 Arizona, and z15 NY/NJ/CT tri-state packs when present. Missing packs are skipped, so it is safe to run before every region has been generated.

For a sharper NYC-first test pack:

```
python3 tools/build_raster_mbtiles.py \
  --tile-url 'http://127.0.0.1:8080/styles/basic-preview/{z}/{x}/{y}.png' \
  --bbox=-75,39.8,-71.8,42.2 \
  --min-zoom 0 \
  --max-zoom 14 \
  --output mapdata/tiles/nyc-raster.mbtiles \
  --name 'NYC OpenMapTiles raster' \
  --force
```

4. Verify and copy to the uConsole:

```
python3 tools/inspect_mbtiles.py mapdata/tiles/northeast-raster.mbtiles
rsync -av mapdata/tiles/northeast-raster.mbtiles djdonovan@192.168.1.195:~/viz1090/mapdata/tiles/
```

5. Run on the uConsole:

```
cd ~/viz1090
./run_uconsole.sh --osm-mode --tiles mapdata/tiles/northeast-raster.mbtiles
```

For the Organic Maps path, use Organic Maps as the primary offline map/navigation engine and run viz1090 as the ADS-B feed producer:

```
tools/bootstrap_organicmaps.sh
tools/apply_organicmaps_overlay.sh
tools/build_organicmaps_macos.sh
./run_uconsole.sh --organic-feed /run/user/$(id -u)/viz1090-aircraft.geojson
```

The aircraft feed is compact GeoJSON and is written atomically for the patched Organic Maps overlay layer. Weather uses the existing radar CSV cache. From the Mac, mirror both uConsole feeds with one SSH session:

```
tools/bridge_uconsole_feeds.sh djdonovan@192.168.1.195
```

Then launch the patched Organic Maps desktop app:

```
external/omim-build-arm64/omim-build-release/OMaps.app/Contents/MacOS/OMaps \
  --viz1090_aircraft_feed /tmp/viz1090-aircraft.geojson \
  --viz1090_weather_feed /tmp/viz1090-radar_tiles.csv
```

See [ORGANIC_MAPS.md](ORGANIC_MAPS.md).

If you previously generated only the smaller NYC or Northeast map, force the new high-detail US map once:

```
./run_uconsole.sh --map-profile us-hd --regen-map
```

The uConsole wrapper also enlarges aircraft icons and aircraft labels by default. Tune those independently:

```
./run_uconsole.sh --plane-scale 1.7 --label-scale 1.8 --status-scale 1.7
```

To validate the future radar overlay UI without live FIS-B weather:

```
./run_uconsole.sh --simulate-weather
```

The simulator uses the same radar-tile renderer as cached weather. To create a static sample cache:

```
python3 tools/generate_weather_fixture.py --output weather/radar_tiles.csv
./run_uconsole.sh --weather-file weather/radar_tiles.csv
```

To try real OTA FIS-B weather on the uConsole, install `dump978-fa` once:

```
tools/install_dump978_fa.sh
```

Then run one UAT capture cycle:

```
./run_uat_weather_cycle.sh --duration 90 --sdr 'driver=rtlsdr,serial=25062501'
```

Before testing live reception, run the diagnostic path while the ADS-B service is under script control:

```
./run_uat_weather_cycle.sh --diagnose --sdr 'driver=rtlsdr,serial=25062501'
```

With one RTL-SDR tuner, this stops `dump1090-mutability`, samples 978 MHz UAT/FIS-B through `dump978-fa`, writes raw decoded JSON to `weather/uat_messages.jsonl`, updates `weather/radar_tiles.csv` when recognizable radar tile records are present, then restarts `dump1090-mutability`. During long captures the script prints progress every 15 seconds. For repeated background sampling:

```
./run_uat_weather_cycle.sh --loop --duration 90 --interval 240 --sdr 'driver=rtlsdr,serial=25062501'
```

The first real capture may only populate `weather/uat_messages.jsonl`; that is still useful because it shows the actual decoded FIS-B product shape we need to support. If `SoapySDRUtil --probe` fails after the capture script exits, check whether `dump1090-mutability` restarted and reclaimed the single RTL-SDR. Do not retune the SDR during map zoom/pan; zooming should only redraw cached radar data.

If UAT/FIS-B is quiet but the uConsole has internet, use the hybrid updater:

```
./run_weather_hybrid_cycle.sh --once
```

For continuous updates:

```
./run_weather_hybrid_cycle.sh
```

The hybrid updater tries RF UAT first. When RF captures decode zero messages, it fetches internet radar into the same `weather/radar_tiles.csv` cache and increases the RF retry interval up to a maximum. `run_uconsole.sh` passes this weather file to viz1090 even before it exists, and the renderer reloads it every 30 seconds, so the updater can be started before or after the app. The network fallback defaults to a lower-48 bbox (`-125,24,-66,50`) so zoomed-out weather can appear away from the current receiver location. Use `--local-weather` for a smaller current-location fetch, or `--weather-bbox lon_min,lat_min,lon_max,lat_max` for a custom area. The network fallback currently uses RainViewer's public Weather Maps API, which is free for personal/educational/small community use, best-effort, and requires visible attribution: "Weather data by RainViewer". The network updater retries lower zoom levels with `--network-min-zoom` when RainViewer returns unsupported placeholder tiles.

For a sharper NYC-area radar overlay, use a smaller bbox with higher network zoom and smaller output cells:

```
./run_weather_hybrid_cycle.sh \
  --no-rf \
  --no-gps \
  --weather-bbox=-75,39.8,-71.8,42.2 \
  --network-zoom 8 \
  --network-cell-pixels 3 \
  --network-min-coverage 0.08 \
  --min-interval 300 \
  --max-interval 300
```

Zoom 9 can add detail, but it increases network requests and CSV size. Start with zoom 8/cell-pixels 3 on the uConsole and only increase if rendering stays smooth.

The one-command equivalent for normal NYC/offline-raster use is:

```
./run_uconsole_station.sh --tiles mapdata/tiles/nyc-raster.mbtiles
```

For normal field use with installed regional packs, prefer:

```
./run_uconsole_station.sh --map-tile-profile auto --weather-profile regional
```

Optional FLOCK/DeFlock camera overlay:

```
python3 tools/build_flock_overlay.py \
  --source deflockhopper \
  --bbox=-125,24,-66,50 \
  --output-dir mapdata/flock

rsync -av --delete mapdata/flock/ \
  djdonovan@192.168.1.195:~/viz1090/mapdata/flock/

./run_uconsole_station.sh --map-tile-profile auto --weather-profile regional
```

`run_uconsole_station.sh` auto-enables the overlay when `mapdata/flock` exists. The renderer loads only visible z6 CSV tiles and caps drawing with `--flock-max-points` for uConsole performance. The default source is `FoggedLens/deflockhopper_maps` `public/cameras-us.json.gz`, which is a compact nationwide ALPR/camera export. `--source ringmast4r` can also convert `Ringmast4r/FLOCK` z6 GeoJSON tiles. This project uses the data as an informational map overlay only; it does not implement camera-avoidance routing.

Weather profiles:

- `national`: lower-48 radar overview, lower update frequency, lower geometry count.
- `regional`: region-sized radar around the configured/current location; default for the station launcher.
- `local`: smaller higher-detail radar around the configured/current location.

The station launcher defaults to supported RainViewer zoom fallback, so higher requested detail does not reintroduce the green "Zoom Level Not Supported" placeholder boxes.

To diagnose the uConsole GPS path while the device sits near a window:

```
./run_gps_probe.sh --timeout 120
```

This enables the configured GPS power GPIO when available, checks gpsd, lists candidate serial devices, prints a few NMEA sentences, and reports whether a valid fix is present.

For the HackerGadgets AIO board, GPS is expected on the UART path (`/dev/serial0`, `/dev/ttyS0`, or `/dev/ttyAMA0`) rather than the ClockworkPi USB control path. If the probe shows serial devices but no NMEA lines, verify that UART is enabled in `/boot/firmware/config.txt` and that `/boot/firmware/cmdline.txt` is not using `console=serial0,115200`.

See [CONTROLS.md](CONTROLS.md) for the full keyboard, pointer, and uConsole physical key map. Current uConsole defaults:

| uConsole control | Action |
| --- | --- |
| Top arrows | Pan north, south, west, and east |
| `L` / `Y` | Zoom out |
| `R` / `X` | Zoom in |
| `A` | Recenter on configured or GPS-derived location |
| `B` | Toggle ATC dark mode and light mode |
| Trackball drag | Pan by pointer drag |

If a physical uConsole key does not behave as expected, run `./run_uconsole.sh --debug-input` and press that key. The terminal will print whether SDL sees it as a keyboard key, mouse button, controller button, joystick button, or hat/D-pad event.

### uConsole GPS and Weather

`run_uconsole.sh` reads GPS using `tools/gps_fix.py`. The helper first tries `gpsd`, then raw NMEA serial devices such as `/dev/serial/by-id/usb-ClockworkPI_uConsole_20230713-if01` and `/dev/ttyACM0`.

Radar/precipitation over RF is a separate receive path from 1090 MHz ADS-B traffic. In the United States, ADS-B weather products are provided through FIS-B on UAT 978 MHz. With one RTL-SDR tuner, the practical approach is to periodically retune from 1090 MHz traffic to 978 MHz weather, cache decoded weather, then return to 1090 MHz. For simultaneous traffic and weather, use a second SDR/tuner.

3. (Windows only)

As WSL does not have an X server built in, you will need to install a 3rd party X server, such as https://sourceforge.net/projects/vcxsrv/

* run Xlaunch from the start menu
* Uncheck "Use Native openGL"
* Add parameter ```-ac``` (WSL 2 only)
* Open the Ubuntu WSL terminal
* Specify the X display to use (WSL 1)
        ```
        export DISPLAY=:0
        ```
* or for (WSL 2)
        ```
        export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0
        ```
* Start viz1090 as described below.

### BINARIES

You can find binaries for installation at https://repology.org/project/viz1090/versions

### RUNNING

1. Start dump1090 (http://www.github.com/MalcolmRobb/dump1090) locally in network mode:
```
dump1090 --net
```

2. Run viz1090 
```
./viz1090 --fullscreen --lat [your latitude] --lon [your longitude]
```

viz1090 will open an SDL window set to the resolution of your screen.

### RUNTIME OPTIONS

| Argument						| Description |
| ----------------------------- | ----------- |
| --server [domain name or ip]	| Specify a dump1090 server | 
| --port [port number]			| Specify dump1090 server port | 
| --metric						| Display metric units | 
| --lat                         | Specify your latitude in degrees | 
| --lon                         | Specify your longitude in degrees | 
| --mapdir [path]               | Directory containing generated map files. New maps may include styled layer files `admin.bin`, `coast.bin`, `water.bin`, and `roads.bin`; legacy `mapdata.bin` is still supported. |
| --organic-feed [path]         | Write compact aircraft GeoJSON for an Organic Maps sidecar overlay |
| --organic-feed-interval-ms [ms] | Organic Maps feed write interval, 100-60000 ms. Default: 1000 |
| --label-scale [factor]        | Scale aircraft labels independently from the rest of the UI |
| --plane-scale [factor]        | Scale aircraft icons independently from the rest of the UI |
| --screensize [width] [height]	| Specify a resolution, otherwise use resolution of display | 
| --simulate-weather            | Draw a simulated moving radar tile grid for UI validation |
| --theme [classic/atc/map/light] | Select the color theme. `classic` is the original look, `atc` is high-contrast radar style, `map` is a muted vector-map style, and `light` is a daylight map style |
| --status-scale [factor]       | Scale the bottom status strip independently from the rest of the UI |
| --tiles [path]                | Render an offline raster basemap under the vector/weather/aircraft overlays. Supports MBTiles files or z/x/y tile directories when optional tile dependencies are installed. |
| --tiles-mode [auto/mbtiles/xyz/tms] | Select raster tile source type. `auto` treats `.mbtiles` paths as MBTiles and other paths as xyz directories. |
| --tile-theme [auto/light/dark] | Select raster tile color treatment. `auto` follows the app light/dark toggle, `dark` transforms light raster tiles into a dark aviation-style basemap, and `light` keeps the original tile colors. |
| --tile-min-zoom [z]           | Minimum raster tile zoom. Default: 0 |
| --tile-max-zoom [z]           | Maximum raster tile zoom. Default: 17 |
| --tile-zoom-offset [n]        | Offset the automatically selected raster tile zoom, useful when a basemap looks too soft or too detailed. |
| --uiscale [scale]				| Scale up UI elements by integer amounts for high resolution screen | 
| --weather-file [path]         | Render a radar tile cache file with `lat_min,lon_min,lat_max,lon_max,intensity` rows |
| --fullscreen					| Render fullscreen rather than in a window | 

### MAPS

The best map data source I've found so far is https://www.naturalearthdata.com. This has a lot of useful GIS data, but not airport runways, which you can get from the FAA Aeronautical Data Delivery Service (https://adds-faa.opendata.arcgis.com/)


I've been using these files:

* [Map geometry](https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/10m/cultural/ne_10m_admin_1_states_provinces.zip) 
* [Coastlines](https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/10m/physical/ne_10m_coastline.zip)
* [Lakes](https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/10m/physical/ne_10m_lakes.zip)
* [Rivers and lake centerlines](https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/10m/physical/ne_10m_rivers_lake_centerlines.zip)
* [Roads](https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/10m/cultural/ne_10m_roads.zip)
* [Place names](https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/10m/cultural/ne_10m_populated_places.zip) 
* [Airport IATA codes](https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/10m/cultural/ne_10m_airports.zip) 
* [Airport runway geometry](https://opendata.arcgis.com/datasets/4d8fa46181aa470d809776c57a8ab1f6_0.zip)  

The bash script getmap.sh will download (so long as the links don't break) and convert these into an offline cache under `mapdata/cache`, then generate viz1090 map files. Alternatively, you can pass shapefiles and other arguments to mapconverter.py directly.

The generated map files can live outside the repository root. Use `--mapdir` when starting viz1090:

```
./viz1090 --mapdir mapdata/generated/us-hd --theme atc --lat 40.723972 --lon -73.845139
```

### MAPCONVERTER.PY RUNTIME OPTIONS

| Argument						| Description |
| ----------------------------- | ----------- |
| --mapfile | shapefile for main map |
| --mapnames | shapefile for map place names |
| --airportfile | shapefile for airport runway outlines |
| --airportnames | shapefile for airport IATA names |
| --minpop | minimum population to show place names for (defaults to 100000) |
| --tolerance | map simplification tolerance (mapconverter default is 0.001; uConsole `us-hd` uses 0.0005; smaller values produce more detail but slow down map refresh) |
| --bbox | optional `lon_min,lat_min,lon_max,lat_max` clipping bounds for smaller offline/regional maps |
| --output-dir | directory where generated map files are written |

### HARDWARE NOTES

This software was originally intended for Raspberry Pi devices, and it is currently optimized for the Raspberry Pi 4 with the following configuration:

* Raspberry Pi 4
* A display:
	* [Pimoroni HyperPixel 4.0 Display](https://shop.pimoroni.com/products/hyperpixel-4) \*best overall, but requires some rework to use battery monitoring features of the PiJuice mentioned below
	* [Waveshare 5.5" AMOLED](https://www.waveshare.com/5.5inch-hdmi-amoled.htm) \*this is very good screen but the Google Pixel 2 phone mentioned below has a very similar display for the same price (along with everything else you need in a nice package)
	* [Waveshare 4.3" HDMI(B)](https://www.waveshare.com/wiki/4.3inch_HDMI_LCD_(B))
	* [Adafruit 2.8" Capacitive Touch](https://www.adafruit.com/product/2423)
* A battery hat, such as:
	* [PiJuice Battery Hat](https://uk.pi-supply.com/products/pijuice-standard) \*I2C pins must be reworked to connect to the Hyperpixel nonstandard I2C breakout pins, unfortunately
	* [MakerFocus UPS Hat](https://www.amazon.com/Makerfocus-Raspberry-2500mAh-Lithium-Battery/dp/B01MQYX4UX) 
* Any USB SDR receiver:
	* [Noelec Nano V3](https://www.nooelec.com/store/nesdr-nano-three.html)
	* Stratux V2 \*very low power but hard to find

If you want to print the case in the GIF shown above, you can [download it here](https://github.com/nmatsuda/viz1090_case).

If running as a front end only, with a separate dump1090 server, the best option is to use an Android phone, such as the Pixel 2, which significantly outperforms a Raspberry Pi 4.

viz1090 has been tested on other boards such as the UP Core and UP Squared, but these boards have poor performance compared to a Raspberry Pi 4, along with worse software and peripheral support, so they are not recommended. viz1090 with a low resolution map will run on these boards or even a Raspberry Pi Zero, so these remain options with some tradeoffs.

Of course, a variety of other devices work well for this purpose - all of the development so far has been done on a touchscreen Dell XPS laptop.

### Credits

viz1090 is largely based on [dump1090](https://github.com/MalcolmRobb/dump1090) (Malcom Robb, Salvatore Sanfilippo)
