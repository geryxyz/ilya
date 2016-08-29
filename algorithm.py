from clustering import *
import subprocess as sp #https://docs.python.org/3.4/library/subprocess.html
import networkx as nx
import community
import re
import os
import statistics
import pdb
import shutil
import re
import glob2
import json

def _prefix_of(name, level=0):
	unified_name = name.replace('.', '/').replace('::', '/')
	match = re.search(r'(?P<prefix>[^(]+)', unified_name)
	prefix = 'unknown'
	if match:
		prefix = match.group('prefix')
	return '/'.join(prefix.split('/')[:(-2 - level)])

def _load_labels(labels_dir):
	labels = {}
	paths = glob2.glob(os.path.join(labels_dir, '**/*.csv'))

	for labels_csv_path in paths:
		with open(labels_csv_path, 'r') as label_file:
			for line in label_file:
				parts = line.strip().split(';')
				labels[parts[0]] = parts[2]

	return labels

def _label_of(name, labels, level=0):
	if name in labels:
		label = labels[name]
		print("Using label '%s' for '%s'" % (label, name))
		return label
	else:
		return _prefix_of(name, level)

def _longest_substr(data):
	substr = ''
	if len(data) == 1:
		return data[0]
	if len(data) > 1 and len(data[0]) > 0:
		for i in range(len(data[0])):
			for j in range(len(data[0])-i+1):
				if j > len(substr) and all(data[0][i:i+j] in x for x in data):
					substr = data[0][i:i+j]
	return substr

def _rawcount(filename):
	buf_size = 32 * 1024 * 1024

	def _makegen(reader):
		b = reader(buf_size)
		while b:
			yield b
			b = reader(buf_size)

	with open(filename, 'rb') as f:
		f_gen = _makegen(f.raw.read)
		return sum(buf.count(b'\n') for buf in f_gen)

