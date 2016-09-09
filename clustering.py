import random
import statistics
import json
import re
import pdb
import math
import os
import shutil
import hashlib

def chunks_of(l, n):
	"""Yield successive n-sized chunks from l."""
	for i in range(0, len(l), n):
		yield l[i:i+n]

def hash_it(text):
	return hashlib.sha224(str(text).encode('utf-8')).hexdigest()

def random_cluster_mapping(item_count, cluster_count):
	mapping = {}
	for item in range(item_count):
		mapping[item] = random.randrange(cluster_count)
	return mapping

def change_mapping(base, switch_count):
	count = len(base)
	modified = base.copy()
	for i in range(switch_count):
		x, y = random.randrange(count), random.randrange(count)
		modified[x], modified[y] = modified[y], modified[x]
	return modified

def _mapping_to_clustering(mapping):
	clusters = {}
	for item, cluster in mapping.items():
		if cluster not in clusters:
			clusters[cluster] = set()
		clusters[cluster].add(item)
	return clusters

class Clustering(object):
	def __init__(self, mapping, name, key, data):
		self.data = data
		self.name = name
		self.mapping = mapping
		self.clusters = _mapping_to_clustering(mapping)
		self.base_set = {k for k in mapping}
		self._init_size_metrics()
		self.key = key

	def _init_size_metrics(self):
		self.base_set_size = len(self.base_set)
		self.size_of = {}
		for i, cluster in self.clusters.items():
			self.size_of[i] = len(cluster)

	def name_of(self, node):
		return self.data[node].get('name', 'noname')

	def domain_of(self, node):
		return self.data[node].get('domain', 'unknown')

	def save(self, name):
		with open('%s.clusters.txt' % name, 'w') as clusters_output, open('%s.mapping.txt' % name, 'w') as mapping_output:
			for key in self.clusters:
				clusters_output.write('%s:\n' % key)
				for node in self.clusters[key]:
					name = node
					clusters_output.write('%s\n' % name)
					mapping_output.write('%s; %s\n' % (name, key))
				clusters_output.write('\n')

	def compatible_with(self, other):
		for node in self.base_set:
			if node not in other.base_set:
				pdb.set_trace()
				return False
		return True

	def compare_to(self, other):
		return ClusteringComparator(self, other)

	def clustering_metrics(self, edge_list_path):
		print("Clustering metrics (cluster_id : value)")
		good_edges = dict()
		bad_edges = dict()
		for cluster_id ,y in self.clusters.items():
			good_edges[cluster_id] = 0
			bad_edges[cluster_id] = 0

		with open(edge_list_path, 'r') as edge_list:
			for one_edge in edge_list.readlines():
				from_edge = one_edge.split(" ")[0]
				to_edge = one_edge.split(" ")[1].split("\n")[0]
				for cluster_id, edge_set in self.clusters.items():
					if str(from_edge) in edge_set:
						if str(to_edge) in self.clusters[cluster_id]:
							good_edges[cluster_id] = good_edges[cluster_id] + 1
						else:
							bad_edges[cluster_id] = bad_edges[cluster_id] + 1

		for cluster_id, good_edges_count in good_edges.items():
			sum_edges = good_edges_count + bad_edges[cluster_id]
			metrics_value = good_edges_count / sum_edges
			print("cluster id: "+str(cluster_id)+"\tvalue: "+str(metrics_value))

