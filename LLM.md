# LLM Build Notes

Last reviewed: 2026-06-21.

## Project Shape

`viz1090` is an SDL2 visualizer for ADS-B aircraft data. It does not read an SDR directly. The expected data path is:

```text
RTL-SDR or compatible receiver -> dump1090/readsb -> Beast TCP output on port 30005 -> viz1090
```

The visualizer connects to `127.0.0.1:30005` by default. Use `--server` and `--port` when `dump1090`/`readsb` runs on another machine.

Important files:

- `viz1090.cpp`: command-line parsing and main loop.
- `AppData.*`: TCP Beast connection, Mode S decode handoff, aircraft list updates.
- `View.*`: SDL window/renderer, map drawing, aircraft drawing, user interaction.
- `Map.*` and `mapconverter.py`: generated map/airport geometry loading and conversion.
- `run.sh`: example local dump1090 + small-screen run.
- `run_viz1090.sh`: example remote server run.

## Local Mac

Local machine observed with read-only system tools:

- MacBook Pro `Mac16,6`
- Apple M4 Max
- 14 CPU cores: 10 performance, 4 efficiency
- 36 GB RAM
- macOS 15.6.1 build 24G90
- Darwin arm64

This Mac does not need an SDR to develop the UI. Run the SDR decoder on the uConsole and point the Mac visualizer at it:

```sh
./viz1090 --server <uconsole-ip-or-hostname> --port 30005 --lat <lat> --lon <lon>
```

Local build status on 2026-06-21: `make` fails because `SDL2/SDL_ttf.h` is not visible to the active compiler. `pkg-config` can see `sdl2`, but not `SDL2_ttf` or `SDL2_gfx`. The active `brew` is `/usr/local/bin/brew`, which is an Intel Homebrew path on an Apple Silicon Mac. Prefer a consistent native Apple Silicon Homebrew under `/opt/homebrew` before debugging compiler/linker issues further.

Likely macOS dependencies:

```sh
brew install pkg-config sdl2 sdl2_ttf sdl2_gfx
```

If using Homebrew from `/opt/homebrew`, ensure `PATH` and `PKG_CONFIG_PATH` point there, not only `/usr/local`.

## uConsole Target

The uConsole is the more important target because it has the SDR/antenna expansions. Confirm the exact compute module before optimizing too aggressively. Common uConsole variants include Raspberry Pi CM4, ClockworkPi A-06, R-01, and community CM5/Radxa CM5 setups. The app should be treated as an ARM Linux/SDL2 target.

Relevant uConsole constraints:

- 5 inch 1280x720 display.
- Portable battery-powered use, commonly dual 18650 based.
- Expansion ecosystem includes RTL-SDR, LoRa, GPS, RTC, USB hub, USB 3.0, and RJ45 options from HackerGadgets.
- Forum activity indicates active uConsole RTL-SDR/AIO board usage, including setup and troubleshooting threads.

Recommended first uConsole run command:

```sh
./viz1090 --fullscreen --screensize 1280 720 --uiscale 1 --theme atc --lat <lat> --lon <lon>
```

If the UI text is too small on the uConsole panel, try `--uiscale 2`. If rendering slows, keep `--uiscale 1` and simplify map data instead.

## Linux/uConsole Dependencies

For Debian/Raspberry Pi OS style images:

```sh
sudo apt update
sudo apt install build-essential pkg-config \
  libsdl2-dev libsdl2-ttf-dev libsdl2-gfx-dev \
  librtlsdr-dev rtl-sdr \
  python3 python3-fiona python3-shapely python3-tqdm python3-numpy python3-requests \
  wget unzip
```

`librtlsdr-dev` is not used by `viz1090` directly, but is useful for the SDR decoder stack.

Decoder options:

- `dump1090 --net` matches the original README.
- `readsb` or `dump1090-fa` are also viable if configured to expose Beast output on TCP port `30005`.

Basic SDR checks on the uConsole:

```sh
lsusb
rtl_test -t
```

If the RTL-SDR is captured by Linux DVB drivers, blacklist the DVB modules for RTL-SDR use. Typical modules to blacklist are `dvb_usb_rtl28xxu`, `rtl2832`, and `rtl2830`; verify against the active kernel and device before changing boot configuration.

