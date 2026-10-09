import requests
import csv
import heapq
from collections import defaultdict, deque

API = "http://10.1.75.51:5300"




locations = {}  
grid = {}      
cat_points = defaultdict(list)  

with open("locations.csv") as f:
    for row in csv.DictReader(f):
        id = int(row["ID"])
        lat = round(float(row["Latitude"]), 6)
        lon = round(float(row["Longitude"]), 6)
        cat = row["Category"]
        locations[id] = (lat, lon, cat)
        grid[(lat, lon)] = id
        cat_points[cat].append((id, lat, lon))

print(f"loaded {len(locations)} locations")




graph = defaultdict(set)

with open("link.txt") as f:
    for line in f:
        parts = line.strip().split()
        if len(parts) != 4:
            continue
        lonA, latA, lonB, latB = round(float(parts[0]), 6), round(float(parts[1]), 6), \
                                  round(float(parts[2]), 6), round(float(parts[3]), 6)
        a = (latA, lonA)
        b = (latB, lonB)
        graph[a].add(b)
        graph[b].add(a)

print(f"loaded {sum(len(v) for v in graph.values())//2} links, {len(graph)} nodes in graph")

STEP = round(1.0 / 99, 6) 

def bfs_distance(start, targets):
    dist = {start: 0}
    queue = deque([start])
    target_set = set(targets)
    found = {}

    while queue and len(found) < len(target_set):
        cur = queue.popleft()
        if cur in target_set:
            found[cur] = dist[cur]

        for nb in graph.get(cur, []):
            if nb not in dist:
                dist[nb] = dist[cur] + 1
                queue.append(nb)

    return found


def euclidean(lat1, lon1, lat2, lon2):
    return ((lat1-lat2)**2 + (lon1-lon2)**2) ** 0.5


def true_top10(lat, lon, cat, rad):
    qi = round(lat / STEP)
    qj = round(lon / STEP)
    qlat = round(qi * STEP, 6)
    qlon = round(qj * STEP, 6)
    query_node = (qlat, qlon)

    targets = []
    for id, plat, plon in cat_points[cat]:
        if euclidean(lat, lon, plat, plon) <= rad:
            targets.append((plat, plon))

    if not targets:
        return []

    dists = bfs_distance(query_node, targets)

    scored = []
    for (plat, plon), d in dists.items():
        if (plat, plon) in grid:
            scored.append((d, grid[(plat, plon)]))

    scored.sort()
    return [id for _, id in scored[:10]]




def query_api(lat, lon, cat, rad):
    try:
        r = requests.get(f"{API}/search/", params={
            "lat": lat, "long": lon, "cat": cat, "rad": rad
        }, timeout=10)
        data = r.json()
        return data.get("results", [])
    except Exception as e:
        print(f"  API error: {e}")
        return []


def compare(api_ids, true_ids):
    api_set = set(api_ids)
    true_set = set(true_ids)
    overlap = api_set & true_set
    return len(overlap), len(true_set)


test_queries = [
    (0.5, 0.5, "bank", 0.15),
    (0.2, 0.3, "hospital", 0.2),
    (0.8, 0.9, "cafe", 0.2),
    (0.1, 0.1, "store", 0.15),
    (0.7, 0.4, "pharmacy", 0.18),
    (0.3, 0.8, "school", 0.2),
    (0.9, 0.2, "restaurant", 0.15),
    (0.5, 0.0, "park", 0.2),
    (0.0, 0.5, "bank", 0.2),
    (0.6, 0.6, "cafe", 0.12),
]

print(f"\n{'='*70}")
print(f"{'Query':<40} {'Match':>8} {'Score':>8}")
print(f"{'='*70}")

total_match = 0
total_possible = 0

for lat, lon, cat, rad in test_queries:
    api_ids = query_api(lat, lon, cat, rad)
    truth = true_top10(lat, lon, cat, rad)
    match, possible = compare(api_ids, truth)
    total_match += match
    total_possible += possible

    tag = "PERFECT" if match == possible else f"{match}/{possible}"
    print(f"  lat={lat}, lon={lon}, cat={cat:<12} rad={rad}  ->  {tag}")
    if match < possible:
        print(f"    API:   {api_ids}")
        print(f"    Truth: {truth}")

print(f"{'='*70}")
print(f"  Total: {total_match}/{total_possible} matched  "
      f"({total_match/total_possible*100:.1f}% accuracy)")
print(f"{'='*70}")

