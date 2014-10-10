# -*- coding: utf-8 -*-
"""
Created on Tue Nov 12 20:22:58 2013

@author: tobydavies
"""

'''
Version 1

TODO:
Metric calculation
Segment colour plotting
Inheritance via boundary
'''

from shapely.geometry import Point, LineString, Polygon
import xml.sax as sax
import pyproj
import pickle as pk
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.path import Path
import ModestMaps as mm
from ModestMaps import Geo
from ModestMaps import OpenStreetMap

projection = pyproj.Proj('+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +wktext +no_defs')

#projection = pyproj.Proj('+proj=tmerc +lat_0=49.000000000 +lon_0=-2.000000000 +k=0.999601 +x_0=400000.000 +y_0=-100000.000 +ellps=airy +towgs84=375,-111,431,0,0,0,0')

#projection = pyproj.Proj("+init=EPSG:4326")

class Node():
    
    def __init__(self,feature_id,lonlat,tags):
        self.feature_id = feature_id
        self.lonlat = lonlat
        self.lon, self.lat = lonlat
#        self.geometry = Point(projection(*lonlat))
        self.tags = tags


class Way():
    
    def __init__(self,feature_id,refs,tags):
        self.feature_id = feature_id
        self.nds = refs
#        self.geometry = LineString([(nodes[ref].x,nodes[ref].y) for ref in refs])
        self.tags = tags


class Relation():
    
    def __init__(self,feature_id,members,tags):
        self.feature_id = feature_id
        self.members = members
        self.tags = tags


class OSMHandler(sax.handler.ContentHandler):
    
    def __init__(self):
        sax.handler.ContentHandler.__init__(self)
        self.id = None
        self.geometry = None
        self.tags = None
        self.nodes = {}
        self.ways = {}
        self.relations = {}
    
    def startElement(self,name,attrs):
        if name=='node':
            self.id = attrs['id']
            self.tags = {}
            self.geometry = map(float,(attrs['lon'],attrs ['lat']))
        
        elif name=='way':
            self.id = attrs['id']
            self.tags = {}
            self.geometry = []
        
        elif name=='nd':
            self.geometry.append(attrs['ref'])
        
        elif name=='relation':
            self.id = attrs['id']
            self.tags = {}
            self.geometry=[]
        
        elif name=='member':
            self.geometry.append(attrs['ref'])

        elif name=='tag':
            self.tags[attrs['k']] = attrs['v']
    
    def endElement(self,name):
        if name=='node':
            self.nodes[self.id] = Node(self.id,self.geometry,self.tags)
            self.id = None
            self.geometry = None
            self.tags = None
        
        elif name=='way':
            self.ways[self.id ] = Way(self.id,self.geometry,self.tags)
            self.reset()
        
        elif name=='relation':
            self.relations[self.id ] = Relation(self.id,self.geometry,self.tags)
            self.reset()
    
    def reset (self):
        self.id = None
        self.geometry = None
        self.tags = None


class OSMData():
    
    def __init__(self,nodes,ways,relations):
        self.nodes = nodes
        self.ways = ways
        self.relations = relations
    
    def save(self,filename):
        f=open(filename,'wb')
        pk.dump(self,f)
        f.close()


class OSMStreetNet():
    
    def __init__(self):
        
        self.g=nx.MultiGraph()
        self.posdict={}
    
    def load_from_data(self,Data):
        
        print 'Building the network'
        self.build_network(Data)
        
        print 'Building position dictionary'
        self.build_posdict(Data)
        
        print 'Unifying segments'
        self.unify_segments()
        