class CoverageBasedData(object):
	def __init__(self, path_to_dump, drop_uncovered=False, regenerate_edge_list=True):
		self._soda_dump = path_to_dump
		self._create_edge_list(path_to_dump, regenerate_edge_list=regenerate_edge_list)
		all_names = [datum['name'] for _, datum in self.data.items()]
		self._most_common = _longest_substr(all_names)

	def _create_edge_list(self, matrix_csv_path, regenerate_edge_list=True):
		base_name = os.path.join(os.path.dirname(matrix_csv_path), os.path.splitext(os.path.basename(matrix_csv_path))[0])
		self.edge_list_path = '%s.edges.csv' % base_name
		self.data_mapping_path = '%s.data.csv' % base_name

		if not regenerate_edge_list and os.path.isfile(self.edge_list_path) and os.path.isfile(self.data_mapping_path):
			with open(self.data_mapping_path, 'r') as data_mapping:
				self.data = dict([json.loads(line) for line in data_mapping])
			return

		self.data = {}
		count_lines = _rawcount(matrix_csv_path)

		with open(matrix_csv_path, 'r') as matrix, open(self.edge_list_path, 'w') as edge_list:
			header = next(matrix).strip()
			code_elements = header.split(';')[1:]
			global_node_index = '0'
			code_map = {}
			test_map = {}
			for test_index, line in enumerate(matrix):
				print("converting matrix to edges, done: %.4f" % (test_index / count_lines))
				parts = line.strip().split(';')
				test_name = parts[0]
				for code_index, connection in enumerate(parts[1:]):
					code_name = code_elements[code_index]
					if int(connection) > 0:
						if code_index not in code_map:
							code_map[code_index] = global_node_index
							global_node_index = str(int(global_node_index)+1)
						if test_index not in test_map:
							test_map[test_index] = global_node_index
							global_node_index = str(int(global_node_index)+1)
						current_code_node = code_map[code_index]
						current_test_node = test_map[test_index]
						if current_test_node not in self.data:
							self.data[current_test_node] = {}
						self.data[current_test_node]['name'] = test_name
						self.data[current_test_node]['domain'] = 'test'
						if current_code_node not in self.data:
							self.data[current_code_node] = {}
						self.data[current_code_node]['name'] = code_name
						self.data[current_code_node]['domain'] = 'code'
						edge_list.write('%s %s\n' % (current_code_node, current_test_node))
		with open(self.data_mapping_path, 'w') as data_mapping:
			for entry in self.data.items():
				data_mapping.write('%s\n' % json.dumps(entry))

	def package_based_clustering(self, name, labels_dir=None, level=0, key='declared_cluster'):
		mapping = {}

		if labels_dir:
			labels = _load_labels(labels_dir)

		for node, data in self.data.items():
			name_of_node = data.get('name', 'noname')
			if labels:
				mapping[str(node)] = _label_of(name_of_node, labels, level=level)
			else:
				mapping[str(node)] = _prefix_of(name_of_node, level=level)

		return Clustering(mapping, name, key, self.data)

	def community_based_clustering(self, name, key='community_cluster', regenerate_external_data=False):
		base_name = os.path.join(os.path.dirname(self._soda_dump), os.path.splitext(os.path.basename(self._soda_dump))[0])

		bin_edge_list_path = '%s.edges.bin' % base_name
		if regenerate_external_data or not os.path.isfile(bin_edge_list_path):
			sp.call('convert -i %s -o %s' % (self.edge_list_path, bin_edge_list_path), shell=True)

		tree_path = '%s.tree' % base_name
		if regenerate_external_data or not os.path.isfile(tree_path):
			sp.call('louvain -v -l -1 %s > %s' % (bin_edge_list_path, tree_path), shell=True)

		self.community_map_path = '%s.map.csv' % base_name
		if regenerate_external_data or not os.path.isfile(self.community_map_path):
			sp.call('hierarchy -m %s > %s' % (tree_path, self.community_map_path), shell=True)

		mapping = {}
		with open(self.community_map_path, 'r') as mapping_file:
			for line in mapping_file:
				parts = line.strip().split(' ')
				mapping[parts[0]] = parts[1]

		return Clustering(mapping, name, key, self.data)

	def save(self, name, clusterings=[], similarity_constrain=lambda v: v):
		dir = os.path.join(os.path.dirname(name), '%s-graphs' % os.path.splitext(os.path.basename(name))[0])
		if os.path.isdir(dir):
			shutil.rmtree(dir)
		os.makedirs(dir)
		self.similarity_models = {}
		self.similarity_models['jaccard'] = self._create_similarity_map(dir, clusterings, similarity_name='J', similarity=jaccard_similarity_coefficient, constrain=similarity_constrain)
		self.similarity_models['f-measure'] = self._create_similarity_map(dir, clusterings, similarity_name='F', similarity=f_measuere, constrain=similarity_constrain)
		self.similarity_models['inclusion'] = self._create_similarity_map(dir, clusterings, similarity_name='I', similarity=inclusion_coefficient, constrain=similarity_constrain)

	def _split_names_to_parts(self, name_of_nodes):
		names = [name.replace('.', '/').replace(self._most_common, '') for name in name_of_nodes]
		common = _longest_substr(names)
		names = [n.replace(common, '') for n in names]
		parted = [[pp for pp in [re.sub(r'\W', '', p) for p in re.sub( r'([A-Z]|\W)', r' \1', n).split()] if not (pp == '' or re.search(r'([tT]est|Lorg)', pp))] for n in names]
		return parted

	def _most_common_parts(self, name_of_nodes, count=10):
		names_parts = self._split_names_to_parts(name_of_nodes)
		counts = {}
		for name in names_parts:
			checked = set()
			for part in name:
				if part not in checked and len(part) > 1:
					counts[part] = counts.get(part, 0) + 1
		sorted_counts = [part[0] for part in sorted(counts.items(), key=lambda x: x[1], reverse=True)]
		return sorted_counts[:count]

	def _suggest_name(self, test_names, code_names):
		_test_names = [name.replace('.', '/').replace(self._most_common, '*') for name in test_names]
		_code_names = [name.replace('.', '/').replace(self._most_common, '*') for name in code_names]
		test_suggested_name = _longest_substr(_test_names)
		code_suggested_name = _longest_substr(_code_names)
		code_summary = '\n'.join(chunks_of(' '.join(self._most_common_parts(_code_names)), 40))
		test_summary = '\n'.join(chunks_of(' '.join(self._most_common_parts(_test_names)), 40))
		return 'code "%s"\nalso: %s etc.\ntested by\ntest "%s"\nalso: %s etc.\ncontaining %d codes, %d tests' % (code_suggested_name, code_summary, test_suggested_name, test_summary, len(_code_names), len(_test_names))

	def _create_similarity_map(self, dir, clusterings, similarity_name=None, similarity=lambda a, b: 0, constrain=lambda v: v):
		merged_model = nx.DiGraph()
		global_cluster_index = 0
		for clustering_index, clustering in enumerate(clusterings):
			for cluster, content in clustering.clusters.items():
				code_names = [clustering.name_of(node) for node in content if clustering.domain_of(node) == 'code']
				test_names = [clustering.name_of(node) for node in content if clustering.domain_of(node) == 'test']
				suggested_name = self._suggest_name(test_names=test_names, code_names=code_names)
				merged_model.add_node(global_cluster_index, id=cluster, clustering=clustering.key, node_count=len(content), suggested_name=suggested_name)
				global_cluster_index += 1
		for cluster_i, data_i in merged_model.nodes(data=True):
			for cluster_j, data_j in merged_model.nodes(data=True):
				if data_i['clustering'] != data_j['clustering'] and cluster_i != cluster_j:
					content_i = [c.clusters[str(data_i['id'])] for c in clusterings if c.key == data_i['clustering']][0]
					content_j = [c.clusters[str(data_j['id'])] for c in clusterings if c.key == data_j['clustering']][0]
					similarity_value = similarity(content_i, content_j)
					if constrain(similarity_value):
						merged_model.add_edge(cluster_i, cluster_j, similarity=similarity_value, label='%s = %.2f' % (similarity_name, similarity_value))
		nx.write_graphml(merged_model, os.path.join(dir,'similarity.model_%s.graphml' % similarity_name))
		return merged_model

print("coverage_cluster.algorithm was loaded.")
