#include "AircraftList.h"
#include "Map.h"
#include "OrganicMapsFeed.h"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

static int failures = 0;

#define CHECK_TRUE(expr) do { \
    if(!(expr)) { \
        std::fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #expr); \
        failures++; \
    } \
} while(0)

#define CHECK_EQ(actual, expected) do { \
    long long actualValue = static_cast<long long>(actual); \
    long long expectedValue = static_cast<long long>(expected); \
    if(actualValue != expectedValue) { \
        std::fprintf(stderr, "FAIL %s:%d: %s == %lld, expected %lld\n", __FILE__, __LINE__, #actual, actualValue, expectedValue); \
        failures++; \
    } \
} while(0)

static void checkNear(double actual, double expected, double tolerance, const char *name) {
    if(std::fabs(actual - expected) > tolerance) {
        std::fprintf(stderr, "FAIL %s: %.8f, expected %.8f +/- %.8f\n", name, actual, expected, tolerance);
        failures++;
    }
}

static std::vector<unsigned char> hexToBytes(const char *hex) {
    std::vector<unsigned char> bytes;
    size_t len = std::strlen(hex);
    CHECK_TRUE((len % 2) == 0);

    for(size_t i = 0; i + 1 < len; i += 2) {
        char pair[3] = {hex[i], hex[i + 1], '\0'};
        bytes.push_back(static_cast<unsigned char>(std::strtoul(pair, NULL, 16)));
    }

    return bytes;
}

static void initModes(Modes *modes) {
    std::memset(modes, 0, sizeof(*modes));
    modes->check_crc = 1;
    modes->quiet = 1;
    modes->interactive_delete_ttl = MODES_INTERACTIVE_DELETE_TTL;
    modes->interactive_display_ttl = MODES_INTERACTIVE_DISPLAY_TTL;
    modes->fUserLat = 0.0;
    modes->fUserLon = 0.0;
    modes->icao_cache = static_cast<uint32_t *>(std::calloc(MODES_ICAO_CACHE_LEN * 2, sizeof(uint32_t)));
    CHECK_TRUE(modes->icao_cache != NULL);
    modesInitErrorInfo(modes);
}

static void freeAircrafts(Modes *modes) {
    struct aircraft *a = modes->aircrafts;
    while(a) {
        struct aircraft *next = a->next;
        std::free(a);
        a = next;
    }
    modes->aircrafts = NULL;
    std::free(modes->icao_cache);
    modes->icao_cache = NULL;
}

static void decodeHex(Modes *modes, const char *hex) {
    std::vector<unsigned char> bytes = hexToBytes(hex);
    struct modesMessage mm;
    std::memset(&mm, 0, sizeof(mm));
    mm.remote = 1;
    decodeModesMessage(modes, &mm, bytes.data());
    useModesMessage(modes, &mm);
}

static void testAircraftHistory() {
    Aircraft aircraft(0xabc123);
    CHECK_EQ(aircraft.getLastLon(), 0);
    CHECK_EQ(aircraft.getLastLat(), 0);
    CHECK_EQ(aircraft.getLastHeading(), 0);

    aircraft.lonHistory.push_back(-122.0f);
    aircraft.latHistory.push_back(47.0f);
    aircraft.headingHistory.push_back(90.0f);
    CHECK_EQ(aircraft.getLastLon(), 0);
    CHECK_EQ(aircraft.getLastLat(), 0);
    CHECK_EQ(aircraft.getLastHeading(), 0);

    aircraft.lonHistory.push_back(-121.5f);
    aircraft.latHistory.push_back(47.5f);
    aircraft.headingHistory.push_back(180.0f);
    checkNear(aircraft.getLastLon(), -122.0, 0.0001, "Aircraft::getLastLon");
    checkNear(aircraft.getLastLat(), 47.0, 0.0001, "Aircraft::getLastLat");
    checkNear(aircraft.getLastHeading(), 90.0, 0.0001, "Aircraft::getLastHeading");
}

