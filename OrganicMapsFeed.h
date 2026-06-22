// viz1090, a vizualizer for dump1090 ADSB output
//
// Copyright (C) 2020, Nathan Matsuda <info@nathanmatsuda.com>
// Copyright (C) 2014, Malcolm Robb <Support@ATTAvionics.com>
// Copyright (C) 2012, Salvatore Sanfilippo <antirez at gmail dot com>
// All rights reserved.

#ifndef ORGANIC_MAPS_FEED_H
#define ORGANIC_MAPS_FEED_H

#include "AppData.h"
#include <chrono>
#include <string>

class OrganicMapsFeed {
public:
    OrganicMapsFeed();

    void setPath(const std::string &path);
    bool enabled() const;
    bool setIntervalMs(int intervalMs);
    void update(AppData *appData);
    std::string buildGeoJson(AppData *appData) const;

private:
    std::string path;
    int intervalMs;
    std::chrono::steady_clock::time_point lastWrite;

    bool writeAtomic(const std::string &payload) const;
};

#endif
