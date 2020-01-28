#!/usr/bin/env python

import glob
import os
import pickle
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

import requests
import gpxpy
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np
from sklearn.cluster import DBSCAN

import osm

# TODO: move to argparse
use_osm = True
osm_color = "salmon"
osm_line_width = .1
osm_alpha = .5


def plot(data, background_color, line_width, line_color, line_alpha, dpi, label=0):
    if line_color.startswith("cmap:"):
        use_cmap = True
        max_elev = max([max(d["elevs"]) for d in data])
        min_elev = min([min(d["elevs"]) for d in data])
        norm = plt.Normalize(min_elev, max_elev)
        print(f"> min elevation: {min_elev}, max elevation: {max_elev}")
        line_color = line_color[5:]
    elif line_color.startswith("lcmap:"):
        use_cmap = True
        norm = None
        line_color = line_color[6:]
    else:
        use_cmap = False

    fig = plt.figure(facecolor=background_color)
    ax = fig.add_subplot(111)

    if use_cmap:
        for i, ds in enumerate(data, 1):
            print(f"> plotting ({i}/{len(data)})", end="\r")
            lons = ds["lons"]
            lats = ds["lats"]
            if use_cmap:
                elevs = np.array(ds["elevs"])
                points = np.array([lons, lats]).T.reshape(-1, 1, 2)
                segments = np.concatenate([points[:-1], points[1:]], axis=1)
                lc = LineCollection(segments, cmap=plt.get_cmap(line_color),
                        alpha=line_alpha, norm=norm)
                lc.set_array(elevs)
                lc.set_linewidth(line_width)
                ax.add_collection(lc)
    else:
        segments = [[(lon, lat) for lon, lat in zip(d["lons"], d["lats"])] for d in data]
        lc = LineCollection(segments, colors=line_color, alpha=line_alpha)
        lc.set_linewidth(line_width)
        ax.add_collection(lc)

    ax.autoscale()
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    aspect_ratio = (ylim[1] - ylim[0]) / (xlim[1] - xlim[0])
    print(f"> bounding box=[{xlim[0]:.4f}, {ylim[0]:.4f}] x [{xlim[1]:.4f}, {ylim[1]:.4f}], "
        f"aspect ratio={aspect_ratio:.4f}")

    # add paths from open street map
    if use_osm:
        print("adding osm data")
        osm_id = osm.osm_id(xlim[0], ylim[0], xlim[1], ylim[1])
        osm_file = f"map_{osm_id}.osm"
        segments_file = f"segments_{osm_id}.pkl"
        print(f"looking for {segments_file}")
        if not os.path.exists(segments_file):
            print(f"looking for {osm_file}")
            if not os.path.exists(osm_file):
                osm.download_osm(osm_file, xlim[0], ylim[0], xlim[1], ylim[1])
            else:
                print("> found")
            segments = osm.parse_osm(osm_file)
            with open(segments_file, "wb") as f:
                pickle.dump(segments, f)
        else:
            print("> found")
            with open(segments_file, "rb") as f:
                segments = pickle.load(f)

        lc = LineCollection(segments, colors=osm_color, alpha=osm_alpha)
        lc.set_linewidth(osm_line_width)
        ax.add_collection(lc)

    ax.set_aspect(aspect_ratio)
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)
    ax.set_facecolor(background_color)
    for spine in ax.spines.values():
        spine.set_edgecolor(background_color)
    #ax.axis("off")
    #plt.show()
    fig.savefig(f"figure_label_{label}.png", facecolor=fig.get_facecolor(),
            edgecolor="none", dpi=dpi)
    plt.close(fig)
    print()


def load_gpx(files, data=None):
    if data is None:
        data = dict(tracks=[])
    for i, path in enumerate(files, 1):
        print(f"loading {100*i/len(files):.2f}%: ({i}/{len(files)})", end="\r")

        with open(path, "r") as f:
            gpx = gpxpy.parse(f)

        track = gpx.tracks[0]
        segment = track.segments[0]

        data["tracks"].append({
            "lats": np.array([p.latitude for p in segment.points]),
            "lons": np.array([p.longitude for p in segment.points]),
            "elevs": np.array([p.elevation for p in segment.points]),
            "type": int(track.type),
            "name": track.name,
            "date": gpx.time,
            "filename": os.path.basename(path)
        })
    print(f"loaded {len(data)} file(s)")
    file_set = set(os.path.basename(f) for f in files)
    if "files" in data:
        data["files"] = data["files"] | file_set
    else:
        data["files"] = file_set
    return data


