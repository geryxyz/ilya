#mvn3.3 clean clover:setup test clover:aggregate clover:clover -Dmaven.test.failure.ignore=true -Dcheckstyle.skip=true
#java -Djava.library.path=. -jar clover2soda-0.0.1.jar -d ../clustering/joda-time/target/clover/clover.db -c joda-time.method.cov.SoDA
#./soda_build/cl/SoDATools/binaryDump -c joda-time.method.cov.SoDA -w --dump-coverage-data joda-time 

import argparse
import sys
from os.path import basename, splitext

from algorithm import *
from ndd import *

parser = argparse.ArgumentParser(description = 'ILYA Test Clustering')
parser.add_argument('-c', '--coverage', nargs='+', required = True, help = 'the SoDA coverage csv file')
args = parser.parse_args()

coverage_files = args.coverage
detectors = []
for coverage_file in coverage_files:
	outputname = coverage_file[:-4]
	name = splitext(basename(coverage_file))[0]

	print("Processing coverage based data...")
	coverage = CoverageBasedData(coverage_file, drop_uncovered=True, regenerate_edge_list=True)
	print("Creating community based clusters...")
	detected_clustering = coverage.community_based_clustering(name='%s-detected' % name, regenerate_external_data=True)
	print("Creating package based clusters...")
	declared_clustering = coverage.package_based_clustering(name='%s-declared' % name)
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

	measure = cityblock
	detector = NDDDetector(coverage.similarity_models, declared_clustering, detected_clustering, name)
	detectors.append(detector)
	print("Clustering NDDs...")
	NDD_clustering = detector.clustering_ndd(outputname, measure)
	print("Saving NDDs...")
	detector.save(outputname, measure)
	print("NDDs saved.")
	print("Saving NDD clusters...")
	NDD_clustering.save('%s_ndd' % outputname)
	print("NDD clusters saved.")

print("%d coverage matrix was analyzed." % len(detectors))

master_detector = detectors[0].merge_with(*detectors)