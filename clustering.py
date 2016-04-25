import random
import statistics
import json
import re
import pdb
import math

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
	def __init__(self, mapping, graph=None):
		self.mapping = mapping
		self.clusters = _mapping_to_clustering(mapping)
		self.base_set = {k for k in mapping}
		self._graph = graph
		self._init_size_metrics()

	def _init_size_metrics(self):
		self.base_set_size = len(self.base_set)
		self.size_of = {}
		for i, cluster in self.clusters.items():
			self.size_of[i] = len(cluster)

	def save(self, name, filter='.*'):
		with open('%s.clusters.txt' % name, 'w') as clusters_output, open('%s.mapping.txt' % name, 'w') as mapping_output:
			for key in self.clusters:
				clusters_output.write('%s:\n' % key)
				for node in self.clusters[key]:
					name = node
					if self._graph:
						name = json.dumps({k: v for k, v in self._graph.node[node].items() if re.search(filter, k)})
					clusters_output.write('%s\n' % name)
					mapping_output.write('%s; %s\n' % (name, key))
				clusters_output.write('\n')

	def compatible_with(self, other):
		for node in self.base_set:
			if node not in other.base_set:
				return False
		return True

	def compare_to(self, other):
		return ClusteringComperator(self, other)

class ClusteringComperator():
	def __init__(self, clustering_i, clustering_j):
		if not clustering_i.compatible_with(clustering_j):
			raise Exception('tring to compare incompatible clusters')
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
		self.same_pair_count = 0
		self.semisame_ij_count = 0
		self.semisame_ji_count = 0
		self.unsame_pair_count = 0
		base_list = list(self.base_set)
		for a, node_a in enumerate(base_list):
			for b, node_b in enumerate(base_list):
				if a == b:
					break
				both_i = self._clustering_i.mapping[node_a] == self._clustering_i.mapping[node_b]
				both_j = self._clustering_j.mapping[node_a] == self._clustering_j.mapping[node_b]
				if both_i and both_j:
					self.same_pair_count += 1
				elif both_i and not both_j:
					self.semisame_ij_count += 1
				elif not both_i and both_j:
					self.semisame_ji_count += 1
				elif not both_i and not both_j:
					self.unsame_pair_count += 1
				else:
					raise Exception('impossible same-pair alignment')
		self.count_of_pairs = self.same_pair_count + self.semisame_ij_count + self.semisame_ji_count + self.unsame_pair_count

	def save(self, name):
		with open('%s.confusion_matrix.csv' % name, 'w') as matrix:
			for k, line in self.confusion_matrix.items():
				for l, datum in line.items():
					matrix.write('%s;' % datum)
				matrix.write('\n')
		with open('%s.same_pair_counts.csv' % name, 'w') as count:
			count.write('same; %d\n' % self.same_pair_count)
			count.write('semi-same (ij); %d\n' % self.semisame_ij_count)
			count.write('semi-same (ji); %d\n' % self.semisame_ji_count)
			count.write('unsame; %d\n' % self.unsame_pair_count)
			count.write('base set size; %d\n' % self.base_set_size)

	def dump(self):
		print('comperation of clusterings')
		print(' | Rand index = %f' % self.rand_index())
		print(' | Fowlkes–Mallows index = %f' % self.fowlkes_mallows_index())
		print(' | Jaccard index = %f' % self.jaccard_index())

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

print("coverage_cluster.clustering was loaded.")