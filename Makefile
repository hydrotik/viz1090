#
# When building a package or installing otherwise in the system, make
# sure that the variable PREFIX is defined, e.g. make PREFIX=/usr/local
#

CXXFLAGS ?= -O2 -std=c++11 -g
CFLAGS ?= -O2 -g
CXX ?= g++
CC ?= cc
PKG_CONFIG ?= pkg-config

SDL_CFLAGS := $(shell $(PKG_CONFIG) --cflags sdl2 SDL2_ttf SDL2_gfx 2>/dev/null)
SDL_LIBS := $(shell $(PKG_CONFIG) --libs sdl2 SDL2_ttf SDL2_gfx 2>/dev/null)
ifeq ($(strip $(SDL_LIBS)),)
SDL_LIBS = -lSDL2 -lSDL2_ttf -lSDL2_gfx
endif

CPPFLAGS += -I. $(SDL_CFLAGS)
LIBS= -lm $(SDL_LIBS) -lpthread -g

all: viz1090

APP_OBJS = viz1090.o AppData.o AircraftList.o Aircraft.o Label.o AircraftLabel.o anet.o interactive.o mode_ac.o mode_s.o net_io.o Input.o View.o Map.o parula.o monokai.o
CORE_TEST_OBJS = tests/core_tests.o AircraftList.o Aircraft.o Map.o interactive.o mode_ac.o mode_s.o

%.o: %.cpp
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $(EXTRACFLAGS) -c $< -o $@

%.o: %.c
	$(CC) $(CPPFLAGS) $(CFLAGS) $(EXTRACFLAGS) -c $< -o $@

viz1090: $(APP_OBJS)
	$(CXX) -o viz1090 $(APP_OBJS) $(LIBS) $(LDFLAGS)

tests/core_tests: $(CORE_TEST_OBJS)
	$(CXX) -o tests/core_tests $(CORE_TEST_OBJS) -lm -lpthread $(LDFLAGS)

test-core: tests/core_tests
	./tests/core_tests

test-mapconverter:
	python3 -m unittest tests.test_mapconverter

test-gps:
	python3 -m unittest tests.test_gps_fix

test-weather:
	python3 -m unittest tests.test_weather_fixture

test-fixtures:
	python3 tools/replay_benchmark.py --check-fixture

smoke-ui: viz1090
	python3 tools/replay_benchmark.py --duration 5 --port 33005 --dummy-video

benchmark-smoke: viz1090
	python3 tools/replay_benchmark.py --duration 15 --rate 60 --port 33006 --dummy-video

test: test-core test-mapconverter test-gps test-weather test-fixtures

sanitize:
	$(MAKE) clean
	$(MAKE) test CFLAGS="-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer" CXXFLAGS="-O1 -std=c++11 -g -fsanitize=address,undefined -fno-omit-frame-pointer" LDFLAGS="-fsanitize=address,undefined"

ci: test sanitize viz1090 smoke-ui

clean:
	rm -f \
		*.o \
		tests/*.o \
		tests/core_tests \
		viz1090

clean-generated:
	rm -f \
		airportdata.bin \
		airportnames \
		mapdata.bin \
		mapnames
	find mapdata/generated -type f \( -name 'airportdata.bin' -o -name 'airportnames' -o -name 'mapdata.bin' -o -name 'mapnames' \) -delete 2>/dev/null || true
