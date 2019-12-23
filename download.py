#!/usr/bin/env python

import argparse
import getpass
import os
import math
import sys

import lxml.html
import requests

login_url = "https://www.strava.com/login"
session_url = "https://www.strava.com/session"
activities_url = "https://www.strava.com/athlete/training_activities"
gpx_url = "https://www.strava.com/activities/{id}/export_gpx"
activity_txt = "activities.txt"


def get_activity_ids(sess, current_list=None):
    if current_list is not None:
        last_activity = current_list[0]
    else:
        last_activity = None
    num_activities = math.inf
    page = 1
    activities = []
    while len(activities) < num_activities:
        response = sess.get(activities_url,
            headers={"Content-Type": "application/javascript", "X-Requested-With": "XMLHttpRequest"},
            # even with 50 strava only seems to support 20 at a time
            params={"new_activity_only": False, "page": page, "per_page": 50}
        )
        obj = response.json()

        if num_activities == math.inf:
            num_activities = obj["total"]

        current = [str(m["id"]) for m in obj["models"]]
        if last_activity is not None:
            try:
                idx = current.index(last_activity)
                activities.extend(current[0:idx])
                print("found overlap with previous list")
                return activities + current_list
            except IndexError:
                pass

        activities.extend(current)
        page += 1
        print(f"{len(activities)}/{num_activities}", end="\r")
    return activities


parser = argparse.ArgumentParser()

parser.add_argument("--output-dir", default="strava")
parser.add_argument("--activity-list")
parser.add_argument("--quick", action="store_true", help="exit when the first existing gpx file is found")

args = parser.parse_args()

if args.activity_list is None:
    args.activity_list = os.path.join(args.output_dir, activity_txt)

if os.path.exists(args.activity_list):
    with open(args.activity_list, "r") as f:
        activity_ids = [l.strip() for l in f.readlines()]
else:
    activity_ids = None

if not os.path.exists(args.output_dir):
    os.mkdir(args.output_dir)

email = input("email> ")
password = getpass.getpass("password> ")

skipped = []
with requests.session() as sess:
    page = sess.get(login_url)
    html = lxml.html.fromstring(page.text)
    inputs = html.xpath(r"//form//input")
    payload = {x.attrib["name"]: x.attrib["value"] if "value" in x.attrib else "" for x in inputs}
    payload.update(email=email, password=password)

    response = sess.post(session_url, data=payload)
    response.raise_for_status()

    if not response.url.endswith("dashboard"):
        sys.exit("looks like you failed to authenticate=[")

    print("getting activity list")
    activity_ids = get_activity_ids(sess, current_list=activity_ids)
    print(f"writing activity list to {args.activity_list}")
    with open(args.activity_list, "w") as f:
        f.write("\n".join(activity_ids))

    for count, identifier in enumerate(activity_ids, 1):
        if count % 20 == 0:
            print(f"({count}/{len(activity_ids)})")

        output = os.path.join(args.output_dir, f"{identifier}.gpx")
        if not os.path.exists(output):
            print(f"downloading activity {identifier} to {output}")
            with sess.get(gpx_url.format(id=identifier)) as r:
                content = r.content
                if not r.content.startswith(b"<?xml"):
                    print("> data doesn't look like gpx, skipping")
                    skipped.append(identifier)
                    continue
                with open(output, "wb") as f:
                    f.write(content)
        else:
            print(f"{output} already exists")
            if args.quick:
                print("found an existing gpx file, exiting")
                sys.exit(0)

fname = os.path.join(args.output_dir, "skipped.txt")
print(f"writing skipped activity list to {fname}")
with open(fname, "w") as f:
    f.write("\n".join(skipped))
