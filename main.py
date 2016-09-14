import sys
import pdb
from algorithm import *
from clustering import *
from smell import *
from os.path import basename, splitext
import networkx as nx

coverage_file = sys.argv[1]
labels_dir = sys.argv[2]
direct_calls_file = sys.argv[3]
p_treshold = float(sys.argv[4])
c_treshold = float(sys.argv[5])
outputname = coverage_file[:-4]
name = splitext(basename(coverage_file))[0]

print("Processing coverage based data...")
coverage = CoverageBasedData(coverage_file, drop_uncovered=True, regenerate_edge_list=False)
print("Creating community based clusters...")
detected_clustering = coverage.community_based_clustering(name='%s-detected' % name, regenerate_external_data=False)
print("Calculating confidence...")
detected_clustering.calculate_c_confidence(coverage.edge_list_path)
print("Creating package based clusters...")
declared_clustering = coverage.package_based_clustering(name='%s-declared' % name, labels_dir=labels_dir)
print("Calculating confidence...")
declared_clustering.calculate_p_confidence(direct_calls_file)
print("Comparing declared to detected...")
comparison_dec_det = declared_clustering.compare_to(detected_clustering)
print("Comparing detected to declared...")
comparison_det_dec = comparison_dec_det.reverse()

comparison_dec_det.dump()
print("Saving dec-det...")
comparison_dec_det.save(outputname)
comparison_det_dec.dump()
print("Saving det-dec...")
comparison_det_dec.save(outputname)

print("Saving coverage...")
coverage.save(outputname, clusterings=[detected_clustering, declared_clustering], similarity_constrain=lambda v: v > 0)
print("Saving detected clusters...")
detected_clustering.save('%s_detected' % outputname)
print("Saving declared clusters...")
declared_clustering.save('%s_declared' % outputname)
print("Measurement saved.")

sniffer = Sniffer(coverage.similarity_models, declared_clustering, detected_clustering, p_treshold, c_treshold)
sniffer.save(outputname)
