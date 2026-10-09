#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <unordered_map>
#include <cmath>
#include <algorithm>
#include <cstring>
#include <queue>
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <csignal>

using namespace std;

struct Location {
    int id;
    double lat, lon;
    string cat;
    int grid_node; 
};

const int grid = 100;
const double step = 1.0 / 99.0;
unordered_map<string, vector<Location>> cat_locs;

int to_grid_node(double lat, double lon) {

    int i = (int)round(lat / step);
    int j = (int)round(lon / step);

    if (i < 0) i = 0; if (i >= grid) i = grid - 1;
    if (j < 0) j = 0; if (j >= grid) j = grid - 1;

    return i * grid + j;

}


void load_csv(const string& path) {

    ifstream file(path);

    if (!file.is_open()) {
        cerr << "cant open " << path << endl;
        return;
    }

    string line;
    getline(file, line);

    int count = 0;

    while (getline(file, line)) {

        if (!line.empty() && line.back() == '\r') line.pop_back();

        stringstream ss(line);

        string tok;
        getline(ss, tok, ','); 
        int id = stoi(tok);
        getline(ss, tok, ','); 
        double lat = stod(tok);
        getline(ss, tok, ','); 
        double lon = stod(tok);
        getline(ss, tok, ','); 
        string cat = tok;

        Location loc;

        loc.id = id;
        loc.lat = lat; 
        loc.lon = lon;
        loc.cat = cat; 
        loc.grid_node = to_grid_node(lat, lon);
        cat_locs[cat].push_back(loc);

        count++;

    }

    cout << "loaded " << count << " locations, " << cat_locs.size() << " categories" << endl;
}




void bfs(const string& link_content, int source, int dist[]) {
 
    for (int i = 0; i < grid * grid; i++) dist[i] = -1;

    vector<vector<int>> adj(grid * grid);
    istringstream stream(link_content);

    double lonA, latA, lonB, latB;

    while (stream >> lonA >> latA >> lonB >> latB) {
        int a = to_grid_node(latA, lonA);
        int b = to_grid_node(latB, lonB);
        adj[a].push_back(b);
        adj[b].push_back(a);
    }

    // BFS
    queue<int> q;
    dist[source] = 0;
    q.push(source);
    while (!q.empty()) {
        int cur = q.front(); 
        q.pop();
        for (int nb : adj[cur]) {
            if (dist[nb] == -1) {
                dist[nb] = dist[cur] + 1;
                q.push(nb);
            }
        }
    }
}

//HTTP Server

string read_full_request(int client) {

    string raw;

    char buf[8192];

    int n = read(client, buf, sizeof(buf) - 1);

    if (n <= 0) return "";

    raw.append(buf, n);

    size_t header_end = raw.find("\r\n\r\n");

    if (header_end == string::npos) return raw;

    int content_length = 0;

    string lower_raw = raw;

    size_t cl_pos = lower_raw.find("Content-Length: ");

    if (cl_pos == string::npos) cl_pos = lower_raw.find("content-length: ");

    if (cl_pos != string::npos) {
        size_t cl_end = lower_raw.find("\r\n", cl_pos);
        content_length = stoi(lower_raw.substr(cl_pos + 16, cl_end - cl_pos - 16));
    }

    int body_start = header_end + 4;
    int body_received = raw.size() - body_start;
    int remaining = content_length - body_received;

    while (remaining > 0) {
        n = read(client, buf, min((int)sizeof(buf), remaining));
        if (n <= 0) break;
        raw.append(buf, n);
        remaining -= n;
    }
    return raw;
}

unordered_map<string, string> parse_query_params(const string& url) {

    unordered_map<string, string> params;

    size_t qmark = url.find('?');

    if (qmark == string::npos) return params;

    string qs = url.substr(qmark + 1);

    stringstream ss(qs);

    string pair;

    while (getline(ss, pair, '&')) {
        size_t eq = pair.find('=');
        if (eq != string::npos)
            params[pair.substr(0, eq)] = pair.substr(eq + 1);
    }


    return params;
}

unordered_map<string, string> parse_multipart(const string& body, const string& boundary) {

    unordered_map<string, string> fields;

    string delim = "--" + boundary;

    size_t pos = 0;

    while (true) {

        size_t start = body.find(delim, pos);

        if (start == string::npos) break;

        start += delim.size();

        if (start + 2 <= body.size() && body.substr(start, 2) == "--") break;

        start += 2; 

        size_t end = body.find(delim, start);

        if (end == string::npos) break;

        string part = body.substr(start, end - start);
     
        if (part.size() >= 2 && part.substr(part.size()-2) == "\r\n")
            part = part.substr(0, part.size()-2);

    
        size_t sep = part.find("\r\n\r\n");

        if (sep == string::npos) { 
            pos = end; 
            continue; 
        }

        string headers = part.substr(0, sep);
        string content = part.substr(sep + 4);

        size_t name_pos = headers.find("name=\"");

        if (name_pos != string::npos) {
            name_pos += 6;
            size_t name_end = headers.find("\"", name_pos);
            string name = headers.substr(name_pos, name_end - name_pos);
            fields[name] = content;

        }

        pos = end;

    }
    return fields;
}

