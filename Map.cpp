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

#include "Map.h"
#include <stdio.h>
#include <cstdlib>
#include <sstream>
#include <fstream>
#include <string>
#include <iostream>
#include <cmath>

static const int MAX_QTREE_DEPTH = 28;
static const float MIN_QTREE_SPAN = 0.00001f;

static std::string joinPath(const std::string &dir, const char *name) {
  if(dir.empty() || dir == ".") {
    return std::string(name);
  }

  if(dir[dir.size() - 1] == '/') {
    return dir + name;
  }

  return dir + "/" + name;
}

bool Map::QTInsert(QuadTree *tree, Line *line, int depth) {
  if(tree == NULL) {
    return false;
  }
  

  bool startInside = line->start.lat >= tree->lat_min &&
   line->start.lat <= tree->lat_max &&
   line->start.lon >= tree->lon_min &&
   line->start.lon <= tree->lon_max;

  bool endInside = line->end.lat >= tree->lat_min &&
   line->end.lat <= tree->lat_max &&
   line->end.lon >= tree->lon_min &&
   line->end.lon <= tree->lon_max;

  // if (!startInside || !endInside) {
  //   return false; 
  // }
  if (!startInside && !endInside) {
    return false; 
  }
  
  if(depth >= MAX_QTREE_DEPTH ||
     fabs(tree->lat_max - tree->lat_min) <= MIN_QTREE_SPAN ||
     fabs(tree->lon_max - tree->lon_min) <= MIN_QTREE_SPAN) {
    tree->lines.push_back(&(*line));
    return true;
  }

  if (startInside != endInside) {
    tree->lines.push_back(&(*line));
    return true; 
  }     

  if (tree->nw == NULL) {
  	tree->nw = new QuadTree;

  	tree->nw->lat_min = tree->lat_min;	
  	tree->nw->lat_max = tree->lat_min + 0.5 * (tree->lat_max - tree->lat_min);
  	tree->nw->lon_min = tree->lon_min;
  	tree->nw->lon_max = tree->lon_min + 0.5 * (tree->lon_max - tree->lon_min);
  }

  if (QTInsert(tree->nw, line, depth + 1)){
  	return true;
  }

  if (tree->sw == NULL) {
  	tree->sw = new QuadTree;

  	tree->sw->lat_min = tree->lat_min;	
  	tree->sw->lat_max = tree->lat_min + 0.5 * (tree->lat_max - tree->lat_min);
  	tree->sw->lon_min = tree->lon_min + 0.5 * (tree->lon_max - tree->lon_min);
  	tree->sw->lon_max = tree->lon_max;
  }

	if (QTInsert(tree->sw, line, depth + 1)){
	 return true;
  }

  if (tree->ne == NULL) {
  	tree->ne = new QuadTree;

  	tree->ne->lat_min = tree->lat_min + 0.5 * (tree->lat_max - tree->lat_min);	
  	tree->ne->lat_max = tree->lat_max;
  	tree->ne->lon_min = tree->lon_min;
  	tree->ne->lon_max = tree->lon_min + 0.5 * (tree->lon_max - tree->lon_min);
  } 

  if (QTInsert(tree->ne, line, depth + 1)){
  	return true;	
  } 	

  if (tree->se == NULL) {  
  	tree->se = new QuadTree;

  	tree->se->lat_min = tree->lat_min + 0.5 * (tree->lat_max - tree->lat_min);
  	tree->se->lat_max = tree->lat_max;
  	tree->se->lon_min = tree->lon_min + 0.5 * (tree->lon_max - tree->lon_min);
  	tree->se->lon_max = tree->lon_max;
	}  

  if (QTInsert(tree->se, line, depth + 1)){
  	return true;	
	} 
	
  tree->lines.push_back(&(*line));

  return true;
}


