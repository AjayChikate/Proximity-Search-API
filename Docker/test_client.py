import os
import sys
import csv
import time
import requests
from collections import defaultdict, deque

API_URL = os.getenv("API_URL", "http://api:5000").rstrip("/")
LINK_PATH = os.getenv("LINK_FILE", "link.txt")
CSV_PATH = os.getenv("CSV_FILE", "locations.csv")

STEP = 1.0 / 99.0
GRID = 100

def to_grid_node(lat, lon):
    i = max(0, min(GRID - 1, round(lat / STEP)))
    j = max(0, min(GRID - 1, round(lon / STEP)))
    return i * GRID + j

locations = {}
cat_locations = defaultdict(list)

with open(CSV_PATH, mode="r") as f:
    for row in csv.DictReader(f):
        loc_id = int(row["ID"])
        lat = float(row["Latitude"])
        lon = float(row["Longitude"])
        cat = row["Category"]
        node = to_grid_node(lat, lon)
        locations[loc_id] = (lat, lon, cat, node)
        cat_locations[cat].append((loc_id, lat, lon, node))

def build_graph(link_filepath):
    adj = defaultdict(list)
    with open(link_filepath, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 4:
                lonA, latA, lonB, latB = map(float, parts)
                u = to_grid_node(latA, lonA)
                v = to_grid_node(latB, lonB)
                adj[u].append(v)
                adj[v].append(u)
    return adj

def compute_ground_truth(lat, lon, cat, rad, adj):
    src = to_grid_node(lat, lon)
    dist = {}
    q = deque([src])
    dist[src] = 0

    while q:
        cur = q.popleft()
        for nb in adj[cur]:
            if nb not in dist:
                dist[nb] = dist[cur] + 1
                q.append(nb)

    rad_sq = rad * rad
    candidates = []

    for loc_id, l_lat, l_lon, l_node in cat_locations[cat]:
        dx = lat - l_lat
        dy = lon - l_lon
        if dx * dx + dy * dy <= rad_sq:
            if l_node in dist:
                candidates.append((dist[l_node], loc_id))

    candidates.sort(key=lambda x: (x[0], x[1]))
    return [c[1] for c in candidates[:10]]

def wait_for_api():
    url = f"{API_URL}/search/"
    print(f"Waiting for API service at {API_URL} ...")
    for _ in range(30):
        try:
            r = requests.get(url, timeout=2)
            if r.status_code in (200, 400):
                print("API service is up and ready!\n")
                return True
        except Exception:
            pass
        time.sleep(1)
    print("API service did not respond in time.")
    return False

def query_api(lat, lon, cat, rad):
    url = f"{API_URL}/search/"
    data = {
        "lat": str(lat),
        "long": str(lon),
        "cat": cat,
        "rad": str(rad)
    }
    with open(LINK_PATH, "rb") as fh:
        files = {"link": ("link.txt", fh, "text/plain")}
        resp = requests.post(url, data=data, files=files, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("results", [])
        return []

def main():
    if not wait_for_api():
        sys.exit(1)

    print("Building ground-truth BFS graph from link file...")
    adj = build_graph(LINK_PATH)

    test_queries = [
        {"lat": 0.5, "long": 0.5, "cat": "bank", "rad": 0.15},
        {"lat": 0.2, "long": 0.3, "cat": "hospital", "rad": 0.20},
        {"lat": 0.8, "long": 0.9, "cat": "cafe", "rad": 0.20},
        {"lat": 0.1, "long": 0.1, "cat": "store", "rad": 0.15},
        {"lat": 0.7, "long": 0.4, "cat": "pharmacy", "rad": 0.18},
        {"lat": 0.3, "long": 0.8, "cat": "school", "rad": 0.20},
        {"lat": 0.9, "long": 0.2, "cat": "restaurant", "rad": 0.15},
        {"lat": 0.5, "long": 0.0, "cat": "park", "rad": 0.20},
        {"lat": 0.0, "long": 0.5, "cat": "bank", "rad": 0.20},
        {"lat": 0.6, "long": 0.6, "cat": "cafe", "rad": 0.12},
    ]

    total_matches = 0
    total_expected = 0

    print("=" * 75)
    print(f"{'#':<3} {'Query Details':<40} {'Matches':<10} {'Status'}")
    print("=" * 75)

    for idx, q in enumerate(test_queries, 1):
        lat, lon, cat, rad = q["lat"], q["long"], q["cat"], q["rad"]
        expected = compute_ground_truth(lat, lon, cat, rad, adj)

        start_t = time.time()
        api_result = query_api(lat, lon, cat, rad)
        elapsed = (time.time() - start_t) * 1000

        matches = len(set(api_result) & set(expected))
        total_matches += matches
        total_expected += len(expected)

        status = "PASS (10/10)" if matches == len(expected) else f"{matches}/{len(expected)}"
        desc = f"({lat:.2f}, {lon:.2f}) {cat:<10} r={rad:.2f}"
        print(f"{idx:<3} {desc:<40} {status:<10} ({elapsed:.1f}ms)")

    print("=" * 75)
    acc = (total_matches / total_expected * 100) if total_expected > 0 else 0
    print(f"Overall Accuracy: {total_matches}/{total_expected} ({acc:.2f}%)\n")

    if total_matches == total_expected:
        print("All test queries passed with 100% accuracy!")
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()