class ClusteringComparator():
	def __init__(self, clustering_i, clustering_j):
		if not clustering_i.compatible_with(clustering_j):
			raise Exception('trying to compare incompatible clusters')
		self._clustering_i = clustering_i
		self._clustering_j = clustering_j
		self.base_set = clustering_i.base_set | clustering_j.base_set
		self.base_set_size = len(self.base_set)
		self._init_confusion_matrix()
		self._init_same_pairs()

	def _init_confusion_matrix(self):
		self.confusion_matrix = {}
		for i, cluster_i in self._clustering_i.clusters.items():
			self.confusion_matrix[i] = {}
			for j, cluster_j in self._clustering_j.clusters.items():
				self.confusion_matrix[i][j] = len(cluster_i & cluster_j)

	def _init_same_pairs(self):
		#self.same_pair = []
		self.same_pair_count = 0
		self.semisame_ij = []
		self.semisame_ij_count = 0
		self.semisame_ji = []
		self.semisame_ji_count = 0
		#self.unsame_pair = []
		self.unsame_pair_count = 0
		base_list = list(self.base_set)
		i = 0
		ps = pc = 5
		n = sum(x for x in range(self.base_set_size))
		print("base set size = %d\npairs = %d" % (self.base_set_size, n))
		for a, node_a in enumerate(base_list):
			for b, node_b in enumerate(base_list):
				i += 1
				p = int(i/n*100)
				if p > 0 and p % pc == 0:
					print("%3d%% :: same = %d, ij = %d, ji = %d, unsame = %d" % (p, self.same_pair_count, self.semisame_ij_count, self.semisame_ji_count, self.unsame_pair_count))
					pc += ps
				if a == b:
					break
				both_i = self._clustering_i.mapping[node_a] == self._clustering_i.mapping[node_b]
				both_j = self._clustering_j.mapping[node_a] == self._clustering_j.mapping[node_b]
				if both_i and both_j:
					#self.same_pair.append((node_a, node_b))
					self.same_pair_count += 1
				elif both_i and not both_j:
					#self.semisame_ij.append((node_a, node_b))
					self.semisame_ij_count += 1
				elif not both_i and both_j:
					#self.semisame_ji.append((node_a, node_b))
					self.semisame_ji_count += 1
				elif not both_i and not both_j:
					#self.unsame_pair.append((node_a, node_b))
					self.unsame_pair_count += 1
				else:
					raise Exception('impossible same-pair alignment')

		#self.same_pair_count = len(self.same_pair)
		#self.semisame_ij_count = len(self.semisame_ij)
		#self.semisame_ji_count = len(self.semisame_ji)
		#self.unsame_pair_count = len(self.unsame_pair)
		self.count_of_pairs = self.same_pair_count + self.semisame_ij_count + self.semisame_ji_count + self.unsame_pair_count

	def reverse(self):
		return ClusteringComparator(self._clustering_j, self._clustering_i)

	def save(self, name):
		dir = os.path.join(os.path.dirname(name), '%s --- %s' % (self._clustering_i.name, self._clustering_j.name))
		if os.path.isdir(dir):
			shutil.rmtree(dir)
		os.makedirs(dir)
		self._save_confusion_matrix(dir)
		self._save_pair_counts(dir)
		self._save_metrics(dir)
		#self._save_bad_pairs(dir)

	def _save_confusion_matrix(self, dir):
		with open(os.path.join(dir, 'confusion_matrix.csv'), 'w') as matrix:
			for k, line in self.confusion_matrix.items():
				for l, datum in line.items():
					matrix.write('%s;' % datum)
				matrix.write('\n')

	def _save_pair_counts(self, dir):
		with open(os.path.join(dir, 'same_pair_counts.csv'), 'w') as count:
			count.write('same; %d\n' % self.same_pair_count)
			count.write('semi-same (ij); %d\n' % self.semisame_ij_count)
			count.write('semi-same (ji); %d\n' % self.semisame_ji_count)
			count.write('unsame; %d\n' % self.unsame_pair_count)
			count.write('base set size; %d\n' % self.base_set_size)

	def _save_metrics(self, dir):
		with open(os.path.join(dir, 'compare.csv'), 'w') as compare:
			compare.write('Chi Squared coefficient;%f\n' % self.chi_squared_coefficient())
			compare.write('Rand index;%f\n' % self.rand_index())
			compare.write('Fowlkes-Mallows index;%f\n' % self.fowlkes_mallows_index())
			compare.write('Jaccard index;%f\n' % self.jaccard_index())
			compare.write('Mirkin metric;%f\n' % self.mirkin_metric())
			compare.write('F-measure;%f\n' % self.f_measure())

	def _save_bad_pairs(self, dir):
		for index, chunk in enumerate(chunks_of([pair for pair in self.semisame_ij if self._clustering_i.domain_of(pair[0]) != self._clustering_i.domain_of(pair[1])], 100000)):
			with open(os.path.join(dir, 'semisame_%d_%s_%s.txt' % (index, self._clustering_i.key, self._clustering_j.key)), 'w') as diff:
				for pair in chunk:
					diff.write('nodes:    %s ; %s\n' % (self._clustering_i.name_of(pair[0]), self._clustering_i.name_of(pair[1])))
					diff.write('clusters: %s - %s ; %s - %s\n' % (self._clustering_i.mapping[pair[0]], self._clustering_i.mapping[pair[1]], self._clustering_j.mapping[pair[0]], self._clustering_j.mapping[pair[1]]))
					diff.write('hashes:   %s - %s ; %s - %s\n\n' % (hash_it(self._clustering_i.mapping[pair[0]]), hash_it(self._clustering_i.mapping[pair[1]]), hash_it(self._clustering_j.mapping[pair[0]]), hash_it(self._clustering_j.mapping[pair[1]])))
		for index, chunk in enumerate(chunks_of([pair for pair in self.semisame_ji if self._clustering_i.domain_of(pair[0]) != self._clustering_i.domain_of(pair[1])], 100000)):
			with open(os.path.join(dir, 'semisame_%d_%s_%s.txt' % (index, self._clustering_j.key, self._clustering_i.key)), 'w') as diff:
				for pair in chunk:
					diff.write('nodes:    %s ; %s\n' % (self._clustering_i.name_of(pair[0]), self._clustering_i.name_of(pair[1])))
					diff.write('clusters: %s - %s ; %s - %s\n' % (self._clustering_j.mapping[pair[0]], self._clustering_j.mapping[pair[1]], self._clustering_i.mapping[pair[0]], self._clustering_i.mapping[pair[1]]))
					diff.write('hashes:   %s - %s ; %s - %s\n\n' % (hash_it(self._clustering_j.mapping[pair[0]]), hash_it(self._clustering_j.mapping[pair[1]]), hash_it(self._clustering_i.mapping[pair[0]]), hash_it(self._clustering_i.mapping[pair[1]])))

	def dump(self):
		print('[Comparison] %s ---> %s' % (self._clustering_i.name, self._clustering_j.name))
		print(' |  Chi Squared coefficient = %f' % self.chi_squared_coefficient())
		print(' |  Rand index = %f' % self.rand_index())
		print(' |  Fowlkes-Mallows index = %f' % self.fowlkes_mallows_index())
		print(' |  Jaccard index = %f' % self.jaccard_index())
		print(' |  Mirkin metric = %f' % self.mirkin_metric())
		print(' |  F-measure = %f' % self.f_measure())

	def chi_squared_coefficient(self):
		chi = 0
		for i, Ci in self._clustering_i.clusters.items():
			for j, Cj  in self._clustering_j.clusters.items():
				Eij = (len(Ci) * len(Cj)) / self.base_set_size
				chi += ((self.confusion_matrix[i][j] - Eij) ** 2) / Eij
		return chi

	def rand_index(self):
		numerator = 2 * (self.same_pair_count + self.unsame_pair_count)
		nominator = self.base_set_size * (self.base_set_size - 1)
		return numerator / nominator

	def fowlkes_mallows_index(self):
		nominator = math.sqrt((self.same_pair_count + self.semisame_ij_count) * (self.same_pair_count + self.semisame_ij_count))
		return self.same_pair_count / nominator

	def jaccard_index(self):
		nominator = self.same_pair_count + self.semisame_ij_count + self.semisame_ji_count
		return self.same_pair_count / nominator

	def mirkin_metric(self):
		a = sum([len(l) ** 2 for _, l in self._clustering_i.clusters.items()])
		b = sum([len(l) ** 2 for _, l in self._clustering_j.clusters.items()])
		m = 0
		for i in self._clustering_i.clusters:
			for j in self._clustering_j.clusters:
				m += self.confusion_matrix[i][j] ** 2
		return a + b - 2 * m

	def _f_measure(self, i, j):
		pij = self.confusion_matrix[i][j] / self._clustering_j.size_of[j]
		rij = self.confusion_matrix[i][j] / self._clustering_i.size_of[i]
		if pij == 0 and rij == 0:
			return 0
		return (2 * rij * pij) / (rij + pij)

	def f_measure(self):
		a = 0
		for i in self._clustering_i.clusters:
			v = []
			for j in self._clustering_j.clusters:
				v.append(self._clustering_i.size_of[i] * self._f_measure(i, j))
			a += max(v)
		return a / self.base_set_size

def jaccard_similarity_coefficient(a, b):
	return len(a & b) / len(a | b)

def f_measuere(a, b):
	confusion = len(a & b)
	pij = confusion / len(a)
	rij = confusion / len(b)
	if pij == 0 and rij == 0:
		return 0
	return (2 * rij * pij) / (rij + pij)

def inclusion_coefficient(a, b):
	return len(a & b) / len(a)

print("coverage_cluster.clustering was loaded.")
