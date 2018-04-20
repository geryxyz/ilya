from gremlin_uploader import *
from gremlin_python import *
from gremlin_python import statics
from gremlin_python.structure.graph import Graph
from gremlin_python.process.graph_traversal import __
from gremlin_python.process.strategies import *
from gremlin_python.process.traversal import P
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
import pdb
import argparse as ap
import numpy

def equals(a, b, g):
	if a == b:
		return 1
	else:
		return 0

def get_pos(x, g):
	return g.V(x).properties('pos').value().next()

def pos_equals(a, b, g):
	pos_a = get_pos(a, g)
	pos_b = get_pos(b, g)
	return pos_a == pos_b

def line_info_similarity(a, b, g):
	pos_a_parts = get_pos(a, g).split(':')
	pos_b_parts = get_pos(b, g).split(':')
	same_count = 0
	if pos_a_parts[0] == pos_b_parts[0]:
		same_count += 1 #both in the same file
		if pos_a_parts[1] == pos_b_parts[1]:
			same_count += 1 #both in the same line of the same file
			if pos_a_parts[2] == pos_b_parts[2]:
				same_count += 1 #both in the same col of the same line of the same file
	similarity = same_count / max(len(pos_a_parts), len(pos_b_parts))
	return similarity

def edge_pos_jaccard(a, b, g):
	adj_a = g.V(a).bothE().not_(__.hasLabel('similarity')).bothV().properties('pos').value().dedup().toList()
	adj_a.remove(get_pos(a, g))
	adj_a = set(adj_a)
	adj_b = g.V(b).bothE().not_(__.hasLabel('similarity')).bothV().properties('pos').value().dedup().toList()
	adj_b.remove(get_pos(b, g))
	adj_b = set(adj_b)

	jaccard = len(adj_a & adj_b) / len(adj_a | adj_b)
	if jaccard > 1:
		pdb.set_trace()

	return jaccard

class GraphDiff:
	def __init__(self, vertex_pattern, edge_pattern):
		self.vertex = vertex_pattern
		self.edge = edge_pattern

class PatternCollection:
	def __init__(self, d_ndd, c_ndd):
		self.c_ndd = c_ndd
		self.d_ndd = d_ndd

class GremlinGraphDiffer(GremlinUploader):
	def __init__(self, server_url, traversal_source):
		super(GremlinGraphDiffer, self).__init__(server_url, traversal_source)

	def diff(self, verbose=True, edge_similarity=equals, vertex_similarity=equals, get_id=get_pos, **json_graphs):
		self._drop_graph()
		for name, graph in json_graphs.items():
			self.upload(graph, name, verbose=verbose, drop_graph=False)

		for name_a in json_graphs:
			for name_b in json_graphs:
				if name_a != name_b:
					print('%s ~ %s ...' % (name_a, name_b))
					nodes_a = self.output_graph.V().where(__.has('source_name', name_a)).toList()
					nodes_b = self.output_graph.V().where(__.has('source_name', name_b)).toList()
					self._diff(nodes_a, nodes_b, edge_similarity=edge_similarity, vertex_similarity=vertex_similarity)

		return GraphDiff(self._detect_ndd_vector('vertex'), self._detect_ndd_vector('edge'))

	def _diff(self, nodes_a, nodes_b, edge_similarity=equals, vertex_similarity=equals, get_id=get_pos):
		for a in nodes_a:
			for b in nodes_b:
				edge_value = edge_similarity(a,b, self.output_graph)
				vertex_value = vertex_similarity(a,b, self.output_graph)
				self.output_graph.addE('similarity').from_(a).to(b)\
				.property('edge', edge_value)\
				.property('vertex', vertex_value)\
				.toList()
				if edge_value > 0 or vertex_value > 0:
					print('\n\t%s ~ %s = (V%f, E%f)' % (get_id(a, self.output_graph), get_id(b, self.output_graph), vertex_value, edge_value))
				else:
					print('.', end='')

	def _ndd_vector_of(self, node, property_name):
		self.curve_props = ['alpha', 'count', 'mean_bethas', 'stddev_bethas']
		G_data = []
		histogram = {}
		for alpha_edge in self.output_graph.V(node).outE('similarity').where(__.has(property_name, P.gt(0))):
			alpha = self.output_graph.E(alpha_edge).properties(property_name).value().next()
			bethas = self.output_graph.E(alpha_edge).outV().outE('similarity').properties(property_name).value().toList()
			count_of_parts = self.output_graph.E(alpha_edge).outV().outE('similarity').where(__.has(property_name, P.gt(0))).count().next()
			histogram[count_of_parts] = histogram.get(count_of_parts, 0) + 1
			G_data.append({'alpha': alpha, 'count': count_of_parts, 'mean_bethas': numpy.mean(bethas), 'stddev_bethas': numpy.std(bethas)})
		if histogram.keys():
			for i in range(max(histogram.keys())):
				histogram[i] = histogram.get(i, 0)
		
		return [v for k, v in sorted(histogram.items(), key=lambda x: x[0])][1:], G_data

	def _detect_ndd_vector(self, property_name):
		histograms = {}
		curves = {}
		for node in self.output_graph.V().toList():
			histograms[node], curves[node] = self._ndd_vector_of(node, property_name)
		return GraphDiff(histograms, curves)

if __name__ == '__main__':
	inputs = {}
	class StoreDictKeyPair(ap.Action):
		def __call__(self, parser, namespace, values, option_string=None):
			for kv in values.split(","):
				k,v = kv.split("=")
				inputs[k] = v
				setattr(namespace, self.dest, inputs)

	clap = ap.ArgumentParser(description = 'This script load JSON graph formats to Apache TinkerPop Gremlin server.')
	clap.add_argument('-is', '--inputs', dest="inputs", action=StoreDictKeyPair, metavar="KEY1=VAL1,KEY2=VAL2...", help='path to input file', required=True)
	clap.add_argument('-os', '--output-server', dest='output_server', action='store', help='URL of the output Gremlin server', required=True)
	clap.add_argument('-ots', '--output-source', dest='output_source', action='store', help='name of the output Gremlin traversal source', required=True)
	clap.add_argument('-q', '--quiet', dest='verbose', action='store_false', help='do not print messages except fatal errors')
	clargs = clap.parse_args()

	differ = GremlinGraphDiffer(clargs.output_server, clargs.output_source)	
	patterns = differ.diff(clargs.verbose, edge_similarity=edge_pos_jaccard, vertex_similarity=line_info_similarity, **{name: open(input_file, 'r') for name, input_file in inputs.items()})
	pdb.set_trace()