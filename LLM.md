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
- `airportdata.bin`
- `mapnames`
- `airportnames`

Recommended uConsole regional map for the observed New York coordinates:

```sh
cd ~/viz1090
./run_uconsole.sh
```

`run_uconsole.sh` builds the binary when needed, generates `mapdata/generated/nyc` when missing, and launches with `--theme atc`, `--mapdir mapdata/generated/nyc`, `--screensize 1280 720`, and the observed coordinates. It tries to read GPS first via `tools/gps_fix.py`, then falls back to the configured/default `--lat` and `--lon`; use `--no-gps` to skip GPS. Its default map tolerance is `0.0001` for more local detail than the original `0.001`; use `--regen-map --tolerance 0.00005` for a denser local map if rendering remains fast enough. It defaults to `--plane-scale 1.5 --label-scale 1.9 --status-scale 1.8` so aircraft, aircraft labels, and the bottom status strip are readable on the uConsole's small high-resolution screen without doubling all UI.

When syncing code from the Mac to the uConsole, keep `mapdata/` out of `rsync --delete` operations. `mapdata/cache` and `mapdata/generated` are device-local offline assets and should survive source updates unless intentionally regenerated.

The generated vector map now combines state/province outlines, coastlines, local roads when a `--bbox` is provided, airport labels, and runway geometry. FAA runway outline downloads are optional; if that ArcGIS endpoint fails, `getmap.sh` falls back to OurAirports `runways.csv` and generates runway centerlines. The original admin-boundary-only map can look blank at a close 25 km New York zoom, so coastlines/roads/runways are important for a visible local map.

Aircraft labels include heuristic category markers:

- Green dot: likely commercial based on common airline callsign prefixes/patterns.
- Orange dot: likely government/military based on common callsign prefixes or US military ICAO range.
- No dot: unknown. This is not authoritative; better classification needs a local aircraft/operator database.

uConsole input support:

- Trackball pointer movement is handled as normal SDL mouse motion.
- Left-click drag pans the map.
- Mouse wheel events zoom when the OS/input device emits them.
- Arrow keys, WASD, and HJKL pan.
- `+`, keypad `+`, and PageUp zoom in.
- `-`, keypad `-`, and PageDown zoom out.
- uConsole controller/D-pad events pan when SDL exposes the top arrow controls as controller or joystick hat input.
- uConsole `X`/`R` zoom in, `Y`/`L` zoom out, `A` recenters, and `B` toggles dark/light mode when SDL exposes those buttons as controller input. Raw joystick fallback maps button indices `0=A`, `1=B`, `2=X`, `3=Y`, `4=L`, `5=R`.
- Home or `r` recenters on the configured latitude/longitude.
- `t` toggles between ATC dark mode and light mode.

Use `./run_uconsole.sh --debug-input` to print SDL input events when validating the physical uConsole keys. This is especially useful because some uConsole controls may appear as mouse buttons instead of keyboard/controller buttons; observed behavior included the `L` control acting like a left click/double click.

After one successful online run, the same map can be regenerated without network:

```sh
./getmap.sh --offline --output-dir mapdata/generated/nyc --bbox -75,39.8,-71.8,42.2
```

Use `--theme atc` for the high-contrast radar/WarGames-style view, `--theme map` for a muted vector-map look, and `--theme classic` for the original palette. If map drawing is slow, increase `mapconverter.py --tolerance` above the default `0.001` and/or raise `--minpop` to reduce labels.

For the uConsole, consider generating on the Mac after Python/GIS dependencies are installed, then copying the generated output directory to the uConsole. True Mapbox-like offline tiles should be treated as a later optional renderer path, likely via MBTiles/PMTiles, because it is larger and heavier than this SDL vector renderer.

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
2. Raw NMEA from known serial devices, including the observed ClockworkPi `/dev/ttyACM0` path.

If no fix is available within `--gps-timeout`, `run_uconsole.sh` continues with configured coordinates.

Future GPS/tracking revisit:

- Decide whether GPS should be enabled by default once outdoor testing confirms reliable fixes.
- Consider continuously tracking GPS while the app runs, not just startup location.
- Add an explicit on-screen indication for `gps` versus configured/fallback location.
- Consider map auto-recenter on moving GPS location for car use, with a key to pause/resume follow mode.

## OTA Weather Possibilities

Radar/precipitation over RF is most realistically obtained through ADS-B In FIS-B on UAT 978 MHz in the United States, not through the existing 1090 MHz `dump1090` traffic path. FAA documentation states FIS-B is broadcast on UAT and includes products such as METAR, CONUS/Regional NEXRAD, NOTAM, PIREP, TAF, winds aloft, and other weather/aeronautical products. Garmin notes additional FIS-B weather products such as lightning, cloud tops, icing, and turbulence, but radar/precipitation is the first useful target.

Implementation options:

- Best: use a second SDR/tuner for 978 MHz UAT while the current RTL-SDR remains on 1090 MHz ADS-B. Multiple antennas do not guarantee simultaneous receive; simultaneous 1090+978 requires multiple tuners or a receiver capable of independent concurrent channels.
- Possible with one RTL-SDR: periodically stop or pause the 1090 MHz decoder, retune to 978 MHz, run a UAT/FIS-B decoder such as `dump978` for a short window, cache decoded weather products, then return to 1090 MHz. A 4 minute cycle is plausible for slowly changing weather, but aircraft updates will be missed during UAT receive windows.
- NOAA Weather Radio around 162 MHz provides audio/text-style weather alerts, not radar images.
- NOAA APT/HRPT/GOES satellite paths are different RF systems and not a good fit for quick local radar in this handheld workflow.

Near-term radar-only weather plan:

1. Install/test `dump978` or `dump978-fa` on the uConsole.
2. Verify whether the installed SDR expansion exposes one tuner or multiple tuners.
3. If one tuner: create a scheduler that samples 978 MHz every few minutes and writes decoded FIS-B radar/NEXRAD artifacts to disk, then returns to `dump1090-mutability`.
4. Add a radar overlay reader in viz1090 after decoded FIS-B radar artifacts are available.
5. Defer non-radar products such as lightning, cloud tops, icing, turbulence, NOTAMs, and text weather until the radar path is proven.

Weather UI validation:

- `--simulate-weather` draws a simulated moving NEXRAD-like radar tile grid over the map under aircraft.
- `./run_uconsole.sh --simulate-weather` is the uConsole validation path.
- `tools/generate_weather_fixture.py` can write a static `weather/radar_tiles.csv` cache for UI screenshots/tests.
- `--weather-file <path>` renders rows of `lat_min,lon_min,lat_max,lon_max,intensity`, where intensity is 1 green, 2 yellow, 3 red, 4 magenta.
- This is only a UI overlay simulator; it is not live weather and should not be used for navigation decisions.

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
