from clustering import *
import networkx as nx
import community
import re

def _prefix_of(name, level=0):
	unified_name = name.replace('.', '/')
	match = re.search(r'(?P<prefix>[^(]+)', unified_name)
	prefix = 'unknown'
	if match:
		prefix = match.group('prefix')
	return '/'.join(prefix.split('/')[:(-2 - level)])

class CoverageBasedData(object):
	def __init__(self, path_to_dump, drop_uncovered=False):
		self._soda_dump = path_to_dump
		self.graph = nx.Graph()
		self._init_graph(path_to_dump, drop_uncovered=drop_uncovered)

	def _init_graph(self, file_path, drop_uncovered=False):
		with open(file_path, 'r') as matrix:
			header = next(matrix).strip()
			code_elements = header.split(';')
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
						self.graph.add_edge(code_node, test_node)
		if drop_uncovered:
			drop_count = {'test': 0, 'code': 0}
			for node in self.graph.nodes():
				if not nx.edges(self.graph, node):
					drop_count[self.graph.node[node]['domain']] += 1
					self.graph.remove_node(node)
			print("dropping %d uncovered code elements and %d useless tests" % (drop_count['code'], drop_count['test']))
		print("%d node was loaded" % len(self.graph.nodes()))

	def package_based_clustering(self, level=0, label='declared_cluster'):
		mapping = {}
		for node in self.graph.node:
			prefix = _prefix_of(self.graph.node[node]['name'], level=level)
			mapping[node] = prefix
			self.graph.node[node][label] = prefix
		return Clustering(mapping, self.graph)

	def community_based_clustering(self, label='community'):
		mapping = community.best_partition(self.graph)
		for node, community_name in mapping.items():
			self.graph.node[node][label] = community_name
		return Clustering(mapping, self.graph)

	def save(self, name):
		nx.write_graphml(self.graph, '%s.graphml' % name)

print("coverage_cluster.algorithm was loaded.")