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

The first Organic Maps patch should be narrow:

1. Add a runtime setting or CLI flag for an external aircraft GeoJSON path.
2. Poll the file every 500-1000 ms, using file mtime to skip unchanged reads.
3. Parse only the fields above.
4. Draw aircraft as a lightweight custom overlay layer using existing map projection APIs.
5. Keep labels optional and zoom-gated for uConsole performance.

Do not add SDR, dump1090, or Beast decoding code to Organic Maps. Keep RF and aviation protocol handling in viz1090/dump1090.

## uConsole Optimization Rules

- Prefer one map renderer at a time. For Organic Maps mode, run Organic Maps as the primary visual app and run viz1090 headless or minimized only as the feed producer.
- Use `/run/user/$(id -u)` for the feed path when available. It is tmpfs-backed and avoids unnecessary SD-card writes.
- Keep feed writes throttled. 500 ms is already aggressive enough for local aircraft motion.
- Avoid large labels at low zoom. Draw dots/triangles first; show labels only when zoomed in or selected.
- Do not poll map/weather/radio state from the Organic Maps render loop; use a timer or background task.
- Keep network/weather fallback separate from Organic Maps until the ADS-B overlay is stable.

## Near-Term Work

- Build Organic Maps desktop on the Mac or a Linux workstation.
- Identify the lightest overlay insertion point in Organic Maps.
- Add a proof-of-concept layer reading `viz1090-aircraft.geojson`.
- Validate runtime on uConsole before adding labels, trails, or weather.
- Only after aircraft overlay is stable, consider moving weather radar into the same Organic Maps overlay path.
