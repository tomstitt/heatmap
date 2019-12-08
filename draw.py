#!/usr/bin/env python

import glob
import os
import pickle
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

import gpxpy
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np
from sklearn.cluster import DBSCAN


def plot(data, background_color, line_width, line_color, line_alpha, dpi, label=0):
    if line_color.startswith("cmap:"):
        use_cmap = True
        line_color = line_color[5:]
    else:
        use_cmap = False

    max_elev = max([max(d["elevs"]) for d in data])
    min_elev = min([min(d["elevs"]) for d in data])
    fig = plt.figure(facecolor=background_color)
    ax = fig.add_subplot(111)

    print(f"> min elevation: {min_elev}, max elevation: {max_elev}")
    for i, ds in enumerate(data, 1):
        print(f"> plotting ({i}/{len(data)})", end="\r")
        lons = ds["lons"]
        lats = ds["lats"]
        if use_cmap:
            elevs = np.array(ds["elevs"])
            points = np.array([lons, lats]).T.reshape(-1, 1, 2)
            segments = np.concatenate([points[:-1], points[1:]], axis=1)
            lc = LineCollection(segments, cmap=plt.get_cmap(line_color), alpha=line_alpha)
            lc.set_array(elevs)
            lc.set_linewidth(line_width)
            ax.add_collection(lc)
        else:
            ax.plot(lons, lats, color=line_color, lw=line_width, alpha=line_alpha)

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
    #ax.axis("off")
    #plt.show()
    fig.savefig(f"figure_label_{label}.png", facecolor=fig.get_facecolor(), edgecolor="none", dpi=dpi)
    plt.close(fig)
    print()


def load_gpx(gpx_dir):
    files = glob.glob(os.path.join(gpx_dir, "*.gpx"))
    data = []
    for i, path in enumerate(files, 1):
        print(f"loading {100*i/len(files):.2f}%: ({i}/{len(files)})", end="\r")

        with open(path, "r") as f:
            gpx = gpxpy.parse(f)

        track = gpx.tracks[0]
        segment = track.segments[0]

        data.append({
            "lats": np.array([p.latitude for p in segment.points]),
            "lons": np.array([p.longitude for p in segment.points]),
            "elevs": np.array([p.elevation for p in segment.points]),
            "type": int(track.type),
            "name": track.name,
            "date": gpx.time
        })
    print(f"loaded {len(data)} file(s)")
    return data


def add_shared_args(parser):
    parser.add_argument("--background-color", type=str, default="black",
        help="background color of image")
    parser.add_argument("--line-color", type=str, default="xkcd:sky blue",
        help="line color of tracks")
    parser.add_argument("--line-width", type=float, default=1,
        help="line width of tracks")
    parser.add_argument("--line-alpha", type=float, default=.2,
        help="line alpha (transparency) of tracks")
    parser.add_argument("--dpi", type=int, default=800,
        help="image quality (dots per inch)")
    parser.add_argument("--radius", type=float, default=.05,
        help="radius in units of degrees for filtering")
    parser.add_argument("--reduction", choices=["start", "average", "start_stop_average"], default="average",
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
coords_parser.add_argument("--lat", type=float, help="center latitude")
coords_parser.add_argument("--lon", type=float, help="center longitude")
add_shared_args(coords_parser)

args = parser.parse_args()

plot_keys = ["background_color", "line_color", "line_width", "line_alpha", "dpi"]
plot_args = {k: getattr(args, k) for k in plot_keys}

cache_path = os.path.join(args.gpx_dir, "cache.pkl")

if os.path.exists(cache_path):
    print(f"found cache at {cache_path}")
    with open(cache_path, "rb") as f:
        data = pickle.load(f)
else:
    data = load_gpx(args.gpx_dir)
    print(f"saving cache to {cache_path}")
    with open(cache_path, "wb") as f:
        pickle.dump(data, f)

if args.activity_type is not None:
    data = np.array([d for d in data if d["type"] == args.activity_type])
else:
    data = np.array(data)

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

elif args.type == "coords":
    if args.lon is not None and args.lat is not None:
        filtered = [d for d,c in zip(data, coords) if np.sqrt(
            (c[0] - args.lat)**2 + (c[1] - args.lon)**2) <= args.radius]
        print(f"plotting {len(filtered)} tracks around {args.lat:.4f}, {args.lon:.4f}")
        plot(filtered, **plot_args)
    else:
        print(f"plotting all tracks")
        plot(data, **plot_args)
