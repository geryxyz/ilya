import argparse
import sys
from os.path import basename, splitext

from algorithm import *
from smell import *

parser = argparse.ArgumentParser(description = 'ILYA Test Clustering')
parser.add_argument('-c', '--coverage', required = True, help = 'the SoDA coverage csv file')
parser.add_argument('-l', '--labels', default = 'fake-dir', help = 'the directory of the test and code label files')
parser.add_argument('-d', '--direct', required = True, help = 'the JDT based direct call data file')
parser.add_argument('-t', '--type', choices = ['unit', 'integration'], default = 'unit', help = 'type of the test suite')
parser.add_argument('--pt', type = float, default = 0.0, help = 'P-confidence threshold')
parser.add_argument('--ct', type = float, default = 0.0, help = 'C-confidence threshold')
args = parser.parse_args()

coverage_file = args.coverage
labels_dir = args.labels
direct_calls_file = args.direct
test_type = args.type
p_threshold = args.pt
c_threshold = args.ct

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

sniffer = Sniffer(coverage.similarity_models, declared_clustering, detected_clustering, test_type, p_threshold, c_threshold)
sniffer.save(outputname)
