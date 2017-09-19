import collections
import hashlib
import math
import os
import pdb
import random
import shutil


Result = collections.namedtuple('Result', 'cluster '
                                          'tests_in_cluster '
                                          'tests_in_cluster_nm '
                                          'methods_in_cluster '
                                          'called_methods '
                                          'called_methods_nm '
                                          'called_methods_in_cluster '
                                          'confidence')


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
		self.confidence = None

	def _init_size_metrics(self):
		self.base_set_size = len(self.base_set)
		self.size_of = {}
		for i, cluster in self.clusters.items():
			self.size_of[i] = len(cluster)

	def name_of(self, node):
		return self.data[node].get('name', 'noname')

	def domain_of(self, node):
		return self.data[node].get('domain', 'unknown')

	def save(self, filename):
		with open('%s.clusters.txt' % filename, 'w') as clusters_output, open('%s.mapping.txt' % filename, 'w') as mapping_output:
			for key in self.clusters:
				clusters_output.write('%s:\n' % key)
				for node in self.clusters[key]:
					name = node
					clusters_output.write('%s\n' % name)
					mapping_output.write('%s; %s\n' % (name, key))
				clusters_output.write('\n')

		if self.confidence:
			with open('%s.confidence.csv' % filename, 'w') as confidence_output:
				confidence_output.write("Cluster;Confidence\n")
				for cluster_id, confidence in self.confidence.items():
					confidence_output.write("%s;%f\n" % (cluster_id, confidence))

	def compatible_with(self, other):
		for node in self.base_set:
			if node not in other.base_set:
				pdb.set_trace()
				return False
		return True

	def compare_to(self, other):
		return ClusteringComparator(self, other)

	def calculate_c_confidence(self, edge_list_path):
		if self.key != 'community_cluster':
			raise Exception("Trying to calculate C-confidence on a not community-based clustering")

		self.confidence = dict()
		good_edges = {k: 0 for k in self.clusters.keys()}
		bad_edges = {k: 0 for k in self.clusters.keys()}

		with open(edge_list_path, 'r') as edge_list_file:
			for line in edge_list_file:
				parts = line.strip().split(' ')
				assert len(parts) == 2

				from_edge = parts[0]
				to_edge = parts[1]

				for cluster_id, edge_set in self.clusters.items():
					if from_edge in edge_set:
						if to_edge in self.clusters[cluster_id]:
							good_edges[cluster_id] = good_edges.get(cluster_id, 0) + 1
							good_edges['global'] = good_edges.get('global', 0) + 1
						else:
							bad_edges[cluster_id] = bad_edges.get(cluster_id, 0) + 1
							bad_edges['global'] = bad_edges.get('global', 0) + 1

		for cluster_id, num_good_edges in good_edges.items():
			num_all_edges = num_good_edges + bad_edges[cluster_id]
			confidence = num_good_edges / num_all_edges if num_all_edges > 0 else 0
			self.confidence[cluster_id] = confidence

	def calculate_p_confidence(self, direct_calls_path):
		if self.key != 'declared_cluster':
			raise Exception("Trying to calculate P-confidence on a not package-based clustering")

		methods = set([item['name'] for _, item in self.data.items() if item['domain'] == 'code'])

		direct_calls = dict()

		with open(direct_calls_path, 'r') as direct_calls_file:
			for line in direct_calls_file:
				parts = line.strip().split(';')
				assert len(parts) == 2

				test = parts[0]
				method = parts[1]

				if not test in direct_calls:
					direct_calls[test] = set()

				direct_calls[test].add(method)

		results = list()

		for cluster, members in self.clusters.items():
			tests_in_cluster = set([self.data[m]['name'] for m in members if self.data[m]['domain'] == 'test'])
			methods_in_cluster = set([self.data[m]['name'] for m in members if self.data[m]['domain'] == 'code'])

			called_methods = set()
			tests_not_matched = set()

			for test in tests_in_cluster:
				if test in direct_calls:
					called_methods |= direct_calls[test]
				else:
					tests_not_matched.add(test)

			matched_called_methods = called_methods & methods
			called_in_cluster = matched_called_methods & methods_in_cluster

			n = len(called_in_cluster)
			m = len(matched_called_methods)
			c = n / m if m > 0 else 0

			r = Result(
				cluster=cluster,
				tests_in_cluster=len(tests_in_cluster),
				tests_in_cluster_nm=len(tests_not_matched),
				methods_in_cluster=len(methods_in_cluster),
				called_methods=len(called_methods),
				called_methods_nm=len(called_methods) - m,
				called_methods_in_cluster=n,
				confidence=c
			)
			results.append(r)

		gn = sum([r.called_methods_in_cluster for r in results])
		gm = sum([r.called_methods for r in results]) - sum([r.called_methods_nm for r in results])
		gc = gn / gm if gm > 0 else 0

		global_result = Result(
			cluster='global',
			tests_in_cluster=sum([r.tests_in_cluster for r in results]),
			tests_in_cluster_nm=sum([r.tests_in_cluster_nm for r in results]),
			methods_in_cluster=sum([r.methods_in_cluster for r in results]),
			called_methods=sum([r.called_methods for r in results]),
			called_methods_nm=sum([r.called_methods_nm for r in results]),
			called_methods_in_cluster=gn,
			confidence=gc
		)

		results.append(global_result)

		self.confidence = dict()
		for r in results:
			self.confidence[r.cluster] = r.confidence

	def get_confidence(self, cluster):
		if self.confidence:
			return self.confidence.get(cluster, 0)
		else:
			return 0


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