#        self.remove_rdb()
#        
#        self.assign_indices()
    
    
    def inherit(self,g,posdict):
        
        self.g=g
        self.posdict=posdict
    
    
    def build_network(self,Data):
        
        g=nx.MultiGraph()
        
        highways_all=[way for way in Data.ways.values() if 'highway' in way.tags]
        
        blacklist=['footway','service']
        
        highways=[way for way in highways_all if way.tags['highway'] not in blacklist]
        
        for way in highways:
            for i in range(len(way.nds)-1):
                atts={}
                if 'junction' in way.tags:
                    if way.tags['junction']=='roundabout':
                        atts['rdb']=True
                else:
                    atts['rdb']=False
                atts['poly_line']=[way.nds[i],way.nds[i+1]]
                g.add_edge(way.nds[i],way.nds[i+1],attr_dict=atts)
        
        g=nx.connected_component_subgraphs(g)[0]
        
        self.g=g
    
    
    def build_posdict(self,Data):
        
        self.posdict={}
        
        for nd in self.g:
            self.posdict[nd]=Data.nodes[nd].lonlat
    
    
    def save(self,filename):
        f=open(filename,'wb')
        pk.dump(self,f)
        f.close()

    
    def unify_segments(self):
        
        node_kill_list=[]
        edge_add_list=[]
        
        for v in self.g:
            node_checker=[x!=v and len(self.g[v][x])==1 for x in self.g[v]]
            if len(node_checker)==2 and all(node_checker):
                node_kill_list.append(v)
                
        nodes_seen=[]
        paths=[]
        
        for v in node_kill_list:
            
            if v not in nodes_seen:
                
                to_connect=[x for x in self.g[v]]
                w0=to_connect[0]
                w1=to_connect[1]
                
                nodes_seen.append(v)
                
                path=[w0,v,w1]
                
                loop=False
                
                while True:
                    
                    if path[0]==path[-1]:
                        loop=True
                        break
                    
                    if path[0] not in node_kill_list:
                        break
                    
                    nodes_seen.append(path[0])
                    next_node=[x for x in self.g[path[0]] if x!=path[1]][0]
                    path.insert(0,next_node)
                
                while True:
                    
                    if path[0]==path[-1]:
                        loop=True
                        break
                    
                    if path[-1] not in node_kill_list:
                        break
                    
                    nodes_seen.append(path[-1])
                    next_node=[x for x in self.g[path[-1]] if x!=path[-2]][0]
                    path.append(next_node)
                
                if not loop:
                    paths.append(path)
        
        for path in paths:
            
            merged_atts={'rdb': self.g[path[0]][path[1]][0]['rdb'], 'poly_line': path}
            edge_add_list.append((path[0],path[-1],merged_atts))
                        
        self.g.remove_nodes_from(node_kill_list)
        self.g.add_edges_from(edge_add_list)
    
    
    def assign_indices(self):
        ind_counter=0
        for e in self.g.edges(data=True):
            e[2]['ind']=ind_counter
            ind_counter+=1
    
    
    def within_boundary(self,poly):
        
        #Create new graph
        g_new=nx.MultiGraph()
        posdict_new={}
        
        #Make a shapely polygon from the boundary
        boundary=Polygon([projection(*lonlat) for lonlat in poly])
        
        print boundary.area
        
        #Loop the edges
        for e in self.g.edges(data=True):
            #Make a polyline for each
            edge_line=LineString([projection(*self.posdict[nd]) for nd in e[2]['poly_line']])
#            print edge_line.length
            
            #Check intersection
            if edge_line.intersects(boundary):
                #Add edge to new graph
                g_new.add_edge(e[0],e[1],attr_dict=e[2])
                #Add all nodes to the new posdict
                for nd in e[2]['poly_line']:
                    posdict_new[nd]=self.posdict[nd]
                
        net_new=OSMStreetNet()
        net_new.inherit(g_new,posdict_new)
        
        return net_new
    
    
    def plot_network_plain(self,min_lon,min_lat,max_lon,max_lat,filename,
                           show_edges=True,show_nodes=False,edge_width=1,
                           node_size=7,edge_col='k',node_col='r',
                           background='w'):
        
        min_x, min_y = projection(min_lon,min_lat)
        max_x, max_y = projection(max_lon,max_lat)
        
        ratio=(max_y-min_y)/(max_x-min_x)
        
        print 'Aspect ratio '+str(ratio)

        fig=plt.figure(figsize=(8,8*ratio))
        fig.subplots_adjust(left=0,right=1,bottom=0,top=1)
        ax=fig.add_subplot(111,axisbg=background)
        
        if show_edges:
            for e in self.g.edges(data=True):
                poly_points=[projection(*self.posdict[nd]) for nd in e[2]['poly_line']]
                bbox_check=[min_x<=p[0]<=max_x and min_y<=p[1]<=max_y for p in poly_points]
                if any(bbox_check):
                    path=Path(poly_points)
                    patch = patches.PathPatch(path, facecolor='none', edgecolor=edge_col, lw=edge_width)
                    ax.add_patch(patch)
        
        if show_nodes:
            node_points=[projection(*self.posdict[nd]) for nd in self.g]
            node_points_bbox=[p for p in node_points if min_x<=p[0]<=max_x and min_y<=p[1]<=max_y]
            x,y = zip(*node_points_bbox)
            ax.scatter(x,y,c=node_col,s=node_size,zorder=5)
        