## Runtime Recipes

On the uConsole, local SDR and local visualizer:

```sh
dump1090 --net --quiet &
./viz1090 --fullscreen --screensize 1280 720 --uiscale 1 --lat <lat> --lon <lon>
```

On the uConsole, run decoder only and view from Mac:

```sh
dump1090 --net --quiet
```

Then on Mac:

```sh
./viz1090 --server <uconsole-ip> --port 30005 --lat <lat> --lon <lon>
```

The default server buffer now supports longer hostnames than the original 32-byte field, but plain IPv4/hostname is still the expected path because the inherited `anet` code is IPv4 oriented.

## Map Data

The app runs without generated map files, but only aircraft/trails/status will show. `getmap.sh` downloads Natural Earth/FAA data and calls `mapconverter.py`.

The map pipeline is offline/vector-first. `getmap.sh` now keeps source downloads under `mapdata/cache`, extracts temporary shapefiles under `mapdata/work`, and writes generated viz1090 files to a chosen `--output-dir`. On low-power hardware, generate maps once and reuse the generated files:

- `mapdata.bin`
- `admin.bin`, `coast.bin`, `water.bin`, and `roads.bin` when generated maps include styled layers
- `airportdata.bin`
- `mapnames`
- `airportnames`

Recommended uConsole offline US map:

```sh
cd ~/viz1090
./run_uconsole.sh
```

`run_uconsole.sh` builds the binary when needed, generates `mapdata/generated/us-hd` when missing, and launches with `--theme atc`, `--mapdir mapdata/generated/us-hd`, `--screensize 1280 720`, and the observed coordinates. The default `us-hd` profile bbox is `-180,17,-52,72`, covering CONUS, Alaska, Hawaii, and Puerto Rico in a single offline map. This is intentionally broader than the earlier NYC-only bbox `-75,39.8,-71.8,42.2` and Northeast bbox `-82,36,-65,48.5`, so zoomed-out or travel use does not show clipped blank map space. It does not fully cover far Pacific territories or every dateline-crossing Aleutian edge case; that needs future multi-bbox/dateline-aware map generation. It tries to read GPS first via `tools/gps_fix.py`, then falls back to the configured/default `--lat` and `--lon`; use `--no-gps` to skip GPS. The `us-hd` profile uses tolerance `0.0005`, minpop `50000`, roads, lakes, and river centerlines. Use `--map-profile conus-hd --regen-map` or `--map-profile drive --regen-map` for denser lower-48 maps if rendering remains fast enough, or increase tolerance if redraw becomes slow. It defaults to `--plane-scale 1.5 --label-scale 1.9 --status-scale 1.8` so aircraft, aircraft labels, and the bottom status strip are readable on the uConsole's small high-resolution screen without doubling all UI. `--car-mode` selects the `drive` map profile, `--theme map`, `--plane-scale 1.8`, `--label-scale 2.2`, `--status-scale 2.2`, and a 20 second GPS timeout for a more readable in-car display. For higher fidelity than Natural Earth can provide, `--osm-mode` selects the `map` theme and renders a local offline raster basemap when `--tiles` points at an MBTiles file or z/x/y tile directory.

When syncing code from the Mac to the uConsole, keep `mapdata/` out of `rsync --delete` operations. `mapdata/cache` and `mapdata/generated` are device-local offline assets and should survive source updates unless intentionally regenerated.

The generated vector map now combines state/province outlines, coastlines, roads, lakes, river centerlines, airport labels, and runway geometry. FAA runway outline downloads are optional; if that ArcGIS endpoint fails, `getmap.sh` falls back to OurAirports `runways.csv` and generates runway centerlines. The original admin-boundary-only map can look blank at a close 25 km New York zoom, and smaller bboxes clip out geography when zooming out; coastlines/roads/water/runways plus the US profile are important for a visible offline national map. Natural Earth roads are still too coarse for car-style neighborhood navigation, so do not keep trying to solve NYC street-level fidelity by lowering simplification alone.

