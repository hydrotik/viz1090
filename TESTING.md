# Testing

This repo now has a small regression foundation. It is intentionally split into tests that do not need SDL and smoke tests that need a full app build.

## Fast Local Tests

```sh
make test
```

This runs:

- `test-core`: C/C++ tests for aircraft state, aircraft list behavior, and Mode S decode fixtures.
- `test-mapconverter`: Python tests for map conversion helpers.
- `test-fixtures`: validates Beast replay fixtures can be loaded and framed.

## Sanitizers

```sh
make sanitize
```

This rebuilds and runs the fast test suite with AddressSanitizer and UndefinedBehaviorSanitizer. It does not build the SDL app.

## Full App Build

```sh
make viz1090
```

This needs SDL2, SDL2_ttf, and SDL2_gfx development headers.

## Headless UI Smoke Test

```sh
make smoke-ui
```

This builds `viz1090`, starts a local Beast TCP replay server from `tests/fixtures/beast_messages.hex`, and runs the app briefly with `SDL_VIDEODRIVER=dummy`.

## Replay Benchmark Smoke

```sh
make benchmark-smoke
```

This runs the same replay path longer and at a higher fixture rate. It is a smoke/perf harness, not a precise benchmark yet. Use it to compare obvious regressions between the Mac and uConsole with the same deterministic ADS-B input.

## CI

```sh
make ci
```

CI runs fast tests, sanitizer tests, full build, and the headless UI smoke test. GitHub Actions is configured in `.github/workflows/ci.yml` for Linux.

## Current Mac Blocker

On the current Apple Silicon Mac, `make viz1090` is blocked because `SDL2/SDL_ttf.h` is not visible to the active compiler. `make test` and `make sanitize` do pass because they do not require SDL.

## uConsole Plan

Once the uConsole is reachable from this Mac:

1. Pull or copy the repo onto the uConsole.
2. Install Linux dependencies from `LLM.md`.
3. Run `make test`.
4. Run `make sanitize` if the image/toolchain supports sanitizers.
5. Run `make viz1090`.
6. Run `make smoke-ui`.
7. Run `make benchmark-smoke` and record timing/CPU observations.
8. Test the real SDR path with `dump1090`/`readsb --net` feeding port `30005`.
