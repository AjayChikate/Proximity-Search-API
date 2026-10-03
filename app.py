from flask import Flask, request, jsonify
import pandas as pd
import numpy as np
from scipy.spatial import KDTree
import heapq

app=Flask(__name__)
df=pd.read_csv("locations.csv")

# each category maps to:(ids_array, coords_array, kdtree)
cat_index={}

for cat, group in df.groupby("Category"):
    ids=group["ID"].values
    coords=group[["Latitude", "Longitude"]].values
    tree=KDTree(coords)
    cat_index[cat]=(ids, coords, tree)


def manhattan(p1, p2):
    return abs(p1[0]-p2[0])+abs(p1[1]-p2[1])


@app.route("/search/", methods=["GET"])
def search():
    lat=request.args.get("lat", type=float)
    long=request.args.get("long", type=float)
    cat=request.args.get("cat", type=str)
    rad=request.args.get("rad", type=float)

    if lat is None or long is None or cat is None or rad is None:
        return jsonify({"error":"need lat, long, cat, rad"}), 400

    if cat not in cat_index:
        return jsonify({"error":f"unknown category: {cat}"}), 400

    query_pt=np.array([lat, long])
    ids, coords,tree=cat_index[cat]

    # step 1:find all points within euclidean radius
    nearby_idx=tree.query_ball_point(query_pt, rad)

    if len(nearby_idx)==0:
        return jsonify({"results":[]})

    # step 2:rank by manhattan distance,pick top 10
    candidates=[]
    for i in nearby_idx:
        dist=manhattan(query_pt, coords[i])
        candidates.append((dist, int(ids[i])))

    # get 10 closest by grid distance
    top10=heapq.nsmallest(10, candidates, key=lambda x: x[0])
    result_ids=[loc_id for _, loc_id in top10]

    return jsonify({"results": result_ids})


if __name__ == "__main__":
    
    print(f"Loaded {len(df)} locations across {len(cat_index)} categories")
    app.run(debug=True, port=5000)