Raster/OSM-style basemap path:

- `viz1090` accepts `--tiles <path>` plus `--tiles-mode auto|mbtiles|xyz|tms`, `--tile-min-zoom`, `--tile-max-zoom`, and `--tile-zoom-offset`.
- Tile rendering is optional at build time. Install `libsdl2-image-dev` for PNG/JPEG tile decoding and `libsqlite3-dev` for MBTiles, then run `make clean && make viz1090`.
- MBTiles are queried using the standard TMS tile row convention; xyz/tms directories are read from `<source>/<z>/<x>/<y>.png|jpg|jpeg|webp`.
- The raster basemap is drawn underneath the existing vector layers, cached radar/weather overlay, aircraft trails, aircraft icons, labels, and status strip.
- OpenMapTiles is the preferred high-fidelity data/style path, but current viz1090 only renders raster MBTiles. OpenMapTiles vector MBTiles (`metadata.format=pbf` or `mvt`) must be rendered/exported to raster PNG/JPEG/WebP MBTiles first. `tools/inspect_mbtiles.py <file.mbtiles>` identifies whether a downloaded MBTiles file is directly usable.
- `tools/build_raster_mbtiles.py` packages a local/approved XYZ/TMS raster endpoint into MBTiles. The intended workflow is OpenMapTiles vector MBTiles -> local TileServer GL raster endpoint -> `build_raster_mbtiles.py` -> `inspect_mbtiles.py` -> `run_uconsole.sh --osm-mode --tiles ...`.
- Use `build_raster_mbtiles.py --dry-run` before rendering. Northeast zoom 0-12 is a reasonable first target; whole-US high zoom should be generated in regional packs because tile count grows roughly 4x per zoom.
- Current country-scale raster plan: use `tools/build_map_tile_pack.py` and `tools/coverage_profiles.py`, not one giant high-zoom national file. `conus-overview` covers lower-48 zoom 0-7; regional packs (`northeast`, `southeast`, `midwest`, `south-central`, `mountain-west`, `west-coast`) cover zoom 0-12; `nyc` remains zoom 0-14. Higher-detail travel packs include `west-coast-hd` and `mountain-west-hd` at zoom 0-14, `arizona-hd` at zoom 0-14, and `tri-state-ultra` at zoom 0-15. `run_uconsole_station.sh --map-tile-profile auto --weather-profile regional` selects the best installed raster pack and falls back to generated vector maps when no pack exists. `deploy_uconsole.sh --tiles starter` syncs code plus available starter packs; `--tiles conus-regions` syncs the lower-48 overview plus regional packs; `--tiles travel-hd` syncs the high-detail western/Arizona/tri-state packs when present.
- Network weather profiles are `national`, `regional`, and `local`. The station launcher defaults to `regional`; RainViewer unsupported-zoom placeholders are rejected by `tools/network_weather.py`, which retries down to `--network-min-zoom` before preserving/writing an empty cache.
- FLOCK/DeFlock overlay: `tools/build_flock_overlay.py --source deflockhopper --bbox=-125,24,-66,50 --output-dir mapdata/flock` converts `FoggedLens/deflockhopper_maps` `public/cameras-us.json.gz` into compact local z6 CSV tiles. `--source ringmast4r` converts `Ringmast4r/FLOCK` z6 GeoJSON tiles. The builder preserves direction fields such as `direction`, `directionCardinal`, and `camera:direction` as an optional fourth CSV column; the renderer draws pulsing camera markers and a directional wedge when heading is known. `run_uconsole_station.sh` auto-enables `--flock-dir mapdata/flock` when that directory exists, drawing markers above radar and below aircraft. Keep this as an informational map overlay only; do not implement camera-avoidance routing.
- FLOCK color semantics: the data still classifies `kind: 0=surveillance, 1=ALPR, 2=Flock Safety`, but the renderer intentionally uses one subdued red family instead of blue/magenta/yellow so camera points do not compete with aircraft on the dark raster basemap. Aircraft draw after radar and FLOCK, with a dark halo behind the plane icon for contrast.
- Station workflow: prefer `./run_uconsole_station.sh --map-tile-profile auto --weather-profile regional` for normal field use. `./run_uconsole_station.sh --status` reports running app/weather processes, selected raster pack, disk headroom, weather cache age/rows, and FLOCK tile count. `./run_uconsole_station.sh --stop` stops the app, station wrapper, and weather updater without broad `pkill -f` patterns that can kill the controlling SSH session. `--restart` runs the same stop step before launching a fresh session.
- `./run_uconsole.sh --osm-mode --tiles mapdata/tiles/us.mbtiles` is the intended launch shape once a legal offline MBTiles basemap exists.
- Do not bulk scrape `tile.openstreetmap.org` into MBTiles. OSM's tile policy prohibits bulk downloading and offline use of those hosted raster tiles. Use self-hosted/generated tiles or a provider that explicitly allows offline packaging.
- Organic Maps is a useful product/design reference for offline OSM maps, but it is no longer the primary uConsole map path. Current Organic Maps source did not build cleanly on Debian 12/aarch64 with the uConsole's available GCC 12/Clang 14 C++23 library support. Its `.mwm` files are not MBTiles and are not directly usable by the SDL renderer.

