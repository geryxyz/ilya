import networkx as nx
import pdb
import statistics
import json
import numpy
from scipy.spatial.distance import euclidean, cityblock
from fastdtw import fastdtw
import subprocess as sp #https://docs.python.org/3.4/library/subprocess.html
import copy
import os
import re

from clustering import *
from snowflake import *

def vector_avg(vectors):
	sums = [0] * max([len(v) for v in vectors])
	for vector in vectors:
		for i, v in enumerate(vector):
			sums[i] += v
	count = len(vectors)
	return [s/count for s in sums]

def shorten(vector):
	short = []
	count = 1
	prev = None
	for value in vector:
		if prev != None:
			if prev == value:
				count += 1
			else:
				short.append((prev, count))
				count = 1
		prev = value
	short.append((prev, count))
	return short

def short_text(vector):
	pre_text = []
	for value, count in shorten(vector):
		if count > 1:
			pre_text.append('%.2f{%d}' % (value, count))
		else:
			pre_text.append(str(value))
	return ';'.join(pre_text)

class NDDClustering(Clustering):
	def __init__(self, mapping, name, key, data, represent=vector_avg):
		super().__init__(mapping, name, key, data)
		self.ranks = {}
		self.representatives = {}
		for cluster_id, cluster in self.clusters.items():
			vectors = []
			for id in cluster:
				vectors.append(self.data[int(id)].get('vector', []))
			self.representatives[cluster_id] = represent(vectors)
		print("Ranking...\n")
		for i, (cluster_id, representative) in enumerate(sorted(self.representatives.items(), key=lambda v: list(reversed(v[1])))):
			print("[%3d] %s" % (i, '\t'.join(map(str, representative))))
			self.ranks[cluster_id] = i

	def compensate_count(self, representative):
		as_text = ';'.join(map(str, representative))
		is_fan = re.match(r'^(0.0;)+[1-9]+\.[0-9]+$', as_text)
		if (is_fan):
			width = len(representative)
			print("(%s) is a fan with %d" % (short_text(representative), width))
			correction = (width - 1) * representative[-1]
			print("correction is %d" % correction)
			return correction
		return 0

	def histogram(self):
		counts = {}
		for cluster_id, cluster in self.clusters.items():
			count = len(cluster)
			counts[cluster_id] = {}
			counts[cluster_id]['total'] = count
			counts[cluster_id]['correction'] = self.compensate_count(self.representatives[cluster_id])
		return counts

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
				if not os.path.isdir('%s_ani' % filename):
					os.makedirs('%s_ani' % filename)
				draw_animated_circles(ndds, '%s_ani/%s.ndd.gif' % (filename, key.replace('/', '_')))
				#draw_blended_circles(ndds, '%s_%s.ndd.mix.png' % (filename, key.replace('/', '_')))
				if not os.path.isdir('%s_layer' % filename):
					os.makedirs('%s_layer' % filename)
				draw_layed_circles(ndds, '%s_layer/%s.ndd.png' % (filename, key.replace('/', '_')))
		with open('%s.counts.clusters.csv' % filename, 'w') as counts:
			for cluster_id, count in self.histogram().items():
				counts.write("[%s],%d,%d\n" % (short_text(self.representatives[cluster_id]), count['total'], count['correction']))

def vector_idintity(ndd_a, ndd_b):
	if len(ndd_a) != len(ndd_b):
		return 0
	for a, b in map(lambda a, b: (a, b), ndd_a, ndd_b):
		if a != b:
			return 0
	return 1

