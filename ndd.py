import networkx as nx
import pdb
import statistics
import json
import numpy
from scipy.spatial.distance import euclidean, cityblock
from fastdtw import fastdtw
import subprocess as sp #https://docs.python.org/3.4/library/subprocess.html

from clustering import *

class NDDClustering(Clustering):
	def save(self, filename):
		super().save(filename)
		with open('%s.vectors.clusters.csv' % filename, 'w') as vectors:
			for key in self.clusters:
				vectors.write("in %s\n" % key)
				for id in self.clusters[key]:
					vectors.write('%s;' % self.name_of(int(id)))
					vectors.write(';'.join([str(x) for x in self.data[int(id)].get('vector', [])]))
					vectors.write('\n')
				vectors.write('\n')


class NDDDetector(object):
	def __init__(self, graphs, base_clustering, derived_clustering):
		self.graphs = graphs
		self.base_histograms = self.detect_ndd_vector(base_clustering)
		self.derived_histograms = self.detect_ndd_vector(derived_clustering)

	@property
	def histograms(self):
		return dict(self.base_histograms, **self.derived_histograms)

	@property
	def padded_histograms(self):
		_histograms = self.histograms
		max_length = max([len(v) for k, v in _histograms.items()])
		return {k: v + ([0] * (max_length - len(v))) for k, v in _histograms.items()}

	def ndd_vector_of(self, cluster_id):
		node = None
		for node_id, node_data in self.graphs['inclusion'].nodes(data=True):
			if node_data['id'] == cluster_id:
				node = node_id
				break

		histogram = {}
		for source, target, edge_data in self.graphs['inclusion'].out_edges(node, data=True):
			count_of_parts = len(self.graphs['inclusion'].out_edges(target, data=True))
			histogram[count_of_parts] = histogram.get(count_of_parts, 0) + 1
		for i in range(max(histogram.keys())):
			histogram[i] = histogram.get(i, 0)

		return [v for k, v in sorted(histogram.items(), key=lambda x: x[0])][1:]

	def detect_ndd_vector(self, clustering):
		histograms = {}
		for node, node_data in self.graphs['inclusion'].nodes(data=True):
			if node_data['clustering'] == clustering.key:
				histograms[node_data['id']] = self.ndd_vector_of(node_data['id'])

		return histograms

	@property
	def distance_matrix(self):
		distances = {}
		for key_a, a in self.histograms.items():
			distances[key_a] = {}
			a_array = numpy.array([[i, v] for i, v in enumerate(a)])
			for key_b, b in self.histograms.items():
				b_array= numpy.array([[i, v] for i, v in enumerate(b)])
				distances[key_a][key_b], path = fastdtw(a_array, b_array, dist=cityblock)
		return distances

	@property
	def distance_graph(self):
		graph = nx.DiGraph()
		distances = self.distance_matrix
		for key_a, a in distances.items():
			for key_b, b in a.items():
				if int(b) > 0:
					graph.add_edge(key_a, key_b, weight=int(b))
		return graph

	def _create_edge_list(self, outputname, regenerate_edge_list=True):
		self.edge_list_path = '%s.ndd-edges.csv' % outputname
		self.data_mapping_path = '%s.ndd-data.csv' % outputname

		distances = self.distance_matrix
		indexes = {}
		self.data = {}

		last_index = 0
		with open(self.edge_list_path, 'w') as edge_list:
			for key_a, a in distances.items():
				if key_a not in indexes:
					indexes[key_a] = last_index
					last_index += 1
				for key_b, b in a.items():
					if key_b not in indexes:
						indexes[key_b] = last_index
						last_index += 1
					if b > 0:
						edge_list.write('%d %d %d\n' % (indexes[key_a], indexes[key_b], b))
		_histograms = self.histograms
		with open(self.data_mapping_path, 'w') as data_mapping:
			for name, index in indexes.items():
				datum = {'name': name, 'vector': _histograms[name]}
				data_mapping.write('%s\n' % json.dumps([index, datum]))
				self.data[index] = datum

	def clustering_ndd(self, outputname, regenerate_external_data=True):
		self._create_edge_list(outputname)

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

		return NDDClustering(mapping, "NDD-vectors", "ndd", self.data)

	def save(self, outputname):
		with open('%s.base.ndd-vector.txt' % outputname, 'w') as ndd_vector:
			for cluster, histogram in self.base_histograms.items():
				ndd_vector.write('%s; %s\n' % (cluster, json.dumps(histogram)))
		with open('%s.derived.ndd-vector.txt' % outputname, 'w') as ndd_vector:
			for cluster, histogram in self.derived_histograms.items():
				ndd_vector.write('%s; %s\n' % (cluster, json.dumps(histogram)))
		with open('%s.all.ndd-vector.txt' % outputname, 'w') as ndd_vector:
			for cluster, histogram in self.histograms.items():
				ndd_vector.write('%s; %s\n' % (cluster, json.dumps(histogram)))
		nx.write_graphml(self.distance_graph, '%s.ndd-distances.graphml' % outputname)