Organic Maps integration path:

- The project is now pursuing Organic Maps as the high-fidelity offline map/navigation engine for the car-friendly view.
- Keep Organic Maps in `external/organicmaps`, ignored by git, using `tools/bootstrap_organicmaps.sh`.
- Apply the tracked aircraft overlay patch with `tools/apply_organicmaps_overlay.sh`. The patch file is `tools/organicmaps_viz1090_aircraft_overlay.patch`.
- On Apple Silicon Macs, build the native desktop app with `tools/build_organicmaps_macos.sh`; it uses `/opt/homebrew` Qt/CMake/Ninja and writes `external/omim-build-arm64/omim-build-release/OMaps.app`. Keep any older Rosetta/Intel build in `external/omim-build-release` separate as a fallback.
- Do not vendor Organic Maps source into this repo.
- Run viz1090/dump1090 as the aviation data producer and Organic Maps as the primary map renderer.
- viz1090 supports `--organic-feed <path>` and `--organic-feed-interval-ms <ms>` to write compact aircraft GeoJSON for an Organic Maps overlay patch.
- Prefer `/run/user/$(id -u)/viz1090-aircraft.geojson` on the uConsole so the feed is tmpfs-backed and avoids SD-card churn.
- The Organic Maps desktop patch adds `--viz1090_aircraft_feed <path>` and `--viz1090_weather_feed <path>`, polls by mtime/size, parses only the GeoJSON properties emitted by `OrganicMapsFeed` plus the radar CSV format `lat_min,lon_min,lat_max,lon_max,intensity`, and draws weather cells, aircraft trails, aircraft symbols, and zoom-gated labels above the map.
- Use `tools/bridge_uconsole_feeds.sh djdonovan@192.168.1.195` from the Mac to mirror `/run/user/1000/viz1090-aircraft.geojson` and `/home/djdonovan/viz1090/weather/radar_tiles.csv` into `/tmp` over one persistent SSH session.
- Keep SDR, Beast decoding, weather capture, and ADS-B classification out of Organic Maps. Those remain in viz1090/dump1090-side tooling.
- Organic Maps binary data files require visible Organic Maps and OpenStreetMap attribution if used in a distributed app.

Aircraft labels include heuristic category markers:

- Green dot: likely commercial based on common airline callsign prefixes/patterns.
- Orange dot: likely government/military based on common callsign prefixes or US military ICAO range.
- No dot: unknown. This is not authoritative; better classification needs a local aircraft/operator database.

uConsole input support is documented in `CONTROLS.md`. Keep that file, `Input.cpp`, and this note aligned when physical key mappings change.

Current observed uConsole mapping on 2026-06-21:

- Top arrows arrive as keyboard arrow keys and pan north/south/west/east.
- `L` arrives as mouse button `1` at `(0,0)` and maps to zoom out.
- `R` arrives as mouse button `3` at `(0,0)` and maps to zoom in.
- `X` is raw joystick button `0` and maps to zoom in.
- `A` is raw joystick button `1` and maps to recenter.
- `B` is raw joystick button `2` and maps to ATC dark/light toggle.
- `Y` is raw joystick button `3` and maps to zoom out.
- Trackball press arrives as mouse button `2` at the pointer location and is left as a normal middle mouse click.

