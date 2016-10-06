import networkx as nx
import pdb
import statistics
import json

def unirange(start, stop, step):
	r = start
	yield r
	while r <= stop:
		r += step
		yield r

class Sniffer(object):
	def __init__(self, graphs, base_clustering, derived_clustering, test_type, base_conf_limit, derived_conf_limit, resolution=list(unirange(0, 1, .05))):
		self.graphs = graphs
		self.base_clustering = base_clustering
		self.derived_clustering = derived_clustering
		self.test_type = test_type
		self.base_conf_limit = base_conf_limit
		self.derived_conf_limit = derived_conf_limit
		self.detect(base_clustering, derived_clustering, resolution=list(unirange(0, 1, .05)))

	def detect_alter_ego(self, clustering):
		count = 0
		for node, data in self.graphs['jaccard'].nodes(data=True):
			if data['clustering'] == clustering.key:
				out_edges = self.graphs['jaccard'].out_edges(node, data=True)
				if len(out_edges) == 1 and out_edges[0][2]['similarity'] == 1:
					count += 1
		return count

	def detect_clean_cut(self, base_clustering, derived_clustering):
		count = 0
		for node, node_data in self.graphs['inclusion'].nodes(data=True):
			if node_data['clustering'] == base_clustering.key:
				out_edges = self.graphs['inclusion'].out_edges(node, data=True)
				if len(out_edges) > 1 and out_edges[0][2]['similarity'] < 1:
					for source, target, edge_data in self.graphs['inclusion'].in_edges(node, data=True):
						if self.graphs['inclusion'].node[source]['clustering'] == derived_clustering.key:
							if edge_data['similarity'] < 1:
								break
					else:
						count += 1
		return count

	def detect_cut(self, base_clustering, derived_clustering, threshold=1):
		count = 0
		for node, node_data in self.graphs['inclusion'].nodes(data=True):
			if node_data['clustering'] == base_clustering.key:
				out_edges = self.graphs['inclusion'].out_edges(node, data=True)
				if len(out_edges) > 1 and out_edges[0][2]['similarity'] < 1:
					for source, target, edge_data in self.graphs['inclusion'].in_edges(node, data=True):
						if self.graphs['inclusion'].node[source]['clustering'] == derived_clustering.key:
							if edge_data['similarity'] <= threshold:
								count += 1
								break
		return count

	def detect_cut_distribution(self, base_clustering, derived_clustering, thresholds):
		counts = {}
		print("counting cuts by threshold\nthreshold;\tcount")
		for threshold in thresholds:
			counts[threshold] = self.detect_cut(base_clustering, derived_clustering, threshold)
			print("%f;\t%d" % (threshold, counts[threshold]))
		return counts

	def detect_chimera_distribution(self, clustering):
		print("counting chimeras by number of parts")
		counts = {}
		for node, node_data in self.graphs['jaccard'].nodes(data=True):
			if node_data['clustering'] == clustering.key:
				count_of_parts = len(self.graphs['jaccard'].out_edges(node, data=True))
				if count_of_parts > 1:
					counts[count_of_parts] = counts.get(count_of_parts, 0) + 1
		for i in range(max(counts.keys())):
			counts[i] = counts.get(i, 0)
		print("number of parts;\tcount")
		print("\n".join(["%d;\t%d" % (parts, count) for parts, count in counts.items()]))
		return counts

	def chimera_vector_of(self, cluster_id):
		node = None
		for node_id, node_data in self.graphs['jaccard'].nodes(data=True):
			if node_data['id'] == cluster_id:
				node = node_id
				break

		histogram = {}
		for source, target, edge_data in self.graphs['jaccard'].out_edges(node, data=True):
			count_of_parts = len(self.graphs['jaccard'].out_edges(target, data=True))
			histogram[count_of_parts] = histogram.get(count_of_parts, 0) + 1
		for i in range(max(histogram.keys())):
			histogram[i] = histogram.get(i, 0)

		return [v for k, v in sorted(histogram.items(), key=lambda x: x[0])][1:]

	def detect_chimera_vector(self, clustering):
		histograms = {}
		for node, node_data in self.graphs['jaccard'].nodes(data=True):
			if node_data['clustering'] == clustering.key:
				histograms[node_data['id']] = self.chimera_vector_of(node_data['id'])

		return histograms

	def check_chimera_vector(self, vector):
		def check_tail(vector):
			for i in vector[1:]:
				if i > 0:
					return '+'
			return '-'

		tail = check_tail(vector)

		if tail == '+':
			return '+'
		elif tail == '-':
			if vector[0] > 1:
				return '-'
			elif vector[0] == 1:
				return '1'
			else:
				raise Exception("Unexpected standalone cluster");
		else:
			return ' '

	def check_cluster(self, cluster_id):
		def check_p(cluster='global'):
			c = self.base_clustering.get_confidence(cluster)
			return c > self.base_conf_limit

		def check_c(cluster='global'):
			c = self.derived_clustering.get_confidence(cluster)
			return c > self.derived_conf_limit

		node = None
		data = None

		for node_id, node_data in self.graphs['jaccard'].nodes(data=True):
			if node_data['id'] == cluster_id:
				node = node_id
				data = node_data
				break

		if node is None or data is None:
			raise Exception("Cluster (%s) cannot be found in the graph" % cluster_id)

		vector = self.chimera_vector_of(cluster_id)
		rule_vector = self.check_chimera_vector(vector)

		if self.test_type == 'unit':
			if rule_vector == '1':
				return (False, rule_vector)
			else:
				if data['clustering'] == self.base_clustering.key: # P cluster
					if rule_vector == '-':
						if check_p():
							if check_c(): # TODO check neighbours separately
								return (True, rule_vector)
							else:
								pass
						else:
							if check_c(): # TODO check neighbours separately
								return (True, rule_vector)
							else:
								pass
					elif rule_vector == '+':
						if check_p():
							if check_c(): # TODO check neighbours separately
								return (True, rule_vector)
							else:
								return (True, rule_vector)
						else:
							if check_c(): # TODO check neighbours separately
								return (True, rule_vector)
							else:
								pass
				elif data['clustering'] == self.derived_clustering.key: # C cluster
					if rule_vector == '-':
						if check_c():
							if check_p(): # TODO check neighbours separately
								return (True, rule_vector)
							else:
								pass
						else:
							if check_p(): # TODO check neighbours separately
								return (True, rule_vector)
							else:
								pass
					elif rule_vector == '+':
						if check_c():
							if check_p(): # TODO check neighbours separately
								return (True, rule_vector)
							else:
								return (True, rule_vector)
						else:
							if check_p(): # TODO check neighbours separately
								return (True, rule_vector)
							else:
								pass
				else:
					raise Exception("Unexpected clustering key (%s)" % data['clustering'])
		elif self.test_type == 'integration':
			if rule_vector == '1':
				pass
			else:
				if data['clustering'] == self.base_clustering.key:  # P cluster
					if rule_vector == '-':
						if check_p():
							if check_c():  # TODO check neighbours separately
								return (True, rule_vector)
							else:
								pass
						else:
							if check_c():  # TODO check neighbours separately
								return (True, rule_vector)
							else:
								pass
					elif rule_vector == '+':
						if check_p():
							if check_c():  # TODO check neighbours separately
								return (False, rule_vector)
							else:
								pass
						else:
							if check_c():  # TODO check neighbours separately
								pass
							else:
								pass
				elif data['clustering'] == self.derived_clustering.key:  # C cluster
					if rule_vector == '-':
						if check_c():
							if check_p():  # TODO check neighbours separately
								return (False, rule_vector)
							else:
								pass
						else:
							if check_p():  # TODO check neighbours separately
								pass
							else:
								pass
					elif rule_vector == '+':
						if check_c():
							if check_p():  # TODO check neighbours separately
								pass
							else:
								pass
						else:
							if check_p():  # TODO check neighbours separately
								pass
							else:
								pass
				else:
					raise Exception("Unexpected clustering key (%s)" % data['clustering'])
		else:
			raise Exception("Unexpected test type (%s)" % self.test_type)

		return None

	def detect_smells(self):
		smells = []

		for node_id, node_data in self.graphs['jaccard'].nodes(data=True):
			cluster_id = node_data['id']
			result = self.check_cluster(cluster_id)

			if not (result is None):
				smells.append((cluster_id,) + (result))

		return smells

	def detect(self, base_clustering, derived_clustering, resolution=list(unirange(0, 1, .05))):
		self.alter_ego_count = self.detect_alter_ego(base_clustering)
		print("%d alter ego was detected" % self.alter_ego_count)
		self.clean_cut_count = self.detect_clean_cut(base_clustering, derived_clustering)
		print("%d clean cut was detected" % self.clean_cut_count)
		self.cut_distribution = self.detect_cut_distribution(base_clustering, derived_clustering, resolution)
		self.chimera_distribution = self.detect_chimera_distribution(derived_clustering)
		self.base_histograms = self.detect_chimera_vector(base_clustering)
		self.derived_histograms = self.detect_chimera_vector(derived_clustering)
		self.smells = self.detect_smells()
		print("%d smells were detected" % len(self.smells))

	def save(self, outputname):
		with open('%s.smells-count.csv' % outputname, 'w') as smells_count:
			smells_count.write("alter egos; %d\n" % self.alter_ego_count)
			smells_count.write("clean cuts; %d\n" % self.clean_cut_count)
			smells_count.write("threshold; cuts\n")
			smells_count.write("\n".join(['%f; %d' % (thr, count) for thr, count in sorted(self.cut_distribution.items())]))
			smells_count.write("\n")
			smells_count.write("parts; chimeras\n")
			smells_count.write("\n".join(['%f; %d' % (p, count) for p, count in sorted(self.chimera_distribution.items())]))
			smells_count.write("\n")
			smells_count.write("cluster; is_smell; pattern\n")
			smells_count.write("\n".join("%s; %s" % s for s in self.smells))
		with open('%s.base.chimeras-vector.txt' % outputname, 'w') as chimeras_vector:
			for cluster, histogram in self.base_histograms.items():
				chimeras_vector.write('%s; %s\n' % (cluster, json.dumps(histogram)))
		with open('%s.derived.chimeras-vector.txt' % outputname, 'w') as chimeras_vector:
			for cluster, histogram in self.derived_histograms.items():
				chimeras_vector.write('%s; %s\n' % (cluster, json.dumps(histogram)))

print("coverage_cluster.smell was loaded.")
