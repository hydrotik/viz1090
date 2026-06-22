// viz1090, a vizualizer for dump1090 ADSB output
//
// Copyright (C) 2020, Nathan Matsuda <info@nathanmatsuda.com>
// Copyright (C) 2014, Malcolm Robb <Support@ATTAvionics.com>
// Copyright (C) 2012, Salvatore Sanfilippo <antirez at gmail dot com>
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are
// met:
//
//  *  Redistributions of source code must retain the above copyright
//     notice, this list of conditions and the following disclaimer.
//
//  *  Redistributions in binary form must reproduce the above copyright
//     notice, this list of conditions and the following disclaimer in the
//     documentation and/or other materials provided with the distribution.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
// "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
// LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
// A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
// HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
// SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
// LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
// DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
// THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
// (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
//

#include "AppData.h"
#include "View.h"
#include "Input.h"
#include "OrganicMapsFeed.h"
#include <cerrno>
#include <climits>
#include <cstdio>
#include <cstdlib>
#include <cstring> 
int go = 1;


AppData appData;
Style style;

//
// ================================ Main ====================================
//
void showHelp(void) {
    printf(
"-----------------------------------------------------------------------------\n"
"|                        viz1090 ADSB Viewer        Ver : 0.1 |\n"
"-----------------------------------------------------------------------------\n"
"--fps                            Show current framerate\n"
"--fullscreen                     Start fullscreen\n"
"--help                           Show this help\n"
"--debug-input                    Print SDL input events to stdout\n"
"--lat <latitude>                 Latitude in degrees\n"
"--label-scale <factor>           Aircraft label scaling (default: 1.0)\n"
"--lon <longitude>                Longitude in degrees\n"
"--metric                         Use metric units\n"
"--organic-feed <path>            Write aircraft GeoJSON for an Organic Maps sidecar overlay\n"
"--organic-feed-interval-ms <ms>  Aircraft GeoJSON write interval, 100-60000 (default: 1000)\n"
"--plane-scale <factor>           Aircraft icon scaling (default: 1.0)\n"
"--port <port>                    TCP Beast output listen port (default: 30005)\n"
"--server <IPv4/hosname>          TCP Beast output listen IPv4 (default: 127.0.0.1)\n"
"--mapdir <path>                  Directory containing generated map files (default: .)\n"
"--screensize <width> <height>    Set frame buffer resolution (default: screen resolution)\n"
"--screenindex <i>                Set the index of the display to use (default: 0)\n"
"--simulate-weather               Draw a simulated moving radar storm cell\n"
"--status-scale <factor>          Bottom status text scaling (default: 1.0)\n"
"--theme <classic|atc|map|light>  Set UI/map color theme (default: classic)\n"
"--tiles <path>                   Offline raster tiles: MBTiles file or z/x/y tile directory\n"
"--tiles-mode <auto|mbtiles|xyz|tms> Raster tile source type (default: auto)\n"
"--tile-theme <auto|light|dark>    Raster tile color treatment (default: auto)\n"
"--tile-min-zoom <z>              Minimum raster tile zoom (default: 0)\n"
"--tile-max-zoom <z>              Maximum raster tile zoom (default: 17)\n"
"--tile-zoom-offset <n>           Adjust chosen raster tile zoom (default: 0)\n"
"--uiscale <factor>               UI global scaling (default: 1)\n"  
"--weather-file <path>            Radar tile cache file to render\n"
    );
}

static bool parseIntArg(const char *arg, int *out) {
    char *end = NULL;
    errno = 0;
    long value = strtol(arg, &end, 10);
    if(errno || end == arg || *end != '\0' || value < INT_MIN || value > INT_MAX) {
        return false;
    }

    *out = static_cast<int>(value);
    return true;
}

static bool parseFloatArg(const char *arg, float *out) {
    char *end = NULL;
    errno = 0;
    float value = strtof(arg, &end);
    if(errno || end == arg || *end != '\0') {
        return false;
    }

    *out = value;
    return true;
}

static void requireArgs(int argc, int current, int needed, const char *option) {
    if(current + needed >= argc) {
        fprintf(stderr, "Not enough arguments for option '%s'.\n\n", option);
        showHelp();
        exit(1);
    }
}


//
//=========================================================================
//