Use `./run_uconsole.sh --debug-input` to print SDL input events when validating the physical uConsole keys. This is especially useful because some uConsole controls may appear as mouse buttons instead of keyboard/controller buttons; observed behavior included the `L` control acting like a left click/double click.

After one successful online run, the same map can be regenerated without network:

```sh
./getmap.sh --offline --output-dir mapdata/generated/us-hd --bbox -180,17,-52,72 --roads --water --tolerance 0.0005 --minpop 50000
```

Use `--theme atc` for the high-contrast radar/WarGames-style view, `--theme map` for a muted vector-map look, and `--theme classic` for the original palette. If map drawing is slow, increase `mapconverter.py --tolerance` above the default `0.0005` and/or raise `--minpop` to reduce labels.

For the uConsole, consider generating on the Mac after Python/GIS dependencies are installed, then copying the generated output directory to the uConsole. For Mapbox/Organic-Maps-like fidelity, prefer MBTiles first because the renderer now supports it and the ADS-B/weather overlay can stay inside this lightweight SDL app. PMTiles/vector tiles remain a future option if raster MBTiles are too large or too static.

## Fork Review

Forks checked from `https://github.com/nmatsuda/viz1090` on 2026-06-21.

Useful findings:

- Local `hydrotik/viz1090` is identical to upstream `nmatsuda/viz1090` at commit `fb7bf016d5d95ddca5b27f260e871484864b5c96` before local edits.
- `npease18/viz1090` and `rlalik/viz1090` were also identical to upstream.
- Many forks are simply behind upstream.
- `dvb1024/viz1090` adds `view.metric = 0` before argument parsing. This is not needed because current `View::View` already sets `metric = 0`.
- `sykocus/viz1090-go` is archived and diverged. Its only relevant C++ change stores `originalLat`/`originalLon` when parsing `--lat`/`--lon`; those fields are not otherwise used in the patch, so it is not worth merging as-is.

No fork had a substantive uConsole, SDR, packaging, or performance patch worth merging directly.

## GPS Notes

Observed uConsole device paths include `/dev/serial/by-id/usb-ClockworkPI_uConsole_20230713-if01 -> ../../ttyACM0`. No `gpsd`/`gpspipe` tools were installed when checked through the temporary `codex` account.

HackerGadgets documents AIO V2 GPS power on GPIO 27. `run_uconsole.sh` tries `pinctrl 27 op` and `pinctrl 27 dh` before reading GPS, unless `--no-gps-power` is passed. Indoor GPS failures are expected, especially after a cold start; this should not block app startup.

`tools/gps_fix.py` uses only the Python standard library. It attempts:

1. `gpsd` JSON on `127.0.0.1:2947`, if `gpsd` is running.
2. Raw NMEA from known serial devices, including `/dev/serial0`, `/dev/ttyS0`, `/dev/ttyAMA0`, and the observed ClockworkPi `/dev/ttyACM0` path.

If no fix is available within `--gps-timeout`, `run_uconsole.sh` continues with configured coordinates.

Future GPS/tracking revisit:

- Decide whether GPS should be enabled by default once outdoor testing confirms reliable fixes.
- Consider continuously tracking GPS while the app runs, not just startup location.
- Add an explicit on-screen indication for `gps` versus configured/fallback location.
- Consider map auto-recenter on moving GPS location for car use, with a key to pause/resume follow mode.
- `run_gps_probe.sh --timeout 120` is the preferred diagnostic path. It enables GPIO 27 when possible, checks gpsd, reports UART boot settings, lists candidate serial devices, prints sample NMEA lines, and reports whether a valid fix was found. If NMEA sentences appear but no fix is found, the GPS is powered and communicating but still needs sky view/time for a fix. If no NMEA lines appear, check `/boot/firmware/config.txt` for `enable_uart=1` and ensure `/boot/firmware/cmdline.txt` does not assign the GPS UART to `console=serial0,115200`.

