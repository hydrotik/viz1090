// viz1090, a vizualizer for dump1090 ADSB output
//
// Copyright (C) 2020, Nathan Matsuda <info@nathanmatsuda.com>
// Copyright (C) 2014, Malcolm Robb <Support@ATTAvionics.com>
// Copyright (C) 2012, Salvatore Sanfilippo <antirez at gmail dot com>
// All rights reserved.

#include "OrganicMapsFeed.h"
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <sstream>

static std::chrono::steady_clock::time_point steadyNow() {
    return std::chrono::steady_clock::now();
}

static std::string jsonEscape(const char *input) {
    std::ostringstream out;

    for(const char *p = input; p && *p; p++) {
        unsigned char c = static_cast<unsigned char>(*p);
        switch(c) {
            case '\\':
                out << "\\\\";
                break;
            case '"':
                out << "\\\"";
                break;
            case '\b':
                out << "\\b";
                break;
            case '\f':
                out << "\\f";
                break;
            case '\n':
                out << "\\n";
                break;
            case '\r':
                out << "\\r";
                break;
            case '\t':
                out << "\\t";
                break;
            default:
                if(c < 0x20) {
                    char escaped[7];
                    std::snprintf(escaped, sizeof(escaped), "\\u%04x", c);
                    out << escaped;
                } else {
                    out << static_cast<char>(c);
                }
                break;
        }
    }

    return out.str();
}

OrganicMapsFeed::OrganicMapsFeed() {
    intervalMs = 1000;
    lastWrite = std::chrono::steady_clock::time_point();
}

void OrganicMapsFeed::setPath(const std::string &newPath) {
    path = newPath;
}

bool OrganicMapsFeed::enabled() const {
    return !path.empty();
}

bool OrganicMapsFeed::setIntervalMs(int newIntervalMs) {
    if(newIntervalMs < 100 || newIntervalMs > 60000) {
        return false;
    }

    intervalMs = newIntervalMs;
    return true;
}

void OrganicMapsFeed::update(AppData *appData) {
    if(!enabled()) {
        return;
    }

    std::chrono::steady_clock::time_point current = steadyNow();
    if(lastWrite.time_since_epoch().count() != 0 &&
       std::chrono::duration_cast<std::chrono::milliseconds>(current - lastWrite).count() < intervalMs) {
        return;
    }

    if(writeAtomic(buildGeoJson(appData))) {
        lastWrite = current;
    }
}

std::string OrganicMapsFeed::buildGeoJson(AppData *appData) const {
    std::ostringstream out;
    out.precision(7);
    out << "{\"type\":\"FeatureCollection\",\"features\":[";

    bool first = true;
    Aircraft *aircraft = appData->aircraftList.head;
    while(aircraft) {
        if(aircraft->lon != 0.0f && aircraft->lat != 0.0f) {
            if(!first) {
                out << ",";
            }
            first = false;

            out << "{\"type\":\"Feature\",\"geometry\":{\"type\":\"Point\",\"coordinates\":[";
            out << aircraft->lon << "," << aircraft->lat;
            out << "]},\"properties\":{";
            out << "\"icao\":\"";
            char icao[9];
            std::snprintf(icao, sizeof(icao), "%06X", aircraft->addr);
            out << icao << "\"";
            out << ",\"flight\":\"" << jsonEscape(aircraft->flight) << "\"";
            out << ",\"altitude\":" << aircraft->altitude;
            out << ",\"speed\":" << aircraft->speed;
            out << ",\"track\":" << aircraft->track;
            out << ",\"vertical_rate\":" << aircraft->vert_rate;
            out << ",\"seen\":" << static_cast<long long>(aircraft->seen);
            out << "}}";
        }
        aircraft = aircraft->next;
    }

    out << "]}";
    return out.str();
}

bool OrganicMapsFeed::writeAtomic(const std::string &payload) const {
    std::string tmpPath = path + ".tmp";

    {
        std::ofstream out(tmpPath.c_str(), std::ios::out | std::ios::trunc);
        if(!out.good()) {
            std::fprintf(stderr, "Could not write Organic Maps feed %s: %s\n", tmpPath.c_str(), std::strerror(errno));
            return false;
        }

        out << payload << "\n";
    }

    if(std::rename(tmpPath.c_str(), path.c_str()) != 0) {
        std::fprintf(stderr, "Could not publish Organic Maps feed %s: %s\n", path.c_str(), std::strerror(errno));
        std::remove(tmpPath.c_str());
        return false;
    }

    return true;
}