int main(int argc, char **argv) {
  
    AppData appData;
    View view(&appData);
    OrganicMapsFeed organicMapsFeed;
    bool debugInput = false;
    
    // Parse the command line options
    for (int j = 1; j < argc; j++) {
        if        (!strcmp(argv[j],"--port")) {
            requireArgs(argc, j, 1, argv[j]);
            if(!parseIntArg(argv[++j], &appData.modes.net_input_beast_port) || appData.modes.net_input_beast_port <= 0 || appData.modes.net_input_beast_port > 65535) {
                fprintf(stderr, "Invalid port '%s'.\n\n", argv[j]);
                showHelp();
                exit(1);
            }
        } else if (!strcmp(argv[j],"--server")) {
            requireArgs(argc, j, 1, argv[j]);
            std::snprintf(appData.server, sizeof(appData.server), "%s", argv[++j]);
        } else if (!strcmp(argv[j],"--mapdir")) {
            requireArgs(argc, j, 1, argv[j]);
            view.map.setDataDir(argv[++j]);
        } else if (!strcmp(argv[j],"--weather-file")) {
            requireArgs(argc, j, 1, argv[j]);
            view.weather_file = argv[++j];
        } else if (!strcmp(argv[j],"--tiles")) {
            requireArgs(argc, j, 1, argv[j]);
            view.raster_tile_source = argv[++j];
            view.mapRedraw = 1;
        } else if (!strcmp(argv[j],"--tiles-mode")) {
            requireArgs(argc, j, 1, argv[j]);
            const char *mode = argv[++j];
            if(strcmp(mode, "auto") && strcmp(mode, "mbtiles") && strcmp(mode, "xyz") && strcmp(mode, "tms")) {
                fprintf(stderr, "Invalid tiles mode '%s'. Expected auto, mbtiles, xyz, or tms.\n\n", mode);
                showHelp();
                exit(1);
            }
            view.raster_tile_mode = mode;
            view.mapRedraw = 1;
        } else if (!strcmp(argv[j],"--tile-theme")) {
            requireArgs(argc, j, 1, argv[j]);
            const char *theme = argv[++j];
            if(strcmp(theme, "auto") && strcmp(theme, "light") && strcmp(theme, "dark")) {
                fprintf(stderr, "Invalid tile theme '%s'. Expected auto, light, or dark.\n\n", theme);
                showHelp();
                exit(1);
            }
            view.raster_tile_theme = !strcmp(theme, "light") ? "normal" : theme;
            view.mapRedraw = 1;
        } else if (!strcmp(argv[j],"--tile-min-zoom")) {
            requireArgs(argc, j, 1, argv[j]);
            if(!parseIntArg(argv[++j], &view.raster_tile_min_zoom) || view.raster_tile_min_zoom < 0 || view.raster_tile_min_zoom > 22) {
                fprintf(stderr, "Invalid tile min zoom '%s'. Expected 0 to 22.\n\n", argv[j]);
                showHelp();
                exit(1);
            }
        } else if (!strcmp(argv[j],"--tile-max-zoom")) {
            requireArgs(argc, j, 1, argv[j]);
            if(!parseIntArg(argv[++j], &view.raster_tile_max_zoom) || view.raster_tile_max_zoom < 0 || view.raster_tile_max_zoom > 22) {
                fprintf(stderr, "Invalid tile max zoom '%s'. Expected 0 to 22.\n\n", argv[j]);
                showHelp();
                exit(1);
            }
        } else if (!strcmp(argv[j],"--tile-zoom-offset")) {
            requireArgs(argc, j, 1, argv[j]);
            if(!parseIntArg(argv[++j], &view.raster_tile_zoom_offset) || view.raster_tile_zoom_offset < -4 || view.raster_tile_zoom_offset > 4) {
                fprintf(stderr, "Invalid tile zoom offset '%s'. Expected -4 to 4.\n\n", argv[j]);
                showHelp();
                exit(1);
            }
        } else if (!strcmp(argv[j],"--lat")) {
            requireArgs(argc, j, 1, argv[j]);
            float lat = 0.0f;
            if(!parseFloatArg(argv[++j], &lat) || lat < -90.0f || lat > 90.0f) {
                fprintf(stderr, "Invalid latitude '%s'.\n\n", argv[j]);
                showHelp();
                exit(1);
            }
            appData.modes.fUserLat = lat;
            view.centerLat = appData.modes.fUserLat;
            view.currentLat = view.centerLat;
        } else if (!strcmp(argv[j],"--lon")) {
            requireArgs(argc, j, 1, argv[j]);
            float lon = 0.0f;
            if(!parseFloatArg(argv[++j], &lon) || lon < -180.0f || lon > 180.0f) {
                fprintf(stderr, "Invalid longitude '%s'.\n\n", argv[j]);
                showHelp();
                exit(1);
            }
            appData.modes.fUserLon = lon;
            view.centerLon = appData.modes.fUserLon;
            view.currentLon = view.centerLon;
        } else if (!strcmp(argv[j],"--metric")) {
            view.metric = 1;
        } else if (!strcmp(argv[j],"--organic-feed")) {
            requireArgs(argc, j, 1, argv[j]);
            organicMapsFeed.setPath(argv[++j]);
        } else if (!strcmp(argv[j],"--organic-feed-interval-ms")) {
            requireArgs(argc, j, 1, argv[j]);
            int intervalMs = 0;
            if(!parseIntArg(argv[++j], &intervalMs) || !organicMapsFeed.setIntervalMs(intervalMs)) {
                fprintf(stderr, "Invalid Organic Maps feed interval '%s'. Expected 100 to 60000 ms.\n\n", argv[j]);
                showHelp();
                exit(1);
            }
        } else if (!strcmp(argv[j],"--plane-scale")) {
            requireArgs(argc, j, 1, argv[j]);
            if(!parseFloatArg(argv[++j], &view.plane_scale) || view.plane_scale < 0.5f || view.plane_scale > 4.0f) {
                fprintf(stderr, "Invalid plane scale '%s'. Expected 0.5 to 4.0.\n\n", argv[j]);
                showHelp();
                exit(1);
            }
        } else if (!strcmp(argv[j],"--label-scale")) {
            requireArgs(argc, j, 1, argv[j]);
            if(!parseFloatArg(argv[++j], &view.label_scale) || view.label_scale < 0.5f || view.label_scale > 4.0f) {
                fprintf(stderr, "Invalid label scale '%s'. Expected 0.5 to 4.0.\n\n", argv[j]);
                showHelp();
                exit(1);
            }
        } else if (!strcmp(argv[j],"--status-scale")) {
            requireArgs(argc, j, 1, argv[j]);
            if(!parseFloatArg(argv[++j], &view.status_scale) || view.status_scale < 0.5f || view.status_scale > 4.0f) {
                fprintf(stderr, "Invalid status scale '%s'. Expected 0.5 to 4.0.\n\n", argv[j]);
                showHelp();
                exit(1);
            }
        } else if (!strcmp(argv[j],"--fps")) {
            view.fps = 1;
        } else if (!strcmp(argv[j],"--debug-input")) {
            debugInput = true;
        } else if (!strcmp(argv[j],"--fullscreen")) {
            view.fullscreen = 1;
        } else if (!strcmp(argv[j],"--simulate-weather")) {
            view.simulate_weather = true;
        } else if (!strcmp(argv[j],"--theme")) {
            requireArgs(argc, j, 1, argv[j]);
            const char *themeName = argv[++j];
            if(!view.setTheme(themeName)) {
                fprintf(stderr, "Invalid theme '%s'. Valid themes: classic, atc, map, light.\n\n", themeName);
                showHelp();
                exit(1);
            }
        } else if (!strcmp(argv[j],"--screenindex")) {
            requireArgs(argc, j, 1, argv[j]);
            if(!parseIntArg(argv[++j], &view.screen_index) || view.screen_index < 0) {
                fprintf(stderr, "Invalid screen index '%s'.\n\n", argv[j]);
                showHelp();
                exit(1);
            }
        } else if (!strcmp(argv[j],"--uiscale")) {
            requireArgs(argc, j, 1, argv[j]);
            if(!parseIntArg(argv[++j], &view.screen_uiscale) || view.screen_uiscale < 1) {
                fprintf(stderr, "Invalid UI scale '%s'.\n\n", argv[j]);
                showHelp();
                exit(1);
            }
         } else if (!strcmp(argv[j],"--screensize")) {
            requireArgs(argc, j, 2, argv[j]);
            if(!parseIntArg(argv[++j], &view.screen_width) || view.screen_width <= 0 ||
               !parseIntArg(argv[++j], &view.screen_height) || view.screen_height <= 0) {
                fprintf(stderr, "Invalid screen size.\n\n");
                showHelp();
                exit(1);
            }
        } else if (!strcmp(argv[j],"--help")) {
            showHelp();
            exit(0);
        } else {
            fprintf(stderr, "Unknown or not enough arguments for option '%s'.\n\n", argv[j]);
            showHelp();
            exit(1);
        }
    }

    if(view.raster_tile_min_zoom > view.raster_tile_max_zoom) {
        fprintf(stderr, "Tile min zoom cannot be greater than tile max zoom.\n\n");
        showHelp();
        exit(1);
    }

    appData.initialize();
    view.startMapLoad();

    view.SDL_init();
    view.font_init();

    Input input(&appData,&view);
    input.debugInput = debugInput;

    signal(SIGINT, SIG_DFL);  // reset signal handler - bit extra safety

    int go;
 
    go = 1;
          
    while (go == 1)
    {
        input.getInput();
        view.draw();
        appData.connect();
        appData.update();
        organicMapsFeed.update(&appData);
    }
    
    appData.disconnect();

    return (0);
}
//
//=========================================================================
//