## OTA Weather Possibilities

Radar/precipitation over RF is most realistically obtained through ADS-B In FIS-B on UAT 978 MHz in the United States, not through the existing 1090 MHz `dump1090` traffic path. FAA documentation states FIS-B is broadcast on UAT and includes products such as METAR, CONUS/Regional NEXRAD, NOTAM, PIREP, TAF, winds aloft, and other weather/aeronautical products. Garmin notes additional FIS-B weather products such as lightning, cloud tops, icing, and turbulence, but radar/precipitation is the first useful target.

Implementation options:

- Best: use a second SDR/tuner for 978 MHz UAT while the current RTL-SDR remains on 1090 MHz ADS-B. Multiple antennas do not guarantee simultaneous receive; simultaneous 1090+978 requires multiple tuners or a receiver capable of independent concurrent channels.
- Possible with one RTL-SDR: periodically stop or pause the 1090 MHz decoder, retune to 978 MHz, run a UAT/FIS-B decoder such as `dump978` for a short window, cache decoded weather products, then return to 1090 MHz. A 4 minute cycle is plausible for slowly changing weather, but aircraft updates will be missed during UAT receive windows.
- NOAA Weather Radio around 162 MHz provides audio/text-style weather alerts, not radar images.
- NOAA APT/HRPT/GOES satellite paths are different RF systems and not a good fit for quick local radar in this handheld workflow.
- Internet fallback is practical when the uConsole has connectivity. `tools/network_weather.py` uses RainViewer's public Weather Maps API to fetch the latest radar tile data and convert it into the same `weather/radar_tiles.csv` format used by the renderer. It supports a coordinate-centered widget fetch and bbox fetching through standard XYZ tiles. The uConsole hybrid wrapper defaults network weather to the lower-48 bbox `-125,24,-66,50` at zoom 5 so zoomed-out weather can appear away from the current receiver location. For local NYC/high-detail mode, prefer `--weather-bbox=-75,39.8,-71.8,42.2 --network-zoom 8 --network-cell-pixels 3 --network-min-coverage 0.08`; zoom 9 is heavier and should only be used if the uConsole render path stays smooth. RainViewer describes the API as free for personal, educational, and small community use, best-effort, refreshed around every 5 minutes, with visible attribution required.

Near-term radar-only weather plan:

1. Install/test `dump978-fa` on the uConsole with `tools/install_dump978_fa.sh`. FlightAware documents `dump978-fa` as the 978 MHz UAT decoder; it can expose decoded JSON on `--json-port` and uses SoapySDR with `--sdr driver=rtlsdr`.
2. Verify whether the installed SDR expansion exposes one tuner or multiple tuners.
3. If one tuner: use `run_uat_weather_cycle.sh` to stop `dump1090-mutability`, sample 978 MHz every few minutes through `tools/uat_weather_cycle.py`, write decoded JSON to `weather/uat_messages.jsonl`, update `weather/radar_tiles.csv` when recognizable radar tiles are present, then restart `dump1090-mutability`.
4. Inspect real `weather/uat_messages.jsonl` captures and extend `tools/uat_weather_cycle.py` for the exact FIS-B/NEXRAD JSON product shape emitted by the installed decoder.
5. Defer non-radar products such as lightning, cloud tops, icing, turbulence, NOTAMs, and text weather until the radar path is proven.

uConsole UAT diagnostics:

- The HackerGadgets AIO RTL-SDR has appeared as serial `25062501`; prefer `--sdr 'driver=rtlsdr,serial=25062501'` when testing UAT weather.
- Run `./run_uat_weather_cycle.sh --diagnose --sdr 'driver=rtlsdr,serial=25062501'` before live weather captures. This stops `dump1090-mutability`, probes `dump978-fa` and SoapySDR, then restarts the ADS-B service.
- `SoapySDRUtil --probe` will fail with `usb_claim_interface error -6` if `dump1090-mutability` already owns the single RTL-SDR. That is expected after the capture script restarts ADS-B service.
- The UAT capture script now prints JSON capture progress every 15 seconds. Let the capture complete unless it is clearly wedged.
- Zooming/panning the map should not retune the SDR. The app should render cached weather data; SDR retuning should happen on a timed/manual weather capture cycle.
- `run_weather_hybrid_cycle.sh` is the preferred long-running weather updater. It tries RF UAT/FIS-B first; if the capture produces zero new JSON messages, it fetches network radar if internet is available and backs off the RF retry interval up to a maximum. Use `--once` for a single RF/network update before launching the UI.

