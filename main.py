import sys
import pdb
from algorithm import *
from clustering import *
from smell import *
from os.path import basename, splitext
import networkx as nx

filename = sys.argv[1]
outputname = filename[:-4]
name = splitext(basename(filename))[0]

coverage = CoverageBasedData(filename, drop_uncovered=True)
detected_clustering = coverage.community_based_clustering(name='%s-detected' % name)
declared_clustering = coverage.package_based_clustering(name='%s-declared' % name)
comperation_dec_det = declared_clustering.compare_to(detected_clustering)
comperation_det_dec = comperation_dec_det.reverse()

comperation_dec_det.dump()
comperation_det_dec.dump()

coverage.save(outputname, clusterings=[detected_clustering, declared_clustering], similarity_depth=None)
detected_clustering.save('%s_detected' % outputname)
declared_clustering.save('%s_declared' % outputname)
comperation_dec_det.save(outputname)
comperation_det_dec.save(outputname)
print("Measurement saved.")

sniffer = Sniffer(coverage.similarity_models, declared_clustering, detected_clustering)
sniffer.save(outputname)
