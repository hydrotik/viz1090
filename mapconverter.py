import argparse
import csv
from pathlib import Path


def convertLinestring(linestring):
	outlist = []

	pointx = linestring.coords.xy[0]
	pointy = linestring.coords.xy[1]

	for j in range(len(pointx)):
		outlist.extend([float(pointx[j]), float(pointy[j])])

	outlist.extend([0, 0])
	return outlist


def geometryToLines(geometry):
	outlist = []

	if geometry.is_empty:
		return outlist

	if geometry.geom_type == "LineString":
		outlist.extend(convertLinestring(geometry))
	elif geometry.geom_type == "MultiLineString":
		for line in geometry.geoms:
			outlist.extend(convertLinestring(line))
	elif geometry.geom_type == "MultiPolygon" or geometry.geom_type == "Polygon":
		boundary = geometry.boundary
		if boundary.geom_type == "MultiLineString":
			for line in boundary.geoms:
				outlist.extend(convertLinestring(line))
		else:
			outlist.extend(convertLinestring(boundary))
	elif geometry.geom_type == "GeometryCollection":
		for item in geometry.geoms:
			outlist.extend(geometryToLines(item))
	else:
		print("Unsupported type: " + geometry.geom_type)

	return outlist


def extractLines(shapefile, tolerance, bbox=None):
	from shapely.geometry import box, shape
	from tqdm import tqdm

	print("Extracting map lines")
	outlist = []
	clip_box = box(*bbox) if bbox else None

	for i in tqdm(range(len(shapefile))):
		geometry = shape(shapefile[i]['geometry'])
		if clip_box:
			if not geometry.intersects(clip_box):
				continue
			geometry = geometry.intersection(clip_box)

		if tolerance > 0:
			geometry = geometry.simplify(tolerance, preserve_topology=False)

		outlist.extend(geometryToLines(geometry))

	return outlist


def writeFloatBin(path, values):
	import numpy as np

	with open(path, "wb") as bin_file:
		np.asarray(values).astype(np.single).tofile(bin_file)


def parseMapLayer(value):
	if "=" not in value:
		raise argparse.ArgumentTypeError("map layer must be name=shapefile")

	name, path = value.split("=", 1)
	name = name.strip()
	path = path.strip()

	if not name or not path:
		raise argparse.ArgumentTypeError("map layer must include both name and shapefile")

	for char in name:
		if not (char.isalnum() or char in ("_", "-")):
			raise argparse.ArgumentTypeError("map layer name may only contain letters, numbers, underscore, and dash")

	return name, path


def inBbox(lon, lat, bbox):
	if bbox is None:
		return True

	return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]


def writePlaceNames(path, shapefile, minpop, bbox=None):
	from tqdm import tqdm

	count = 0
	with open(path, "w") as bin_file:
		for i in tqdm(range(len(shapefile))):
			xcoord = shapefile[i]['geometry']['coordinates'][0]
			ycoord = shapefile[i]['geometry']['coordinates'][1]
			pop = shapefile[i]['properties']['POP_MIN']
			name = shapefile[i]['properties']['NAME']

			if pop > minpop and inBbox(xcoord, ycoord, bbox):
				bin_file.write("{0} {1} {2}\n".format(xcoord, ycoord, name))
				count = count + 1

	return count


def writeAirportNames(path, shapefile, bbox=None):
	from tqdm import tqdm

	count = 0
	with open(path, "w") as bin_file:
		for i in tqdm(range(len(shapefile))):
			xcoord = shapefile[i]['geometry']['coordinates'][0]
			ycoord = shapefile[i]['geometry']['coordinates'][1]
			name = shapefile[i]['properties']['iata_code']

			if inBbox(xcoord, ycoord, bbox):
				bin_file.write("{0} {1} {2}\n".format(xcoord, ycoord, name))
				count = count + 1

	return count


def writeRunwayCsv(path, csv_path, bbox=None):
	outlist = []

	with open(csv_path, newline="", encoding="utf-8") as csv_file:
		reader = csv.DictReader(csv_file)
		for row in reader:
			try:
				le_lon = float(row["le_longitude_deg"])
				le_lat = float(row["le_latitude_deg"])
				he_lon = float(row["he_longitude_deg"])
				he_lat = float(row["he_latitude_deg"])
			except (KeyError, TypeError, ValueError):
				continue

			if bbox and not (inBbox(le_lon, le_lat, bbox) or inBbox(he_lon, he_lat, bbox)):
				continue

			outlist.extend([le_lon, le_lat, he_lon, he_lat, 0, 0])

	writeFloatBin(path, outlist)
	return int(len(outlist) / 6)


