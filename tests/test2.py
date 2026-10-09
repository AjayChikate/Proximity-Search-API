import sys
import csv
import time
import requests
from collections import defaultdict, deque

API_URL = sys.argv[1] if len(sys.argv) > 1 else "http://10.1.75.51:5300"

STEP = 1.0 / 99.0
GRID = 100

def to_grid_node(lat, lon):
    i = max(0, min(GRID - 1, round(lat / STEP)))
    j = max(0, min(GRID - 1, round(lon / STEP)))
    return i * GRID + j


locations = {}
cat_locations = defaultdict(list)

with open("locations.csv", mode="r") as f:
    reader = csv.DictReader(f)
    for row in reader:
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

def query_api(lat, lon, cat, rad, link_filepath):
    url = f"{API_URL.rstrip('/')}/search/"
    data = {
        "lat": str(lat),
        "long": str(lon),
        "cat": cat,
        "rad": str(rad)
    }
    with open(link_filepath, "rb") as link_file:
        files = {"link": ("link.txt", link_file, "text/plain")}
        resp = requests.post(url, data=data, files=files, timeout=15)
        if resp.status_code == 200:
            return resp.json().get("results", [])
        else:
            print(f"  [Error] status: {resp.status_code}, response: {resp.text}")
            return []

def main():
    link_file = "link.txt"
    print(f"Testing API at: {API_URL}")
    print("Building local ground-truth graph from link.txt...")
    adj = build_graph(link_file)

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

    print("\n" + "=" * 75)
    print(f"{'#':<3} {'Query Details':<42} {'Matches':<10} {'Status':<10}")
    print("=" * 75)

    for idx, q in enumerate(test_queries, 1):
        lat, lon, cat, rad = q["lat"], q["long"], q["cat"], q["rad"]
        expected = compute_ground_truth(lat, lon, cat, rad, adj)
        
        try:
            start_t = time.time()
            api_result = query_api(lat, lon, cat, rad, link_file)
            elapsed = (time.time() - start_t) * 1000
        except Exception as e:
            print(f"Query {idx} failed with exception: {e}")
            api_result = []
            elapsed = 0
        matches = len(set(api_result) & set(expected))
        total_matches += matches
        total_expected += len(expected)

        status = "PASS (10/10)" if matches == len(expected) and len(expected) > 0 else f"{matches}/{len(expected)}"
        query_desc = f"({lat:.2f}, {lon:.2f}) {cat:<10} r={rad:.2f}"
        print(f"{idx:<3} {query_desc:<42} {status:<10} ({elapsed:.1f}ms)")
        
        if matches < len(expected):
            print(f"    Expected: {expected}")
            print(f"    Returned: {api_result}")

    print("=" * 75)
    accuracy = (total_matches / total_expected * 100) if total_expected > 0 else 0
    print(f"Overall Accuracy: {total_matches}/{total_expected} ({accuracy:.2f}%)\n")

if __name__ == "__main__":
    main()