Weather UI validation:

- `--simulate-weather` draws a simulated moving NEXRAD-like radar tile grid over the map under aircraft.
- `./run_uconsole.sh --simulate-weather` is the uConsole validation path.
- `tools/generate_weather_fixture.py` can write a static `weather/radar_tiles.csv` cache for UI screenshots/tests.
- `tools/uat_weather_cycle.py` is the live UAT/FIS-B capture bridge. It preserves existing radar cache files if a capture yields no recognized radar tiles, so a no-signal capture does not erase the last useful overlay.
- `--weather-file <path>` renders rows of `lat_min,lon_min,lat_max,lon_max,intensity`, where intensity is 1 green, 2 yellow, 3 red, 4 magenta.
- This is only a UI overlay simulator; it is not live weather and should not be used for navigation decisions.

## Future Bluetooth Detector Integration

Uniden R8 integration is plausible because the Android Highway Radar app supports the R8 over Bluetooth, which implies the detector exposes live alert data over a Bluetooth/BLE protocol that third-party software can consume. Treat the protocol as undocumented until proven otherwise.

Future R8 work should start with a separate bridge rather than putting Bluetooth code directly into the SDL renderer:

1. Pair the R8 to the uConsole with `bluetoothctl`.
2. Use a Python BLE probe such as `bleak` to list GATT services/characteristics and subscribe to notification characteristics.
3. Log raw packets while creating known alerts, muting, changing bands, changing arrows/direction, and toggling detector settings.
4. Decode the packet fields into a normalized JSON file or local socket, for example `/run/user/$(id -u)/viz1090-r8.json`.
5. Add a small viz1090 overlay/status panel that reads the normalized feed and displays detector connection state, band, frequency, signal strength, directional arrows, mute state, and timestamp.

Likely bridge shape:

```text
Uniden R8 Bluetooth/BLE
  -> tools/r8_probe.py / tools/r8_bridge.py
  -> /run/user/1000/viz1090-r8.json
  -> viz1090 detector overlay
```

Potential constraints:

- The R8 may allow only one active Bluetooth client. If Highway Radar is connected from an Android phone, the uConsole may not be able to connect at the same time.
- Some R8 Bluetooth behavior may be BLE GATT notifications; some devices expose classic Bluetooth serial profiles. Probe before assuming either path.
- Keep the bridge optional. viz1090 should start normally when the detector is absent.
- Keep detector data separate from ADS-B/weather. Do not retune or interrupt the RTL-SDR for Bluetooth work.

uConsole Bluetooth/SDR notes:

- The uConsole SDR/AIO expansion includes the RTL-SDR path for ADS-B/UAT plus other expansion features; Bluetooth is handled by the uConsole/Linux Bluetooth stack, not by the RTL-SDR tuner.
- Using Bluetooth for R8 data should not conflict with the SDR radio path, but it can share CPU, power, and USB/Bluetooth subsystem resources on the uConsole.
- Before field use, test Bluetooth connection stability while `dump1090-mutability`, viz1090 rendering, weather updater, GPS probing, and the FLOCK overlay are all active.
- Useful first commands: `bluetoothctl scan on`, `bluetoothctl info <R8-MAC>`, `bluetoothctl pair/trust/connect <R8-MAC>`, then a BLE service dump from a future `tools/r8_probe.py`.

## Cleanup Already Applied

Initial cleanup in this checkout:

