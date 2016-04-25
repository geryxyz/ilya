import sys
import pdb
from algorithm import *
from clustering import *

filename = sys.argv[1]
outputname = filename[:-4]

coverage = CoverageBasedData(filename, drop_uncovered=True)
detected_clustering = coverage.community_based_clustering()
declared_clustering = coverage.package_based_clustering()
comperation = declared_clustering.compare_to(detected_clustering)

comperation.dump()

coverage.save(outputname)
detected_clustering.save('%s_detected' % outputname, filter='(name|domain)')
declared_clustering.save('%s_declared' % outputname, filter='(name|domain)')
comperation.save(outputname)
print("Measurement saved.")

#pdb.set_trace()