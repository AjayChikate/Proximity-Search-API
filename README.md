# Lab 7: Proximity Search API

A lightweight, zero-dependency C++ HTTP service for spatial proximity search and road-network distance ranking over a discrete grid.

---

##  Problem Overview

Given a dataset of 10,000 locations on a $100 \times 100$ grid (spanning $[0, 1] \times [0, 1]$), the objective is to recommend the **10 closest locations** matching a query category and circular search radius.

### Key Distance Definitions:
1. **Filtering Radius (Euclidean / Circular Distance):**
   $$\text{dist}_{\text{euc}} = \sqrt{(\text{lat}_1 - \text{lat}_2)^2 + (\text{lon}_1 - \text{lon}_2)^2} \le \text{rad}$$
   Only locations within this circular radius are valid candidates.
2. **Ranking Metric (Grid Traversal / Road-Network Shortest Path):**
   Real-world road networks have missing segments and obstacles. The true distance is the **shortest path hop count** on the provided road network graph, computed using Breadth-First Search (BFS).

---

##  API Specification

### **Endpoint:** `POST /search/` (or `GET /search/`)

### **Input Parameters (Multipart Form-Data or URL Encoded):**

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `lat` | Float | Query latitude (range $[0.0, 1.0]$) |
| `long` | Float | Query longitude (range $[0.0, 1.0]$) |
| `cat` | String | Target category (`bank`, `hospital`, `cafe`, `store`, `pharmacy`, `school`, `restaurant`, `park`) |
| `rad` | Float | Search radius for circular distance filtering |
| `link` | File / Text | Road link graph data (`LonA LatA LonB LatB` per line) |

### **Output Format (JSON):**

```json
{
  "results": [4850, 4948, 4648, 4753, 4947, 5349, 4451, 5348, 4351, 4654]
}
```

---

##  Build and Execution

The server is built with standard C++17 and native POSIX sockets, requiring no external libraries.

### 1. Compile

```bash
g++ -O2 -std=c++17 -o api api.cpp
```

### 2. Run

```bash
# Run in foreground (default port 5000 or custom port):
./api 5300

# Run in background (survives SSH disconnect):
setsid ./api 5300 > api.log 2>&1 < /dev/null &
```


---

##  API Usage Examples

### Using `cURL`:

```bash
curl -X POST "http://10.1.75.51:5300/search/" \
  -F "lat=0.50" \
  -F "long=0.50" \
  -F "cat=bank" \
  -F "rad=0.15" \
  -F "link=@link.txt"
```


##  Testing & Validation

A test script is included to compare API responses against ground-truth BFS results computed locally.

```bash
python test3.py http://10.1.75.51:5300
```

### Output:
```
===========================================================================
#   Query Details                              Matches    Status    
===========================================================================
1   (0.50, 0.50) bank       r=0.15             PASS (10/10) (78.3ms)
2   (0.20, 0.30) hospital   r=0.20             PASS (10/10) (81.5ms)
3   (0.80, 0.90) cafe       r=0.20             PASS (10/10) (69.2ms)
...
===========================================================================
Overall Accuracy: 100/100 (100.00%)
```

---

##  Project Structure

```
├── api.cpp          # C++ HTTP server with BFS traversal & proximity ranking
├── locations.csv    # Dataset with 10,000 locations [ID, Latitude, Longitude, Category]
├── link.txt         # Road network link connectivity data
├── tests            # Automated test suite and accuracy evaluator
└── README.md        # Documentation and API reference
```
