import sys
import pdb
from algorithm import *
from clustering import *
from smell import *
from os.path import basename, splitext
import networkx as nx

filename = sys.argv[1]
labels_dir = sys.argv[2]
outputname = filename[:-4]
name = splitext(basename(filename))[0]

coverage = CoverageBasedData(filename, drop_uncovered=True, regenerate_edge_list=False)
detected_clustering = coverage.community_based_clustering(name='%s-detected' % name)
declared_clustering = coverage.package_based_clustering(name='%s-declared' % name, labels_dir=labels_dir)
comparison_dec_det = declared_clustering.compare_to(detected_clustering)
comparison_det_dec = comparison_dec_det.reverse()

comparison_dec_det.dump()
comparison_det_dec.dump()

coverage.save(outputname, clusterings=[detected_clustering, declared_clustering], similarity_constrain=lambda v: v > 0.25)
detected_clustering.save('%s_detected' % outputname)
declared_clustering.save('%s_declared' % outputname)
comparison_dec_det.save(outputname)
comparison_det_dec.save(outputname)
print("Measurement saved.")
pdb.set_trace()

sniffer = Sniffer(coverage.similarity_models, declared_clustering, detected_clustering)
sniffer.save(outputname)