class NDDDetector(object):
	def __init__(self, graphs, base_clustering, derived_clustering, key, similarity_measure=vector_idintity):
		self.key = key
		self.base_histograms, self.base_curves = self.detect_ndd_vector(base_clustering, graphs)
		self.derived_histograms, self.derived_curves = self.detect_ndd_vector(derived_clustering, graphs)
		self.similarity_measure = similarity_measure

	@property
	def histograms(self):
		return dict(self.base_histograms, **self.derived_histograms)

	@property
	def curves(self):
		return dict(self.base_curves, **self.derived_curves)

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

		self.curve_props = ['alpha', 'count', 'mean_bethas', 'stddev_bethas']
		G_data = []
		histogram = {}
		for source, target, edge_data in graphs['inclusion'].out_edges(node, data=True):
			alpha = edge_data['similarity']
			bethas = [d['similarity'] for s, t, d in graphs['inclusion'].out_edges(target, data=True)]
			count_of_parts = len(graphs['inclusion'].out_edges(target, data=True))
			histogram[count_of_parts] = histogram.get(count_of_parts, 0) + 1
			G_data.append({'alpha': alpha, 'count': count_of_parts, 'mean_bethas': numpy.mean(bethas), 'stddev_bethas': numpy.std(bethas)})
		for i in range(max(histogram.keys())):
			histogram[i] = histogram.get(i, 0)
		
		return [v for k, v in sorted(histogram.items(), key=lambda x: x[0])][1:], G_data

	def detect_ndd_vector(self, clustering, graphs):
		histograms = {}
		curves = {}
		for node, node_data in graphs['inclusion'].nodes(data=True):
			if node_data['clustering'] == clustering.key:
				histograms[node_data['id']], curves[node_data['id']] = self.ndd_vector_of(node_data['id'], graphs)
		return histograms, curves

	def distance_matrix(self):
		print("Measure distances with %s" % str(self.similarity_measure))
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
			for key_b, b in self.histograms.items():
				distances[key_a][key_b] = self.similarity_measure(a, b)
				#a_array = numpy.array([[i, v] for i, v in enumerate(a)])
				#b_array= numpy.array([[i, v] for i, v in enumerate(b)])
				#distances[key_a][key_b], path = fastdtw(a_array, b_array, dist=measure)
		return distances

	def distance_graph(self):
		graph = nx.DiGraph()
		distances = self.distance_matrix()
		for key_a, a in distances.items():
			for key_b, b in a.items():
				if int(b) > 0:
					graph.add_edge(key_a, key_b, weight=int(b))
		return graph

	def _create_edge_list(self, outputname, regenerate_edge_list=True):
		self.edge_list_path = '%s.ndd-edges.csv' % outputname
		self.data_mapping_path = '%s.ndd-data.csv' % outputname

		distances = self.distance_matrix()
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

		return NDDClustering(mapping, "NDD of %s" % self.key , self.key, self.data)

	def save(self, outputname, scale_factor=100):
		with open('%s.base.ndd-vector.txt' % outputname, 'w') as ndd_vector:
			for cluster, histogram in self.base_histograms.items():
				ndd_vector.write('%s; %s\n' % (cluster, json.dumps(histogram)))
		with open('%s.base.ndd-curve.txt' % outputname, 'w') as ndd_curve:
			ndd_curve.write("id;%s\n" % ";".join(self.curve_props))
			for cluster, curve in self.base_curves.items():
				for props in curve:
					ndd_curve.write('%s; %s\n' % (cluster, ';'.join([str(props[prop]) for prop in self.curve_props])))
		with open('%s.derived.ndd-vector.txt' % outputname, 'w') as ndd_vector:
			for cluster, histogram in self.derived_histograms.items():
				ndd_vector.write('%s; %s\n' % (cluster, json.dumps(histogram)))
		with open('%s.derived.ndd-curve.txt' % outputname, 'w') as ndd_curve:
			ndd_curve.write("id;%s\n" % ";".join(self.curve_props))
			for cluster, curve in self.derived_curves.items():
				for props in curve:
					ndd_curve.write('%s; %s\n' % (cluster, ';'.join([str(props[prop]) for prop in self.curve_props])))
		with open('%s.all.ndd-vector.txt' % outputname, 'w') as ndd_vector:
			for cluster, histogram in self.histograms.items():
				ndd_vector.write('%s; %s\n' % (cluster, json.dumps(histogram)))
		with open('%s.all.ndd-curve.txt' % outputname, 'w') as ndd_curve:
			ndd_curve.write("id;%s\n" % ";".join(self.curve_props))
			for cluster, curve in self.curves.items():
				for props in curve:
					ndd_curve.write('%s; %s\n' % (cluster, ';'.join([str(props[prop]) for prop in self.curve_props])))
		nx.write_graphml(self.distance_graph(), '%s.ndd-distances.graphml' % outputname)
		draw_animated_circles(self.histograms.values(), '%s.ndd.ani.gif' % outputname)
		#draw_blended_circles(self.histograms.values(), '%s.ndd.mix.png' % outputname)
		draw_layed_circles(self.histograms.values(), '%s.ndd.layer.png' % outputname)

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