def add_shared_args(parser):
    parser.add_argument("--background-color", type=str, default="antiquewhite",
        help="background color of image")
    parser.add_argument("--line-color", type=str, default="darkturquoise",
        help="line color of tracks")
    parser.add_argument("--line-width", type=float, default=.15,
        help="line width of tracks")
    parser.add_argument("--line-alpha", type=float, default=.8,
        help="line alpha (transparency) of tracks")
    parser.add_argument("--dpi", type=int, default=2000,
        help="image quality (dots per inch)")
    parser.add_argument("--radius", type=float, default=.05,
        help="radius in units of degrees for filtering")
    parser.add_argument("--reduction",
        choices=["start", "average", "start_stop_average"],
        default="average",
        help="method to get a single lat/lon from a track when filtering")
    parser.add_argument("--activity-type", type=int,
        help="if defined only include this activity type")
    parser.add_argument("--gpx-dir", default="strava",
        help="directory with gpx files")


parser = ArgumentParser()
subparsers = parser.add_subparsers(dest="type")

cluster_parser = subparsers.add_parser("cluster", formatter_class=ArgumentDefaultsHelpFormatter)
cluster_parser.add_argument("--min-cluster-size", type=int, default=10,
    help="minimum number of tracks to create a cluster")
add_shared_args(cluster_parser)

coords_parser = subparsers.add_parser("coords", formatter_class=ArgumentDefaultsHelpFormatter)
coords_parser.add_argument("--lat", type=float, help="center latitude", required=True)
coords_parser.add_argument("--lon", type=float, help="center longitude", required=True)
add_shared_args(coords_parser)

find_me_parser = subparsers.add_parser("here", formatter_class=ArgumentDefaultsHelpFormatter)
add_shared_args(find_me_parser)

all_tracks_parser = subparsers.add_parser("all", formatter_class=ArgumentDefaultsHelpFormatter)
add_shared_args(all_tracks_parser)

args = parser.parse_args()

plot_keys = ["background_color", "line_color", "line_width", "line_alpha", "dpi"]
plot_args = {k: getattr(args, k) for k in plot_keys}

cache_path = os.path.join(args.gpx_dir, "cache.pkl")
files = glob.glob(os.path.join(args.gpx_dir, "*.gpx"))

if os.path.exists(cache_path):
    print(f"found cache at {cache_path}")
    with open(cache_path, "rb") as f:
        data = pickle.load(f)
    new_files = data["files"] ^ set([os.path.basename(f) for f in files])
    if len(new_files) > 0:
        print(f"updating cache file {cache_path}")
        dirname = os.path.dirname(files[0])
        data = load_gpx([os.path.join(dirname, f) for f in new_files], data)
        with open(cache_path, "wb") as f:
            pickle.dump(data, f)
else:
    data = load_gpx(files)
    print(f"saving cache to {cache_path}")
    with open(cache_path, "wb") as f:
        pickle.dump(data, f)


if args.activity_type is not None:
    data = np.array([d for d in data["tracks"] if d["type"] == args.activity_type])
else:
    data = np.array(data["tracks"])

if args.reduction == "average":
    coords = np.array([[np.average(d["lats"]), np.average(d["lons"])] for d in data])
elif args.reduction == "start_stop_average":
    coords = np.array([[np.average(d["lats"][[0, -1]]), np.average(d["lons"][[0, -1]])] for d in data])
elif args.reduction == "start":
    coords = np.array([[np.average(d["lats"][0]), np.average(d["lons"][0])] for d in data])

if args.type == "cluster":
    cluster = DBSCAN(eps=args.radius, min_samples=10)
    cluster.fit(coords)
    n_clusters = np.max(cluster.labels_) + 1
    centroids = [np.mean(coords[cluster.labels_ == l], axis=0) for l in range(n_clusters)]

    print(f"found {n_clusters} clusters, {np.sum(cluster.labels_ == -1)} tracks unclassified")

    for label in range(n_clusters):
        label_data = data[cluster.labels_ == label]
        print(f"plotting cluster {label+1}/{n_clusters}: {len(label_data)} tracks")
        plot(label_data, **plot_args, label=label)

elif args.type == "coords" or args.type == "here":
    if args.type == "here":
        resp = requests.get("https://geo.risk3sixty.com/me")
        obj = resp.json()
        print(f"looks like you're near {obj['city']}")
        args.lat = obj["ll"][0]
        args.lon = obj["ll"][1]

    filtered = [d for d,c in zip(data, coords) if np.sqrt(
        (c[0] - args.lat)**2 + (c[1] - args.lon)**2) <= args.radius]
    print(f"plotting {len(filtered)} tracks around {args.lat:.4f}, {args.lon:.4f}")
    plot(filtered, **plot_args)

else:
    print(f"plotting all tracks")
    plot(data, **plot_args)
