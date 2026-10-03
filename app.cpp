#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <unordered_map>
#include <cmath>
#include <algorithm>
#include <cstring>
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>

struct Location{
    int id;
    double lat,lon;
};

//KD-Tree:2D splits alternating between lat and lon

struct KDNode{
    Location loc;
    KDNode* left=nullptr;
    KDNode* right=nullptr;
};

KDNode* build_kdtree(std::vector<Location>& pts,int lo,int hi,int depth){

    if (lo>hi) return nullptr;
    int axis=depth%2;
    int mid=(lo+hi)/2;

    // partition around median on current axis

    std::nth_element(pts.begin()+lo,pts.begin()+mid,pts.begin()+hi+1,[axis](const Location& a,const Location& b){
            return axis==0 ? a.lat<b.lat : a.lon<b.lon;
        });


    KDNode* node=new KDNode;
    node->loc=pts[mid];
    node->left=build_kdtree(pts,lo,mid - 1,depth+1);
    node->right=build_kdtree(pts,mid+1,hi,depth+1);
    return node;
}

void radius_search(KDNode* node,double lat,double lon,double rad_sq,int depth,std::vector<std::pair<double,int>>& results){
   
    if (!node) return;

    double dx=lat - node->loc.lat;
    double dy=lon - node->loc.lon;

    if (dx*dx+dy*dy<=rad_sq)
        results.push_back({std::fabs(dx)+std::fabs(dy),node->loc.id});

    int axis=depth%2;
    double diff=(axis==0)?dx : dy;
    KDNode* near=(diff>=0)?node->right : node->left;
    KDNode* far =(diff>=0)?node->left : node->right;

    radius_search(near,lat,lon,rad_sq,depth+1,results);

    if (diff*diff<=rad_sq)
        radius_search(far,lat,lon,rad_sq,depth+1,results);
}

//one KD-Tree per category 

std::unordered_map<std::string,KDNode*>cat_trees;

void load_csv(const std::string& path){
    std::ifstream file(path);
    if (!file.is_open()) {
        std::cerr <<"cant open " <<path <<std::endl;
        return;
    }

    std::string line;
    std::getline(file,line);

    std::unordered_map<std::string,std::vector<Location>>buckets;

    int count=0;

    while (std::getline(file,line)){

        if (!line.empty() && line.back()=='\r')
            line.pop_back();

        std::stringstream ss(line);
        std::string token;
        std::getline(ss,token,',');
        int id=std::stoi(token);
        std::getline(ss,token,',');
        double lat=std::stod(token);
        std::getline(ss,token,',');
        double lon=std::stod(token);
        std::getline(ss,token,',');

        buckets[token].push_back({id,lat,lon});

        count++;
    }

    // building KD-Tree for each category
    for (auto& [cat,pts]:buckets)
        cat_trees[cat]= build_kdtree (pts,0,pts.size() - 1, 0);

    std::cout <<"loaded " <<count <<" locations,built "<<cat_trees.size() <<" KD-Trees" <<std::endl;
}



//HTTP Server

std::unordered_map<std::string,std::string>parse_params(const std::string& url){

    std::unordered_map<std::string,std::string>params;

    size_t qmark=url.find('?');

    if (qmark==std::string::npos) return params;

    std::string qs=url.substr(qmark+1);
    std::stringstream ss(qs);
    std::string pair;

    while (std::getline(ss,pair,'&')){
        size_t eq=pair.find('=');
        if (eq != std::string::npos)
            params[pair.substr(0,eq)]=pair.substr(eq+1);
    }

    return params;
}

std::string handle_search(const std::unordered_map<std::string,std::string>& params){

    if (params.find("lat")==params.end() || params.find("long")==params.end() || params.find("cat")==params.end() || params.find("rad")==params.end())
        return "{\"error\":\"need lat,long,cat,rad\"}";

    double lat=std::stod(params.at("lat"));
    double lon=std::stod(params.at("long"));
    std::string cat=params.at("cat");
    double rad=std::stod(params.at("rad"));
    auto it=cat_trees.find(cat);

    if (it==cat_trees.end())
        return "{\"error\":\"unknown category\"}";

    //KD-Tree range search 

    std::vector<std::pair<double,int>>candidates;

    radius_search(it->second,lat,lon,rad*rad,0,candidates);

    int k=std::min(10,(int)candidates.size());

    std::partial_sort(candidates.begin(),candidates.begin()+k,candidates.end());

    std::string json="{\"results\":[";
    for(int i=0;i<k;i++){
        if (i>0) json+=",";
        json+=std::to_string(candidates[i].second);
    }
    json+="]}";

    return json;

}

void send_response(int client,int code,const std::string& body){

    std::string status=(code==200)?"200 OK" : "400 Bad Request";
    std::string resp="HTTP/1.1 "+status+"\r\n"
                       "Content-Type: application/json\r\n"
                       "Content-Length: "+std::to_string(body.size())+"\r\n"
                       "Connection: close\r\n\r\n"+body;
    ssize_t ret=write(client,resp.c_str(),resp.size());
    (void)ret;

}






int main(){

    load_csv("locations.csv");

    int server_fd=socket(AF_INET,SOCK_STREAM,0);
    if (server_fd <0) { perror("socket");return 1;}

    int opt=1;

    setsockopt(server_fd,SOL_SOCKET,SO_REUSEADDR,&opt,sizeof(opt));

    struct sockaddr_in addr;
    memset(&addr,0,sizeof(addr));
    addr.sin_family=AF_INET;
    addr.sin_addr.s_addr=INADDR_ANY;
    addr.sin_port=htons(5000);

    if (bind(server_fd,(struct sockaddr*)&addr,sizeof(addr))<0) {
        perror("bind failed (port already in use?)");
        return 1;
    }

    if (listen(server_fd,10)<0) { perror("listen");return 1;}

    std::cout <<"server running on http://0.0.0.0:5000" <<std::endl;

    while (true){

        int client=accept(server_fd,NULL,NULL);
        if (client <0) continue;

        try {
            char buf[4096];
            int n=read(client,buf,sizeof(buf) - 1);
            if (n<=0) { close(client);continue;}
            buf[n]='\0';

            std::string req(buf);
            size_t start=req.find(' ')+1;
            size_t end=req.find(' ',start);
            std::string url=req.substr(start,end - start);

            if (url.find("/search")==0){

                auto params=parse_params(url);
                std::string body=handle_search(params);
                bool is_error=body.find("error") != std::string::npos;
                send_response(client,is_error?400 : 200,body);

            } 
            else{

                send_response(client,200,"{\"message\":\"use /search/ endpoint\"}");

            }

        } 
        catch(std::exception& e){

            std::cerr <<"error: " <<e.what() <<std::endl;
            send_response(client,400,"{\"error\":\"bad request\"}");

        }

        close(client);
    }

    close(server_fd);

    return 0;




    
}

