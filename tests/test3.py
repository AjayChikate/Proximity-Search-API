
import argparse
import csv
import json
import math
import re
import sys
import time

import requests

BASE_URL = "http://10.1.75.51:5300"
ROUTE = "/search/"
CSV_PATH = "locations.csv"
LINK_PATH = "link.txt"

QUERIES = [
    (0.50, 0.50, "cafe", 0.20),
    (0.10, 0.10, "bank", 0.25),
    (0.90, 0.20, "hospital", 0.30),
    (0.25, 0.75, "park", 0.25),
    (0.75, 0.75, "pharmacy", 0.30),
    (0.05, 0.95, "restaurant", 0.35),
    (0.60, 0.30, "school", 0.25),
    (0.40, 0.55, "store", 0.20),
    (0.95, 0.95, "cafe", 0.40),
    (0.00, 0.00, "bank", 0.30),
]


def load_locations(path):
    locs = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            locs[int(row["ID"])] = (
                float(row["Latitude"]),
                float(row["Longitude"]),
                row["Category"].strip(),
            )
    return locs


def send(mode, method, lat, lon, cat, rad):
    url = BASE_URL + ROUTE
    fields = {"lat": lat, "long": lon, "cat": cat, "rad": rad}

    if mode == "file":
        with open(LINK_PATH, "rb") as fh:
            return requests.post(
                url, data=fields, files={"link": (LINK_PATH, fh, "text/plain")}, timeout=120
            )

    if mode == "text":
        with open(LINK_PATH) as fh:
            fields["link"] = fh.read()
    else:  # path
        fields["link"] = LINK_PATH

    if method == "get":
        return requests.get(url, params=fields, timeout=120)
    return requests.post(url, data=fields, timeout=120)


def extract_ids(resp):
    try:
        body = resp.json()
    except ValueError:
        return [int(x) for x in re.findall(r"\d+", resp.text)]

    def walk(o):
        if isinstance(o, list):
            if all(isinstance(x, (int, float)) for x in o):
                return [int(x) for x in o]
            if all(isinstance(x, dict) for x in o):
                out = []
                for d in o:
                    for k in ("id", "ID", "Id"):
                        if k in d:
                            out.append(int(d[k]))
                            break
                return out
        if isinstance(o, dict):
            for k in ("ids", "IDs", "result", "results", "locations", "recommendations", "data"):
                if k in o:
                    r = walk(o[k])
                    if r:
                        return r
            for v in o.values():
                r = walk(v)
                if r:
                    return r
        return []

    return walk(body)


def check(ids, locs, lat, lon, cat, rad):
    problems = []
    if len(ids) != 10:
        problems.append(f"expected 10 ids, got {len(ids)}")
    if len(set(ids)) != len(ids):
        problems.append("duplicate ids")
    for i in ids:
        if i not in locs:
            problems.append(f"id {i} not in dataset")
            continue
        la, lo, c = locs[i]
        if c != cat:
            problems.append(f"id {i} category {c!r} != {cat!r}")
        d = math.hypot(la - lat, lo - lon)
        if d > rad + 1e-9:
            problems.append(f"id {i} outside radius ({d:.4f} > {rad})")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["file", "text", "path"], default="file")
    ap.add_argument("--method", choices=["post", "get"], default="post")
    args = ap.parse_args()

    locs = load_locations(CSV_PATH)
    print(f"Loaded {len(locs)} locations; target {BASE_URL}{ROUTE} (mode={args.mode})\n")

    failures = 0
    for n, (lat, lon, cat, rad) in enumerate(QUERIES, 1):
        t0 = time.perf_counter()
        try:
            resp = send(args.mode, args.method, lat, lon, cat, rad)
        except requests.RequestException as e:
            print(f"[{n}] REQUEST ERROR: {e}")
            failures += 1
            continue
        dt = (time.perf_counter() - t0) * 1000

        if resp.status_code != 200:
            print(f"[{n}] HTTP {resp.status_code} ({dt:.0f} ms): {resp.text[:200]}")
            failures += 1
            continue

        ids = extract_ids(resp)
        problems = check(ids, locs, lat, lon, cat, rad)
        status = "OK  " if not problems else "FAIL"
        print(f"[{n}] {status} ({dt:.0f} ms) q=({lat},{lon},{cat},{rad}) -> {ids}")
        for p in problems:
            print(f"      - {p}")
        failures += bool(problems)

    print(f"\n{len(QUERIES) - failures}/{len(QUERIES)} queries passed shape checks")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()