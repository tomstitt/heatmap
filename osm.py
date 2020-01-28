#!/usr/bin/env python

import requests
import xml.etree.ElementTree as et
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import pickle
import base64
import struct

osm_url = "https://www.openstreetmap.org/api/0.6/map?bbox={min_lon}%2C{min_lat}%2C{max_lon}%2C{max_lat}"
overpass_url = "https://overpass-api.de/api/map?bbox={min_lon},{min_lat},{max_lon},{max_lat}"


def osm_id(min_lon, min_lat, max_lon, max_lat):
    name = ""
    for f in [min_lon, min_lat, max_lon, max_lat]:
        name += base64.b16encode(struct.pack(">f", f)).decode().lower()
    return name


def download_osm(file_name, min_lon, min_lat, max_lon, max_lat):
    url = overpass_url
    print(f"downloading osm data for {min_lon},{min_lat} x {max_lon},{max_lat}, this may take a bit")
    r = requests.get(url.format(min_lon=min_lon, min_lat=min_lat, max_lon=max_lon, max_lat=max_lat))
    with open(file_name, "wb") as f:
        f.write(r.content)


def parse_osm(osm_file):
    print("loading osm file, this could take a little")
    root = et.parse(osm_file).getroot()

    print("parsing nodes")
    # <node id="30373224" visible="true" version="10" changeset="17008899" timestamp="2013-07-19T08:29:25Z"
    #       user="KindredCoda" uid="14293" lat="37.8056490" lon="-122.2779586"/>
    nodes = {}
    for node in root.findall("node"):
        nodes[int(node.get("id"))] = (float(node.get("lon")), float(node.get("lat")))
    print(f"found {len(nodes)} nodes")

    print("parsing ways for highways")
    # <way id="684629570" visible="true" version="1" changeset="69353172" timestamp="2019-04-18T17:18:20Z" user="clay_c" uid="119881">
    #  <nd ref="6414733808"/>
    #  <nd ref="6239113537"/>
    #  <nd ref="4595671557"/>
    #  <tag k="bicycle" v="yes"/>
    #  <tag k="foot" v="yes"/>
    #  <tag k="highway" v="tertiary"/>
    #  <tag k="name" v="Martin Luther King Junior Way"/>
    #  <tag k="name:etymology:wikidata" v="Q8027"/>
    #  <tag k="old_name" v="Grove Street"/>
    #  <tag k="sidewalk" v="both"/>
    # </way>
    segments = []
    for way in root.findall("way"):
        keep = False
        attrs = {}
        coords = []
        for e in way:
            if e.tag == "nd":
                ref = e.get("ref")
                if ref is not None:
                    coords.append(nodes[int(ref)])
            elif e.tag == "tag":
                key = e.get("k")
                val = e.get("v")
                if key == "highway":
                    keep = True
                attrs[key] = val
        if keep:
            attrs["coords"] = coords
            segments.append(coords)
    print(f"found {len(segments)} highways")
    return segments


def plot_segments(file_name, segments, background_color="antiquewhite", line_color="salmon", line_width=.1,
        line_alpha=1, dpi=800):
    fig = plt.figure(facecolor=background_color)
    ax = fig.add_subplot(111)

    print("plotting")
    lc = LineCollection(segments, colors=line_color, alpha=line_alpha)
    lc.set_linewidth(line_width)
    ax.add_collection(lc)

    ax.autoscale()
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    aspect_ratio = (ylim[1] - ylim[0]) / (xlim[1] - xlim[0])
    print(f"> bounding box=[{xlim[0]:.4f}, {ylim[0]:.4f}] x [{xlim[1]:.4f}, {ylim[1]:.4f}], "
        f"aspect ratio={aspect_ratio:.4f}")

    ax.set_aspect(aspect_ratio)
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)
    ax.set_facecolor(background_color)
    for spine in ax.spines.values():
        spine.set_edgecolor(background_color)
    #ax.axis("off")
    #plt.show()
    fig.savefig(file_name, facecolor=fig.get_facecolor(), edgecolor="none", dpi=dpi)
    plt.close(fig)
    print()


if __name__ == "__main__":
    import os

    file_name = "map.osm"
    cache_name = "segments.pkl"
    segments = None
    if os.path.exists(cache_name):
        print(f"found cache {cache_name}")
        with open(cache_name, "rb") as f:
            ways = pickle.load(f)
    elif not os.path.exists(file_name):
        download_osm(file_name, -122.3362, 37.7100, -122.1017, 37.9683)
    else:
        print("found osm file")

    if ways is None:
        segments = parse_osm(file_name)
        print(f"saving cache to {cache_name}")
        with open(cache_name, "wb") as f:
            pickle.dump(segments, f)

    plot_segments("map.png", segments)