static void testAircraftListUpdateAndRemoval() {
    Modes modes;
    std::memset(&modes, 0, sizeof(modes));

    struct aircraft raw;
    std::memset(&raw, 0, sizeof(raw));
    raw.addr = 0x123456;
    std::memcpy(raw.flight, "TEST123 ", 8);
    raw.signalLevel[0] = 42;
    raw.seen = 10;
    raw.seenLatLon = 10;
    raw.altitude = 12000;
    raw.speed = 250;
    raw.track = 85;
    raw.vert_rate = 64;
    raw.lat = 47.61;
    raw.lon = -122.33;
    modes.aircrafts = &raw;

    AircraftList list;
    list.update(&modes);

    Aircraft *tracked = list.find(raw.addr);
    CHECK_TRUE(tracked != NULL);
    CHECK_EQ(tracked->addr, raw.addr);
    CHECK_EQ(tracked->altitude, 12000);
    CHECK_EQ(tracked->speed, 250);
    CHECK_EQ(tracked->track, 85);
    CHECK_EQ(tracked->lonHistory.size(), 1);
    CHECK_EQ(tracked->latHistory.size(), 1);
    CHECK_EQ(tracked->headingHistory.size(), 1);

    list.update(&modes);
    tracked = list.find(raw.addr);
    CHECK_TRUE(tracked != NULL);
    CHECK_EQ(tracked->lonHistory.size(), 1);

    raw.seen = 11;
    raw.seenLatLon = 11;
    raw.lat = 47.62;
    raw.lon = -122.34;
    list.update(&modes);
    tracked = list.find(raw.addr);
    CHECK_TRUE(tracked != NULL);
    CHECK_EQ(tracked->lonHistory.size(), 2);
    checkNear(tracked->messageRate, 1.0, 0.0001, "AircraftList messageRate");

    modes.aircrafts = NULL;
    list.update(&modes);
    CHECK_TRUE(list.head == NULL);
}

static void testModeSCallsignFixture() {
    Modes modes;
    initModes(&modes);

    decodeHex(&modes, "8D4840D6202CC371C32CE0576098");
    struct aircraft *a = interactiveFindAircraft(&modes, 0x4840D6);
    CHECK_TRUE(a != NULL);
    CHECK_TRUE(a && std::strncmp(a->flight, "KLM1023", 7) == 0);
    CHECK_TRUE(a && (a->bFlags & MODES_ACFLAGS_CALLSIGN_VALID));

    freeAircrafts(&modes);
}

static void testModeSPositionFixture() {
    Modes modes;
    initModes(&modes);

    decodeHex(&modes, "8D40621D58C382D690C8AC2863A7");
    decodeHex(&modes, "8D40621D58C386435CC412692AD6");

    struct aircraft *a = interactiveFindAircraft(&modes, 0x40621D);
    CHECK_TRUE(a != NULL);
    CHECK_TRUE(a && (a->bFlags & MODES_ACFLAGS_LATLON_VALID));
    if(a) {
        checkNear(a->lat, 52.25720, 0.01, "decoded latitude");
        checkNear(a->lon, 3.93891, 0.01, "decoded longitude");
        CHECK_EQ(a->altitude, 38000);
    }

    freeAircrafts(&modes);
}

static void testMapQuadtreeDegenerateLine() {
    Map map;
    map.root.lon_min = -180.0f;
    map.root.lon_max = -52.0f;
    map.root.lat_min = 17.0f;
    map.root.lat_max = 72.0f;

    Point point;
    point.lon = -73.845139f;
    point.lat = 40.723972f;

    Line line(point, point);
    CHECK_TRUE(map.QTInsert(&map.root, &line, 0));
    CHECK_TRUE(!map.root.lines.empty() ||
               map.root.nw != NULL ||
               map.root.ne != NULL ||
               map.root.sw != NULL ||
               map.root.se != NULL);
}

static void testOrganicMapsFeedGeoJson() {
    AppData appData;
    Aircraft *aircraft = new Aircraft(0xABC123);
    aircraft->lon = -73.845139f;
    aircraft->lat = 40.723972f;
    std::memcpy(aircraft->flight, "TEST\"1", 6);
    aircraft->altitude = 12000;
    aircraft->speed = 250;
    aircraft->track = 85;
    aircraft->vert_rate = -64;
    aircraft->seen = 12345;
    appData.aircraftList.head = aircraft;

    OrganicMapsFeed feed;
    std::string json = feed.buildGeoJson(&appData);

    CHECK_TRUE(json.find("\"type\":\"FeatureCollection\"") != std::string::npos);
    CHECK_TRUE(json.find("\"icao\":\"ABC123\"") != std::string::npos);
    CHECK_TRUE(json.find("\"flight\":\"TEST\\\"1\"") != std::string::npos);
    CHECK_TRUE(json.find("\"coordinates\":[-73.84514,40.72397]") != std::string::npos);
    CHECK_TRUE(json.find("\"vertical_rate\":-64") != std::string::npos);
}

int main() {
    testAircraftHistory();
    testAircraftListUpdateAndRemoval();
    testModeSCallsignFixture();
    testModeSPositionFixture();
    testMapQuadtreeDegenerateLine();
    testOrganicMapsFeedGeoJson();

    if(failures) {
        std::fprintf(stderr, "%d core test failure(s)\n", failures);
        return 1;
    }

    std::printf("core tests passed\n");
    return 0;
}
