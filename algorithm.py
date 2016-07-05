from clustering import *
import networkx as nx
import community
import re
import os
import statistics
import pdb
import shutil
import re

def _prefix_of(name, level=0):
	unified_name = name.replace('.', '/')
	match = re.search(r'(?P<prefix>[^(]+)', unified_name)
	prefix = 'unknown'
	if match:
		prefix = match.group('prefix')
	return '/'.join(prefix.split('/')[:(-2 - level)])

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

class CoverageBasedData(object):
	def __init__(self, path_to_dump, drop_uncovered=False):
		self._soda_dump = path_to_dump
		self.graph = nx.Graph()
		self._init_graph(path_to_dump, drop_uncovered=drop_uncovered)

	def _init_graph(self, file_path, drop_uncovered=False):
		with open(file_path, 'r') as matrix:
			header = next(matrix).strip()
			code_elements = header.split(';')[1:]
			for test_index, line in enumerate(matrix):
				parts = line.strip().split(';')
				test_name = parts[0]
				for code_index, connection in enumerate(parts[1:]):
					code_name = code_elements[code_index]
					test_node = test_index + len(code_elements)
					code_node = code_index
					self.graph.add_node(test_node, domain='test', name=test_name)
					self.graph.add_node(code_node, domain='code', name=code_name)
					if int(connection) > 0:
						self.graph.add_edge(code_node, test_node, type='tested by')
		if drop_uncovered:
			drop_count = {'test': 0, 'code': 0}
			for node in self.graph.nodes():
				if not nx.edges(self.graph, node):
					drop_count[self.graph.node[node]['domain']] += 1
					self.graph.remove_node(node)
			print("dropping %d uncovered code elements and %d useless tests" % (drop_count['code'], drop_count['test']))
		names = [data['name'].replace('.', '/') for node, data in self.graph.nodes(data=True)]
		self._most_common = _longest_substr([name for name in names if not name.startswith('/')])
		print("%d node was loaded" % len(self.graph.nodes()))

	def package_based_clustering(self, name, level=0, key='declared_cluster'):
		mapping = {}
		for node in self.graph.node:
			prefix = _prefix_of(self.graph.node[node]['name'], level=level)
			mapping[node] = prefix
			self.graph.node[node][key] = prefix
		return Clustering(mapping, name, key, self.graph)

	def community_based_clustering(self, name, key='community_cluster'):
		mapping = community.best_partition(self.graph)
		for node, community_name in mapping.items():
			self.graph.node[node][key] = community_name
		return Clustering(mapping, name, key, self.graph)

	def save(self, name, clusterings=[], similarity_depth=None):
		dir = os.path.join(os.path.dirname(name), '%s-graphs' % os.path.splitext(os.path.basename(name))[0])
		if os.path.isdir(dir):
			shutil.rmtree(dir)
		os.makedirs(dir)
		nx.write_graphml(self.graph, os.path.join(dir, 'whole.graphml'))
		self._save_components(dir)
		self._save_blockmodels(dir, clusterings)
		self.block_models = {}
		self.block_models['jaccard'] = self._save_merged_model(dir, clusterings, similarity_name='jaccard', similarity=jaccard_similarity_coefficient, similarity_depth=similarity_depth)
		self.block_models['f-measure'] = self._save_merged_model(dir, clusterings, similarity_name='f-measure', similarity=f_measuere, similarity_depth=similarity_depth)
		self.block_models['snail'] = self._save_merged_model(dir, clusterings, similarity_name='snail', similarity=snail_coefficient, similarity_depth=similarity_depth)
		self.similarity_models = {}
		self.similarity_models['jaccard'] = self._save_merged_model(dir, clusterings, similarity_name='jaccard', similarity=jaccard_similarity_coefficient, drop_inter_cluster_edges=True, similarity_depth=similarity_depth)
		self.similarity_models['f-measure'] = self._save_merged_model(dir, clusterings, similarity_name='f-measure', similarity=f_measuere, drop_inter_cluster_edges=True, similarity_depth=similarity_depth)
		self.similarity_models['snail'] = self._save_merged_model(dir, clusterings, similarity_name='snail', similarity=snail_coefficient, drop_inter_cluster_edges=True, similarity_depth=similarity_depth)

	def _save_components(self, dir):
		comps = list(nx.connected_component_subgraphs(self.graph))
		print("%d connected component subgraphs was detected" % len(comps))
		for i, comp in enumerate(comps):
			nx.write_graphml(comp, os.path.join(dir, 'connected-component-%d.graphml' % i))

	def _split_names_to_parts(self, sub_graph, domain):
		names = [data['name'].replace('.', '/').replace(self._most_common, '') for node, data in sub_graph.nodes(data=True) if data['domain'] == domain]
		common = _longest_substr(names)
		names = [n.replace(common, '') for n in names]
		parted = [[pp for pp in [re.sub(r'\W', '', p) for p in re.sub( r'([A-Z]|\W)', r' \1', n).split()] if not (pp == '' or re.search(r'([tT]est|Lorg)', pp))] for n in names]
		return parted

	def _most_common_parts(self, sub_graph, domain, count=10):
		names_parts = self._split_names_to_parts(sub_graph, domain)
		counts = {}
		for name in names_parts:
			checked = set()
			for part in name:
				if part not in checked and len(part) > 1:
					counts[part] = counts.get(part, 0) + 1
		sorted_counts = [part[0] for part in sorted(counts.items(), key=lambda x: x[1], reverse=True)]
		return sorted_counts[:count]

	def _suggest_name(self, sub_graph):
		test_names = [data['name'].replace('.', '/').replace(self._most_common, '*') for node, data in sub_graph.nodes(data=True) if data['domain'] == 'test']
		code_names = [data['name'].replace('.', '/').replace(self._most_common, '*') for node, data in sub_graph.nodes(data=True) if data['domain'] == 'code']
		test_suggested_name = _longest_substr(test_names)
		code_suggested_name = _longest_substr(code_names)
		code_summary = '\n'.join(chunks_of(' '.join(self._most_common_parts(sub_graph, 'code')), 40))
		test_summary = '\n'.join(chunks_of(' '.join(self._most_common_parts(sub_graph, 'test')), 40))
		return 'code "%s"\nalso: %s etc.\ntested by\ntest "%s"\nalso: %s etc.\ncontaining %d codes, %d tests' % (code_suggested_name, code_summary, test_suggested_name, test_summary, len(code_names), len(test_names))

	def _save_blockmodels(self, dir, clusterings):
		for clustering in clusterings:
			model = nx.blockmodel(self.graph, clustering.clusters.values())
			for block in model.nodes():
				model.node[block]['cluster'] = block
				sub_graph = model.node[block]['graph']
				key = sub_graph.nodes(data=True)[0][1][clustering.key]
				model.node[block]['key'] = str(key)
				model.node[block]['suggested_name'] = self._suggest_name(sub_graph)
				nx.write_graphml(model.node[block]['graph'], os.path.join(dir, 'block-%s-%s.graphml' % (hash_it(key), clustering.name)))
				del model.node[block]['graph']
			nx.write_graphml(model, os.path.join(dir, 'blockmodel-%s.graphml' % clustering.name))

	def _save_merged_model(self, dir, clusterings, similarity_name=None, similarity=lambda a, b: 0, similarity_depth=None, drop_inter_cluster_edges=False):
		merged_model = nx.DiGraph()
		for clustering in clusterings:
			model = nx.blockmodel(self.graph, clustering.clusters.values())
			for block in model.nodes():
				model.node[block]['original-id'] = block
				model.node[block]['clustering'] = clustering.key
				sub_graph = model.node[block]['graph']
				model.node[block]['key'] = str(sub_graph.nodes(data=True)[0][1][clustering.key])
				model.node[block]['suggested_name'] = self._suggest_name(sub_graph)
			merged_model = nx.disjoint_union(merged_model, model)
		if drop_inter_cluster_edges:
			merged_model.remove_edges_from(merged_model.edges())
		if similarity_name:
			for block_i in merged_model:
				candidates = []
				for block_j in merged_model:
					if block_i != block_j and merged_model.node[block_i]['clustering'] != merged_model.node[block_j]['clustering']:
						graph_i = merged_model.node[block_i]['graph']
						graph_j = merged_model.node[block_j]['graph']
						names_i = set([data['name'] for _, data in graph_i.nodes(data=True)])
						names_j = set([data['name'] for _, data in graph_j.nodes(data=True)])
						current_similarity = similarity(names_i, names_j)
						if current_similarity > 0:
							candidates.append((current_similarity, block_j))
				merged_model.node[block_i]['max_similarity'] = max(candidates, key=lambda x: x[0])[0]
				merged_model.node[block_i]['median_similarity'] = statistics.median([c[0] for c in candidates])
				merged_model.node[block_i]['average_similarity'] = statistics.mean([c[0] for c in candidates])
				for value, block in sorted(candidates, key=lambda x: x[0], reverse=True)[:similarity_depth]:
					merged_model.add_edge(block_i, block, type='suggested_identity')
					merged_model[block_i][block]['similarity'] = value
					merged_model[block_i][block]['label'] = '%s:\n%.4f' % (similarity_name, value)
		for block in merged_model:
			del merged_model.node[block]['graph']
		if drop_inter_cluster_edges:
			nx.write_graphml(merged_model, os.path.join(dir, 'similarity.model_%s.graphml' % similarity_name))
		else:
			nx.write_graphml(merged_model, os.path.join(dir, 'block.model_%s.graphml' % similarity_name))
		return merged_model

print("coverage_cluster.algorithm was loaded.")