- Added `TESTING.md`, Linux GitHub Actions CI, and Makefile targets for `test`, `sanitize`, `smoke-ui`, `benchmark-smoke`, and `ci`.
- Added non-SDL C++ regression tests for aircraft history, aircraft list updates/removal, and Mode S decode fixtures.
- Added Python mapconverter regression tests and refactored `mapconverter.py` so it can be safely imported by tests.
- Added deterministic Beast replay fixtures and `tools/replay_benchmark.py` for headless UI smoke/perf runs once `viz1090` builds.
- Fixed the `Makefile` to use separate `.cpp` and `.c` compile rules.
- Added `pkg-config` SDL flags when available, with the old `-lSDL2 -lSDL2_ttf -lSDL2_gfx` fallback.
- Replaced unsafe `--server` copy with bounded copy and expanded `AppData::server` to 256 bytes.
- Added validation for port, latitude, longitude, screen index, UI scale, and screen size CLI arguments.
- Fixed a connection retry memory leak and reduced reconnect spam to one attempt per second while disconnected.
- Avoided divide-by-zero signal average when no aircraft are tracked.
- Initialized `Aircraft` fields so core logic is deterministic under tests/sanitizers.
- Added SDL display/window/renderer/texture error checks.
- Added SDL software renderer fallback for dummy/headless smoke tests.
- Initialized SDL pointers and destroyed SDL resources in `View::~View`.
- Fixed aircraft label bounds measurement so flight labels, not speed labels, drive the top label row size.

`make test`, `make sanitize`, and `git diff --check` pass locally. Full compile has not been verified because the Mac is missing active SDL2_ttf/SDL2_gfx headers.

## Next UI and Performance Work

Forks do not provide meaningful UI, performance, or library upgrade patches. The best improvements should come from the local codebase:

- Cache rendered text textures. `Label::draw`/TTF rendering appears to run every frame for status, scale bars, map names, and aircraft labels. Text caching by string/font/color would reduce CPU on the uConsole.
- Reduce label conflict cost. `View::draw` currently calls `resolveLabelConflicts()` eight times per frame while connected. That produces repeated aircraft-list scans and can become expensive in dense ADS-B areas. Add an early-exit threshold or run fewer passes on low-power profiles.
- Separate static and dynamic rendering. Geography is already rendered into `mapTexture`, but trails are drawn from `drawLines()` and therefore get baked into the map redraw path. Moving trails to the dynamic frame layer would make map caching cleaner and reduce redraw artifacts.
- Add a uConsole profile. A built-in `--profile uconsole` could set `--screensize 1280 720`, default `--uiscale 1`, cap label passes, and use map detail appropriate for the small display.
- Add display density controls. Useful toggles include hiding airport labels, hiding place labels below a zoom threshold, shortening trail history, and choosing high-contrast/day/night themes.
- Replace per-frame `pow()` scale-bar work with cached scale marks per `maxDist` bucket.
- Introduce a profiling build target, for example `make profile`, using `-O2 -g` plus platform-appropriate profiler flags. On Linux/uConsole, start with `perf`; on macOS, use Instruments or `sample`.

Library direction:

- Stay on SDL2 for the near term. SDL3 has a real migration path and tooling, but it changes headers, return conventions, and package names. It also does not directly replace this project's dependency on `SDL2_gfx` primitives.
- Prefer modernizing the build first. A small CMake or Meson build could use `pkg-config`/package discovery cleanly on macOS and Linux, and later make SDL3 experimentation easier.
- For the decoder, consider `readsb` or `dump1090-fa` on the uConsole instead of the older MalcolmRobb `dump1090`, as long as Beast output remains available on TCP port `30005`.

## Sources Checked

- Upstream repo and forks: https://github.com/nmatsuda/viz1090
- GitHub forks API: https://api.github.com/repos/nmatsuda/viz1090/forks?per_page=100
- ClockworkPi uConsole product page: https://www.clockworkpi.com/uconsole
- ClockworkPi forum search for uConsole SDR topics: https://forum.clockworkpi.com/search?q=uConsole%20SDR
- HackerGadgets uConsole SDR/AIO product search: https://hackergadgets.com/search?q=uConsole+SDR
- HackerGadgets AIO guide surfaced in search: https://hackergadgets.com/pages/hackergadgets-uconsole-rtl-sdr-lora-gps-rtc-usb-hub-all-in-one-extension-board-setup-guide