std::vector<Line*> Map::getLinesRecursive(QuadTree *tree, float screen_lat_min, float screen_lat_max, float screen_lon_min, float screen_lon_max) {
    std::vector<Line*> retLines;

    if(tree == NULL) {
        return retLines;
    }

    if (tree->lat_min > screen_lat_max || screen_lat_min > tree->lat_max) {
        return retLines; 
    }

    if (tree->lon_min > screen_lon_max || screen_lon_min > tree->lon_max) {
        return retLines; 
    }

    std::vector<Line*> ret;
    ret = getLinesRecursive(tree->nw, screen_lat_min, screen_lat_max, screen_lon_min, screen_lon_max);
    retLines.insert(retLines.end(), ret.begin(), ret.end());

    ret = getLinesRecursive(tree->sw, screen_lat_min, screen_lat_max, screen_lon_min, screen_lon_max);
    retLines.insert(retLines.end(), ret.begin(), ret.end());

    ret = getLinesRecursive(tree->ne, screen_lat_min, screen_lat_max, screen_lon_min, screen_lon_max);
    retLines.insert(retLines.end(), ret.begin(), ret.end());

    ret = getLinesRecursive(tree->se, screen_lat_min, screen_lat_max, screen_lon_min, screen_lon_max);
    retLines.insert(retLines.end(), ret.begin(), ret.end());

    retLines.insert(retLines.end(), tree->lines.begin(), tree->lines.end());   

    // Debug quadtree
    // Point TL, TR, BL, BR;

    // TL.lat = tree->lat_min;
    // TL.lon = tree->lon_min;

    // TR.lat = tree->lat_max;
    // TR.lon = tree->lon_min;

    // BL.lat = tree->lat_min;
    // BL.lon = tree->lon_max;

    // BR.lat = tree->lat_max;
    // BR.lon = tree->lon_max;

    // retLines.push_back(new Line(TL,TR));
    // retLines.push_back(new Line(TR,BR));
    // retLines.push_back(new Line(BL,BR));
    // retLines.push_back(new Line(TL,BL));

    return retLines;
}

std::vector<Line*> Map::getLines(float screen_lat_min, float screen_lat_max, float screen_lon_min, float screen_lon_max) {
  return getLinesRecursive(&root, screen_lat_min, screen_lat_max, screen_lon_min, screen_lon_max);
};

static bool readPointFile(const std::string &path, float **points, int *count, const char *label) {
  FILE *fileptr;

  *count = 0;
  *points = NULL;

  if(!(fileptr = fopen(path.c_str(), "rb"))) {
    return false;
  }

  fseek(fileptr, 0, SEEK_END);
  *count = ftell(fileptr) / sizeof(float);
  rewind(fileptr);

  if(*count == 0) {
    fclose(fileptr);
    printf("Read 0 %s points.\n", label);
    return true;
  }

  *points = (float *)malloc(*count * sizeof(float));
  if(!fread(*points, sizeof(float), *count, fileptr)){
    printf("Map read error\n");
    exit(0);
  }

  fclose(fileptr);
  printf("Read %d %s points.\n", *count / 2, label);
  return true;
}

static void buildLayerTree(Map *map, QuadTree *root, float *points, int count, int *processed, int total) {
  if(count <= 0 || points == NULL) {
    return;
  }

  for(int i = 0; i < count; i += 2) {
    if(points[i] == 0) {
      continue;
    }

    if(points[i] < root->lon_min) {
      root->lon_min = points[i];
    } else if(points[i] > root->lon_max) {
      root->lon_max = points[i];
    }

    if(points[i + 1] < root->lat_min) {
      root->lat_min = points[i + 1];
    } else if(points[i + 1] > root->lat_max) {
      root->lat_max = points[i + 1];
    }
  }

  Point currentPoint;
  Point nextPoint;

  for(int i = 0; i < count - 2; i += 2) {
    if(points[i] == 0) {
      continue;
    }
    if(points[i + 1] == 0) {
      continue;
    }
    if(points[i + 2] == 0) {
      continue;
    }
    if(points[i + 3] == 0) {
      continue;
    }

    currentPoint.lon = points[i];
    currentPoint.lat = points[i + 1];
    nextPoint.lon = points[i + 2];
    nextPoint.lat = points[i + 3];

    map->QTInsert(root, new Line(currentPoint, nextPoint), 0);
    (*processed)++;

    if(total > 0) {
      map->loaded = floor(100.0f * (float)(*processed) / (float)total);
    }
  }
}


