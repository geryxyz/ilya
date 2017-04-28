import networkx as nx
import pdb
import statistics
import json
import numpy
from scipy.spatial.distance import euclidean, cityblock
from fastdtw import fastdtw
import subprocess as sp #https://docs.python.org/3.4/library/subprocess.html
import copy
import svgwrite
import cairosvg

from clustering import *
from snowflake import *

class NDDClustering(Clustering):
	def save(self, filename):
		super().save(filename)
		with open('%s.vectors.clusters.csv' % filename, 'w') as vectors:
			for key in self.clusters:
				vectors.write("in %s\n" % key)
				ndds = []
				for id in self.clusters[key]:
					ndd = self.data[int(id)].get('vector', [])
					vectors.write('%s;' % self.name_of(int(id)))
					vectors.write(';'.join([str(x) for x in ndd]))
					vectors.write('\n')
					ndds.append(ndd)
				vectors.write('\n')
				draw_animated_circles(ndds, '%s_%s.ndd.gif' % (filename, key.replace('/', '_')))
				draw_blended_circles(ndds, '%s_%s.ndd.gif' % (filename, key.replace('/', '_')))


class NDDDetector(object):
	def __init__(self, graphs, base_clustering, derived_clustering, key):
		self.key = key
		self.base_histograms = self.detect_ndd_vector(base_clustering, graphs)
		self.derived_histograms = self.detect_ndd_vector(derived_clustering, graphs)

	@property
	def histograms(self):
		return dict(self.base_histograms, **self.derived_histograms)

	@property
	def padded_histograms(self):
		_histograms = self.histograms
		max_length = max([len(v) for k, v in _histograms.items()])
		return {k: v + ([0] * (max_length - len(v))) for k, v in _histograms.items()}

	def ndd_vector_of(self, cluster_id, graphs):
		node = None
		for node_id, node_data in graphs['inclusion'].nodes(data=True):
			if node_data['id'] == cluster_id:
				node = node_id
				break

		histogram = {}
		for source, target, edge_data in graphs['inclusion'].out_edges(node, data=True):
			count_of_parts = len(graphs['inclusion'].out_edges(target, data=True))
			histogram[count_of_parts] = histogram.get(count_of_parts, 0) + 1
		for i in range(max(histogram.keys())):
			histogram[i] = histogram.get(i, 0)

		return [v for k, v in sorted(histogram.items(), key=lambda x: x[0])][1:]

	def detect_ndd_vector(self, clustering, graphs):
		histograms = {}
		for node, node_data in graphs['inclusion'].nodes(data=True):
			if node_data['clustering'] == clustering.key:
				histograms[node_data['id']] = self.ndd_vector_of(node_data['id'], graphs)

		return histograms

	def distance_matrix(self, measure):
		print("Measure distances with DTW using %s" % str(measure))
		i = 0
		ps = pc = 5
		n = len(self.histograms)
		distances = {}
		for key_a, a in self.histograms.items():
			i += 1
			p = int(i/n*100)
			if p > 0 and p % pc == 0:
				print("%3d%%" % p)
				pc += ps
			distances[key_a] = {}
			a_array = numpy.array([[i, v] for i, v in enumerate(a)])
			for key_b, b in self.histograms.items():
				b_array= numpy.array([[i, v] for i, v in enumerate(b)])
				distances[key_a][key_b], path = fastdtw(a_array, b_array, dist=measure)
		return distances

	def distance_graph(self, measure):
		graph = nx.DiGraph()
		distances = self.distance_matrix(measure)
		for key_a, a in distances.items():
			for key_b, b in a.items():
				if int(b) > 0:
					graph.add_edge(key_a, key_b, weight=int(b))
		return graph

	def _create_edge_list(self, outputname, measure, regenerate_edge_list=True):
		self.edge_list_path = '%s.ndd-edges.csv' % outputname
		self.data_mapping_path = '%s.ndd-data.csv' % outputname

		distances = self.distance_matrix(measure)
		indexes = {name: i for i, name in enumerate(sorted(distances))}
		self.data = {}

		with open(self.edge_list_path, 'w') as edge_list:
			for key_a, a in distances.items():
				for key_b, b in a.items():
					if b > 0:
						edge_list.write('%d %d %d\n' % (indexes[key_a], indexes[key_b], b))
		_histograms = self.histograms
		with open(self.data_mapping_path, 'w') as data_mapping:
			for name, index in indexes.items():
				datum = {'name': name, 'vector': _histograms[name]}
				data_mapping.write('%s\n' % json.dumps([index, datum]))
				self.data[index] = datum

	def clustering_ndd(self, outputname, measure=cityblock, regenerate_external_data=True):
		self._create_edge_list(outputname, measure)

		bin_edge_list_path = '%s.ndd-edges.bin' % outputname
		weight_path = '%s.ndd-weights.bin' % outputname
		if regenerate_external_data or not os.path.isfile(bin_edge_list_path):
			sp.call('./convert -i %s -o %s -w %s' % (self.edge_list_path, bin_edge_list_path, weight_path), shell=True)

		tree_path = '%s.ndd.tree' % outputname
		if regenerate_external_data or not os.path.isfile(tree_path):
			sp.call('./louvain -v -l -1 %s -w %s > %s' % (bin_edge_list_path, weight_path, tree_path), shell=True)

		self.community_map_path = '%s.ndd-map.csv' % outputname
		if regenerate_external_data or not os.path.isfile(self.community_map_path):
			sp.call('./hierarchy -m %s > %s' % (tree_path, self.community_map_path), shell=True)

		mapping = {}
		with open(self.community_map_path, 'r') as mapping_file:
			for line in mapping_file:
				parts = line.strip().split(' ')
				mapping[parts[0]] = parts[1]

		return NDDClustering(mapping, "NDD of %s" % self.key , self.key, self.data)

	def save(self, outputname, measure=cityblock, scale_factor=100):
		with open('%s.base.ndd-vector.txt' % outputname, 'w') as ndd_vector:
			for cluster, histogram in self.base_histograms.items():
				ndd_vector.write('%s; %s\n' % (cluster, json.dumps(histogram)))
		with open('%s.derived.ndd-vector.txt' % outputname, 'w') as ndd_vector:
			for cluster, histogram in self.derived_histograms.items():
				ndd_vector.write('%s; %s\n' % (cluster, json.dumps(histogram)))
		with open('%s.all.ndd-vector.txt' % outputname, 'w') as ndd_vector:
			for cluster, histogram in self.histograms.items():
				ndd_vector.write('%s; %s\n' % (cluster, json.dumps(histogram)))
		nx.write_graphml(self.distance_graph(measure), '%s.ndd-distances.graphml' % outputname)
		draw_multi_circles(self.histograms.values(), '%s.ndd.gif' % outputname)

	def merge_with(self, *others):
		clone = copy.deepcopy(self)
		clone.key = '%s MERGED WITH %s' % (self.key, ','.join([other.key for other in others]))
		_mark_source = lambda hists: {'%s FROM %s' % (k, self.key): v for k, v in hists.items()}
		own_base_histograms = _mark_source(self.base_histograms)
		own_derived_histograms = _mark_source(self.derived_histograms)
		for other in others:
			clone.base_histograms = dict(own_base_histograms, **_mark_source(other.base_histograms))
			clone.derived_histograms = dict(own_derived_histograms, **_mark_source(other.derived_histograms))
		return clone