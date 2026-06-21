# viz1090 Controls

This file is the authoritative key map for keyboard, mouse, and observed ClockworkPi uConsole controls.

## Standard Keyboard and Pointer

| Control | Action |
| --- | --- |
| Up / `W` / `K` | Pan north |
| Down / `S` / `J` | Pan south |
| Left / `A` / `H` | Pan west |
| Right / `D` / keyboard `L` | Pan east |
| `+` / keypad `+` / PageUp | Zoom in |
| `-` / keypad `-` / PageDown | Zoom out |
| Home / keyboard `R` | Recenter on configured or GPS-derived location |
| Keyboard `T` | Toggle ATC dark mode and light mode |
| Escape | Quit |
| Mouse or trackball left-click drag | Pan map by drag |
| Mouse wheel | Zoom, when the OS/input device emits wheel events |
| Single click near aircraft | Select nearest aircraft |
| Double click | Zoom toward clicked location |

## uConsole Physical Keys

Observed on the uConsole on 2026-06-21:

| Physical control | SDL event observed | Action |
| --- | --- | --- |
| Top Up | `key sym=Up scancode=Up` | Pan north |
| Top Down | `key sym=Down scancode=Down` | Pan south |
| Top Left | `key sym=Left scancode=Left` | Pan west |
| Top Right | `key sym=Right scancode=Right` | Pan east |
| `L` | `mouse up which=0 button=1 clicks=1 x=0 y=0` | Zoom out |
| `R` | `mouse up which=0 button=3 clicks=1 x=0 y=0` | Zoom in |
| `X` | `joystick button joy=0 button=0` | Zoom in |
| `Y` | `joystick button joy=0 button=3` | Zoom out |
| `A` | `joystick button joy=0 button=1` | Recenter |
| `B` | `joystick button joy=0 button=2` | Toggle ATC dark mode and light mode |
| Trackball press | `mouse button=2` at pointer location | Normal middle mouse click; currently no map command |

`L` and `R` are intentionally intercepted only when they arrive as synthetic mouse events at `(0,0)`, so normal trackball clicks still work as pointer input.

## Debugging Input

Run:

```sh
./run_uconsole.sh --debug-input
```

Press the physical key and read the terminal output. The app prints whether SDL received a keyboard key, mouse button, controller button, raw joystick button, joystick hat/D-pad event, or mouse wheel event. Update this file and `Input.cpp` together if the uConsole firmware or OS reports different button numbers.