void Map::load() { 
  std::string mapDataPath = joinPath(dataDir, "mapdata.bin");
  std::string adminDataPath = joinPath(dataDir, "admin.bin");
  std::string coastDataPath = joinPath(dataDir, "coast.bin");
  std::string waterDataPath = joinPath(dataDir, "water.bin");
  std::string roadsDataPath = joinPath(dataDir, "roads.bin");
  std::string airportDataPath = joinPath(dataDir, "airportdata.bin");
  std::string mapNamesPath = joinPath(dataDir, "mapnames");
  std::string airportNamesPath = joinPath(dataDir, "airportnames");

  bool loadedLayers = false;
  loadedLayers = readPointFile(adminDataPath, &adminPoints, &adminPoints_count, "admin layer") || loadedLayers;
  loadedLayers = readPointFile(coastDataPath, &coastPoints, &coastPoints_count, "coast layer") || loadedLayers;
  loadedLayers = readPointFile(waterDataPath, &waterPoints, &waterPoints_count, "water layer") || loadedLayers;
  loadedLayers = readPointFile(roadsDataPath, &roadsPoints, &roadsPoints_count, "roads layer") || loadedLayers;

  if(!loadedLayers) {
    readPointFile(mapDataPath, &mapPoints, &mapPoints_count, "map");
  }

  readPointFile(airportDataPath, &airportPoints, &airportPoints_count, "airport");

  int total = mapPoints_count / 2 +
    adminPoints_count / 2 +
    coastPoints_count / 2 +
    waterPoints_count / 2 +
    roadsPoints_count / 2 +
    airportPoints_count / 2;
  int processed = 0;

  if(mapPoints_count > 0) {
    buildLayerTree(this, &root, mapPoints, mapPoints_count, &processed, total);
  } else {
    if(!loadedLayers) {
      printf("No map file found\n");
    }
  }

  buildLayerTree(this, &admin_root, adminPoints, adminPoints_count, &processed, total);
  buildLayerTree(this, &coast_root, coastPoints, coastPoints_count, &processed, total);
  buildLayerTree(this, &water_root, waterPoints, waterPoints_count, &processed, total);
  buildLayerTree(this, &roads_root, roadsPoints, roadsPoints_count, &processed, total);

  if(airportPoints_count > 0) {
    buildLayerTree(this, &airport_root, airportPoints, airportPoints_count, &processed, total);
  } else {
    printf("No airport file found\n");
  }


  std::string line;
  std::ifstream infile(mapNamesPath.c_str());


  while (std::getline(infile, line))  
  {
    float lon, lat;

    std::istringstream iss(line);

    iss >> lon;
    iss >> lat;

    std::string assemble;

    iss >> assemble;

    for(std::string s; iss >> s; ) {
      assemble = assemble + " " + s;
    }

    // std::cout << "[" << x << "," << y << "] " << assemble << "\n";
    MapLabel *label = new MapLabel(lon,lat,assemble); 
    mapnames.push_back(label);
  }

  std::cout << "Read " << mapnames.size() << " place names\n";

  infile.close();

  infile.open(airportNamesPath.c_str());


  while (std::getline(infile, line))  
  {
    float lon, lat;

    std::istringstream iss(line);

    iss >> lon;
    iss >> lat;

    std::string assemble;

    iss >> assemble;

    for(std::string s; iss >> s; ) {
      assemble = assemble + " " + s;
    }

    // std::cout << "[" << x << "," << y << "] " << assemble << "\n";
    MapLabel *label = new MapLabel(lon,lat,assemble); 
    airportnames.push_back(label);
  }

  std::cout << "Read " << airportnames.size() << " airport names\n";

  infile.close();

  printf("done\n");

  loaded = 100;
}

void Map::setDataDir(std::string path) {
    dataDir = path;
}

Map::Map() {
    loaded = 0;
    dataDir = ".";

    mapPoints_count = 0;
    mapPoints = NULL;

    adminPoints_count = 0;
    adminPoints = NULL;

    coastPoints_count = 0;
    coastPoints = NULL;

    waterPoints_count = 0;
    waterPoints = NULL;

    roadsPoints_count = 0;
    roadsPoints = NULL;

    airportPoints_count = 0;
    airportPoints = NULL;
} 
