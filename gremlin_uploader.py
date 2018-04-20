#python3 json2gremlin.py -i "samples\totinfo.dynamic.json" -os "ws://localhost:8182/gremlin" -ots "g"

from gremlin_python import statics
from gremlin_python.structure.graph import Graph
from gremlin_python.process.graph_traversal import __
from gremlin_python.process.strategies import *
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
import networkx as nx
import json
import io
import pdb
import argparse as ap
import hashlib

class GremlinUploader(object):
	def __init__(self, server_url, traversal_source):
		super(GremlinUploader, self).__init__()
		self._print("output Gremlin server: %s, %s" % (server_url, traversal_source))
		self.output_graph = Graph().traversal().withRemote(DriverRemoteConnection(server_url, traversal_source))

	def _print(self, obj="", verbose=True):
		if verbose:
			print(obj)
		
	def _drop_graph(self):
		self.output_graph.V().drop().toList()
		self.output_graph.E().drop().toList()

	def upload(self, json_graph, source_name, verbose=True, drop_graph=True):
		if isinstance(json_graph, str):
			input_graph = nx.readwrite.json_graph.node_link_graph(json.loads(json_graph))
		elif isinstance(json_graph, io.TextIOBase):
			input_graph = nx.readwrite.json_graph.node_link_graph(json.load(json_graph))

		if drop_graph:
			self._print("Clearing ouput graph...", verbose)
			self._drop_graph()
			self._print("done", verbose)

		for id, props in input_graph.nodes(data=True):
			self._print("processing node: %s\nwith data: %s" % (id, props), verbose)
			new_node = self.output_graph.addV('node_link_node').next()
			self.output_graph.V(new_node).property('original_id', id).toList()
			self.output_graph.V(new_node).property('source_name', source_name).toList()
			for prop, value in props.items():
				self.output_graph.V(new_node).property(prop, value).toList()
			self._print("added properties: %s" % self.output_graph.V(new_node).properties().toList(), verbose)

		for out_id, in_id, props in input_graph.edges(data=True):
			self._print("processing edge: %s --> %s" % (out_id, in_id), verbose)
			out_node = self.output_graph.V().where(__.has('original_id', out_id)).next()
			in_node = self.output_graph.V().where(__.has('original_id', in_id)).next()
			new_edge = self.output_graph.addE('node_link_connection').from_(out_node).to(in_node).next()
			for prop, value in props.items():
				self.output_graph.E(new_edge).property(prop, value).toList()
			self._print("added properties: %s" % self.output_graph.E(new_edge).properties().toList(), verbose)

		self._print("total nodes added: %d" % self.output_graph.V().count().next(), verbose)
		self._print("total edges added: %d" % self.output_graph.E().count().next(), verbose)

if __name__ == '__main__':
	clap = ap.ArgumentParser(description = 'This script load JSON graph formats to Apache TinkerPop Gremlin server.');
	clap.add_argument('-i', '--input', dest='input_file', action='store', help='path to input file', required=True)
	clap.add_argument('-os', '--output-server', dest='output_server', action='store', help='URL of the output Gremlin server', required=True)
	clap.add_argument('-ots', '--output-source', dest='output_source', action='store', help='name of the output Gremlin traversal source', required=True)
	clap.add_argument('-q', '--quiet', dest='verbose', action='store_false', help='do not print messages except fatal errors')
	clap.add_argument('-k', '--keep', dest='delete', action='store_false', help='do not delete existing graph')

	clargs = clap.parse_args()

	uploader = GremlinUploader(clargs.output_server, clargs.output_source)
	with open(clargs.input_file, 'r') as jsonfile:
		uploader.upload(jsonfile, clargs.input_file, verbose=clargs.verbose, drop_graph=clargs.delete)