#        ax.set_frame_on(False)
        
        ax.set_xlim(min_x,max_x)
        ax.set_ylim(min_y,max_y)
        
        ax.set_xticks([])
        ax.set_yticks([])
        
        plt.savefig(filename+'.png')
        plt.savefig(filename+'.pdf')
        plt.savefig(filename+'.eps')
        
        plt.close('all')
    
    
    def plot_network_background(self,min_lon,min_lat,max_lon,max_lat,zoom,filename,
                                show_edges=True,show_nodes=False,edge_width=1,
                                node_size=7,edge_col='k',node_col='r'):
        
        sw = Geo.Location(min_lat,min_lon)
        ne = Geo.Location(max_lat,max_lon)
        
        m = mm.mapByExtentZoom(OpenStreetMap.Provider(), sw, ne, zoom)
        
        lower_left=m.locationPoint(sw)
        upper_right=m.locationPoint(ne)
        
        ratio=(lower_left.y-upper_right.y)/(upper_right.x-lower_left.x)
        
        print 'Aspect ratio '+str(ratio)

        fig=plt.figure(figsize=(8,8*ratio))
        fig.subplots_adjust(left=0,right=1,bottom=0,top=1)
        ax=fig.add_subplot(111)
        
        if show_edges:
            for e in self.g.edges(data=True):
                poly_points=[m.locationPoint(Geo.Location(self.posdict[nd][1],self.posdict[nd][0])) for nd in e[2]['poly_line']]
                bbox_check=[lower_left.x<=p.x<=upper_right.x and upper_right.y<=p.y<=lower_left.y for p in poly_points]
                if any(bbox_check):
                    path=Path([(point.x,point.y) for point in poly_points])
                    patch = patches.PathPatch(path, facecolor='none', edgecolor=edge_col, lw=edge_width)
                    ax.add_patch(patch)
        
        if show_nodes:
            node_points=[m.locationPoint(Geo.Location(self.posdict[nd][1],self.posdict[nd][0])) for nd in self.g]
            node_points_bbox=[p for p in node_points if lower_left.x<=p.x<=upper_right.x and upper_right.y<=p.y<=lower_left.y]
            x=[point.x for point in node_points_bbox]
            y=[point.y for point in node_points_bbox]
            ax.scatter(x,y,c=node_col,s=node_size,zorder=5)
        
        ax.set_frame_on(False)
        
        ax.set_xlim(lower_left.x,upper_right.x)
        ax.set_ylim(lower_left.y,upper_right.y)
        
        ax.set_xticks([])
        ax.set_yticks([])
        
        map_image=m.draw()
        
        ax.imshow(map_image)
        
        plt.savefig(filename+'.png')
        plt.savefig(filename+'.pdf')
        plt.savefig(filename+'.eps')
        
        plt.close('all')
    
    


def read_data(filename):
    CurrentHandler=OSMHandler()
    sax.parse(filename,CurrentHandler)
    CurrentData=OSMData(CurrentHandler.nodes,CurrentHandler.ways,CurrentHandler.relations)
    return CurrentData