string handle_search(double lat, double lon, const string& cat, double rad, const string& link_content) {
    
    auto it = cat_locs.find(cat);
    
    if (it == cat_locs.end())
        return "{\"error\":\"unknown category\"}";

    int src = to_grid_node(lat, lon);

    int dist[grid * grid];

    bfs(link_content, src, dist);

    double rad_sq = rad * rad;
    vector<pair<int, int>> candidates; 

    for (const auto& loc : it->second) {
        double dx = lat - loc.lat;
        double dy = lon - loc.lon;
        if (dx * dx + dy * dy > rad_sq) continue; // outside radius
        int d = dist[loc.grid_node];
        if (d < 0) continue; // unreachable
        candidates.push_back({d, loc.id});
    }

    int k = min(10, (int)candidates.size());

    partial_sort(candidates.begin(), candidates.begin() + k, candidates.end());

    string json = "{\"results\":[";

    for (int i = 0; i < k; i++) {
        if (i > 0) json += ",";
        json += to_string(candidates[i].second);
    }

    json += "]}";

    return json;
}

void send_response(int client, int code, const string& body) {

    string status = (code == 200) ? "200 OK" : "400 Bad Request";

    string resp = "HTTP/1.1 " + status + "\r\n"
                       "Content-Type: application/json\r\n"
                       "Content-Length: " + to_string(body.size()) + "\r\n"
                       "Connection: close\r\n\r\n" + body;

    ssize_t ret = write(client, resp.c_str(), resp.size());
    (void)ret;

}



int main(int argc, char* argv[]) {

    signal(SIGPIPE, SIG_IGN);

    int port = (argc > 1) ? stoi(argv[1]) : 5000;

    load_csv("locations.csv");

    int server_fd = socket(AF_INET, SOCK_STREAM, 0);

    if (server_fd < 0) { perror("socket"); return 1; }

    int opt = 1;

    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons(port);

    if (bind(server_fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        perror("bind failed"); 
        return 1;
    }

    if (listen(server_fd, 128) < 0) { 
        perror("listen");
        return 1; 
    }

    cout << "server running on http://0.0.0.0:" << port << endl;

    while (true) {


        int client = accept(server_fd, NULL, NULL);

        if (client < 0) continue;

        try {
            string raw = read_full_request(client);

            if (raw.empty()) { 
                close(client); 
                continue; 
            }

            size_t first_space = raw.find(' ');
            string method = raw.substr(0, first_space);

            size_t second_space = raw.find(' ', first_space + 1);
            string url = raw.substr(first_space + 1, second_space - first_space - 1);

            if (url.find("/search") != 0) {
                send_response(client, 200, "{\"message\":\"use /search/ endpoint\"}");
                close(client); 
                continue;
            }

            double lat = 0, lon = 0, rad = 0;
            string cat, link_content;

            size_t body_start = raw.find("\r\n\r\n");
            string body = (body_start != string::npos) ? raw.substr(body_start + 4) : "";

            size_t ct_pos = raw.find("Content-Type: ");
            string content_type = "";

            if (ct_pos != string::npos) {
                size_t ct_end = raw.find("\r\n", ct_pos);
                content_type = raw.substr(ct_pos + 14, ct_end - ct_pos - 14);
            }

            if (content_type.find("multipart/form-data") != string::npos) {
                size_t bnd_pos = content_type.find("boundary=");
                string boundary = content_type.substr(bnd_pos + 9);
                while (!boundary.empty() && (boundary.back() == ' ' || boundary.back() == ';'))
                    boundary.pop_back();

                auto fields = parse_multipart(body, boundary);

                if (fields.count("lat")) lat = stod(fields["lat"]);
                if (fields.count("long")) lon = stod(fields["long"]);
                if (fields.count("cat")) cat = fields["cat"];
                if (fields.count("rad")) rad = stod(fields["rad"]);
                if (fields.count("link")) link_content = fields["link"];

            } 
            else {
                auto params = parse_query_params(url);
                if (params.count("lat")) lat = stod(params["lat"]);
                if (params.count("long")) lon = stod(params["long"]);
                if (params.count("cat")) cat = params["cat"];
                if (params.count("rad")) rad = stod(params["rad"]);
                link_content = body;
            }

            string result = handle_search(lat, lon, cat, rad, link_content);


            bool is_error = result.find("error") != string::npos;

            send_response(client, is_error ? 400 : 200, result);

        } 
        catch (exception& e) {
            cerr << "error: " << e.what() << endl;
            send_response(client, 400, "{\"error\":\"bad request\"}");
        }


        close(client);
    }

    close(server_fd);

    
    return 0;
}

