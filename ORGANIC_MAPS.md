# Organic Maps Integration

This project is moving toward Organic Maps as the high-fidelity offline map engine for car-friendly and navigation-style views.

Organic Maps should be treated as a sibling application/engine, not as vendored source inside viz1090. The optimized split is:

- Organic Maps renders the offline OSM map, GPS/navigation UI, gestures, search, and routing.
- viz1090 or dump1090 owns SDR/ADS-B decoding and publishes a small local aircraft overlay feed.
- A small Organic Maps patch consumes the local feed and draws aircraft symbols above the map.

This avoids running two complete map renderers in one process and keeps the uConsole runtime path simple.

## Why Not Embed Organic Maps Directly?

Organic Maps is a full C++/Qt/OpenGL application with its own map data format, generator, routing, search, styles, and UI. It is not a drop-in SDL widget for viz1090.

The Organic Maps source is open, but its binary map data files have a separate license. If this project uses Organic Maps `.mwm` data files or Organic Maps UI/source in a distributed app, the app needs visible Organic Maps and OpenStreetMap attribution. See:

- https://github.com/organicmaps/organicmaps
- https://github.com/organicmaps/organicmaps/blob/master/DATA_LICENSE.txt
- https://github.com/organicmaps/organicmaps/blob/master/docs/INSTALL.md

## Local Checkout

Clone Organic Maps into an ignored local workspace:

```sh
tools/bootstrap_organicmaps.sh
```

This creates `external/organicmaps`, which is intentionally ignored by git.

Organic Maps is large. Build it on the Mac or a Linux workstation first, then decide whether the uConsole should run the resulting desktop app or a smaller custom fork. The uConsole is not the fastest place to compile Organic Maps.

On an Apple Silicon Mac, build the native desktop app with:

```sh
tools/apply_organicmaps_overlay.sh
tools/build_organicmaps_macos.sh
```

The helper uses `/opt/homebrew` by default on arm64 and writes the app to:

```sh
external/omim-build-arm64/omim-build-release/OMaps.app
```

If a previous Rosetta/Intel build exists in `external/omim-build-release`, leave it as a fallback; do not mix that build directory with the native arm64 build.

The overlay patch is tracked in this repository as:

```sh
tools/organicmaps_viz1090_aircraft_overlay.patch
```

It adds the Organic Maps desktop flag:

```sh
--viz1090_aircraft_feed <path>
```

Run the patched Mac app against a local copy of the uConsole feed with:

```sh
external/omim-build-arm64/omim-build-release/OMaps.app/Contents/MacOS/OMaps \
  --viz1090_aircraft_feed /tmp/viz1090-aircraft.geojson
```

For a quick live Mac-side check while the feed is produced on the uConsole, copy it over SSH in a loop:

```sh
while true; do
  scp djdonovan@192.168.1.195:/run/user/1000/viz1090-aircraft.geojson /tmp/viz1090-aircraft.geojson.tmp &&
    mv /tmp/viz1090-aircraft.geojson.tmp /tmp/viz1090-aircraft.geojson
  sleep 1
done
```

## ADS-B Overlay Feed

viz1090 can now publish a compact aircraft GeoJSON file for an Organic Maps sidecar overlay:

```sh
./run_uconsole.sh --organic-feed /run/user/$(id -u)/viz1090-aircraft.geojson
```

Raw viz1090 equivalent:

```sh
./viz1090 --organic-feed /run/user/$(id -u)/viz1090-aircraft.geojson
```

The feed is written atomically once per second by default. Tune the interval if needed:

```sh
./run_uconsole.sh \
  --organic-feed /run/user/$(id -u)/viz1090-aircraft.geojson \
  --organic-feed-interval-ms 500
```

The feed shape is a GeoJSON `FeatureCollection` of point features:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [-73.845139, 40.723972]
      },
      "properties": {
        "icao": "ABC123",
        "flight": "TEST123",
        "altitude": 12000,
        "speed": 250,
        "track": 85,
        "vertical_rate": 0,
        "seen": 1782070000
      }
    }
  ]
}
```

## Organic Maps Patch Target

The current Organic Maps patch is intentionally narrow:

1. Adds `--viz1090_aircraft_feed`.
2. Polls the file by mtime/size from the Qt draw path.
3. Parses only the GeoJSON fields emitted by viz1090.
4. Draws aircraft markers above the desktop Organic Maps map using the current viewport projection.
5. Shows compact labels only when the map is zoomed in enough.

Do not add SDR, dump1090, or Beast decoding code to Organic Maps. Keep RF and aviation protocol handling in viz1090/dump1090.

## uConsole Optimization Rules

- Prefer one map renderer at a time. For Organic Maps mode, run Organic Maps as the primary visual app and run viz1090 headless or minimized only as the feed producer.
- Use `/run/user/$(id -u)` for the feed path when available. It is tmpfs-backed and avoids unnecessary SD-card writes.
- Keep feed writes throttled. 500 ms is already aggressive enough for local aircraft motion.
- Avoid large labels at low zoom. Draw dots/triangles first; show labels only when zoomed in or selected.
- Do not poll map/weather/radio state from the Organic Maps render loop; use a timer or background task.
- Keep network/weather fallback separate from Organic Maps until the ADS-B overlay is stable.

## Near-Term Work

- Validate the patched desktop overlay visually with a live copied uConsole feed.
- Decide whether to run patched Organic Maps on the uConsole or keep it as the Mac/high-fidelity view.
- If uConsole runtime is acceptable, build/test the patched Organic Maps checkout on Linux/aarch64.
- Only after aircraft overlay is stable, consider moving weather radar into the same Organic Maps overlay path.