def parseBbox(value):
	parts = [float(part.strip()) for part in value.split(",")]
	if len(parts) != 4:
		raise argparse.ArgumentTypeError("bbox must be lon_min,lat_min,lon_max,lat_max")

	if parts[0] >= parts[2] or parts[1] >= parts[3]:
		raise argparse.ArgumentTypeError("bbox minimums must be smaller than maximums")

	return parts


def outputPath(output_dir, filename):
	return Path(output_dir) / filename


def buildParser():
	parser = argparse.ArgumentParser(description='viz1090 Natural Earth Data Map Converter')
	parser.add_argument("--mapfile", action="append", type=str, help="shapefile for main map; may be repeated")
	parser.add_argument("--maplayer", action="append", type=parseMapLayer, help="named map layer as name=shapefile; may be repeated")
	parser.add_argument("--mapnames", type=str, help="shapefile for map place names")
	parser.add_argument("--airportfile", type=str, help="shapefile for airport runway outlines")
	parser.add_argument("--airportcsv", type=str, help="OurAirports runways.csv fallback for runway centerlines")
	parser.add_argument("--airportnames", type=str, help="shapefile for airport IATA names")
	parser.add_argument("--minpop", default=100000, type=int, help="minimum population for place names")
	parser.add_argument("--tolerance", default=0.001, type=float, help="map simplification tolerance")
	parser.add_argument("--bbox", type=parseBbox, help="clip to lon_min,lat_min,lon_max,lat_max")
	parser.add_argument("--output-dir", default=".", type=str, help="directory for generated map files")
	return parser


def main(argv=None):
	import fiona

	args = buildParser().parse_args(argv)
	output_dir = Path(args.output_dir)
	output_dir.mkdir(parents=True, exist_ok=True)

	outlist = []
	if args.maplayer is not None:
		layer_outputs = {}
		for layer_name, layer_file in args.maplayer:
			shapefile = fiona.open(layer_file)
			layer_lines = extractLines(shapefile, args.tolerance, args.bbox)
			layer_outputs.setdefault(layer_name, []).extend(layer_lines)
			outlist.extend(layer_lines)
			print("Wrote %d %s layer points" % (len(layer_lines) / 2, layer_name))
		for layer_name, layer_lines in layer_outputs.items():
			writeFloatBin(outputPath(output_dir, layer_name + ".bin"), layer_lines)
			print("Wrote %d combined %s layer points" % (len(layer_lines) / 2, layer_name))

	if args.mapfile is not None:
		for mapfile in args.mapfile:
			shapefile = fiona.open(mapfile)
			outlist.extend(extractLines(shapefile, args.tolerance, args.bbox))

	if outlist:
		writeFloatBin(outputPath(output_dir, "mapdata.bin"), outlist)
		print("Wrote %d points" % (len(outlist) / 2))

	if args.mapnames is not None:
		shapefile = fiona.open(args.mapnames)
		count = writePlaceNames(outputPath(output_dir, "mapnames"), shapefile, args.minpop, args.bbox)
		print("Wrote %d place names" % count)

	airport_lines = []
	if args.airportfile is not None:
		shapefile = fiona.open(args.airportfile)
		airport_lines.extend(extractLines(shapefile, 0, args.bbox))

	if airport_lines:
		writeFloatBin(outputPath(output_dir, "airportdata.bin"), airport_lines)
		print("Wrote %d airport outline points" % (len(airport_lines) / 2))

	if args.airportcsv is not None and not airport_lines:
		count = writeRunwayCsv(outputPath(output_dir, "airportdata.bin"), args.airportcsv, args.bbox)
		print("Wrote %d runway centerlines" % count)

	if args.airportnames is not None:
		shapefile = fiona.open(args.airportnames)
		count = writeAirportNames(outputPath(output_dir, "airportnames"), shapefile, args.bbox)
		print("Wrote %d airport names" % count)


if __name__ == "__main__":
	main()
