import collections
import csv
import json
import sys


Item = collections.namedtuple('Item', 'id name domain')
Result = collections.namedtuple('Result', 'cluster '
                                          'tests_in_cluster '
                                          'tests_in_cluster_nm '
                                          'methods_in_cluster '
                                          'called_methods '
                                          'called_methods_nm '
                                          'called_methods_in_cluster '
                                          'confidence')


if len(sys.argv) != 5:
    print("Usage: %s <data-file> <direct-calls-file> <clusters-file> <output-file>" % (sys.argv[0]))
    exit(1)


data_path = sys.argv[1]
direct_calls_path = sys.argv[2]
clusters_path = sys.argv[3]
output_path = sys.argv[4]


items = dict()

with open(data_path, 'r') as data_file:
    for line in data_file:
        obj = json.loads(line)

        i = Item(obj[0], obj[1]['name'], obj[1]['domain'])
        items[i.id] = i

print('ITEMS', len(items))

methods = set([i.name for i in items.values() if i.domain == 'code'])

print('METHODS', len(methods))

direct_calls = dict()

with open(direct_calls_path, 'r') as direct_calls_file:
    for line in direct_calls_file:
        parts = line.strip().split(';')
        assert len(parts) == 2

        test = parts[0]
        method = parts[1]

        if not test in direct_calls:
            direct_calls[test] = set()

        direct_calls[test].add(method)

print('DIRECT_CALLS', len(direct_calls))

clusters = dict()

with open(clusters_path, 'r') as clusters_file:
    for line in clusters_file:
        line = line.strip()

        if line.endswith(':'):
            cluster = line[:-1]

            if not cluster:
                cluster = 'unknown'

            members = list()
        elif line:
            members.append(items[line])
        else:
            clusters[cluster] = members

print('CLUSTERS', len(clusters))

results = list()

for cluster, members in clusters.items():
    tests_in_cluster = set([m.name for m in members if m.domain == 'test'])
    methods_in_cluster = set([m.name for m in members if m.domain == 'code'])

    called_methods = set()
    tests_not_matched = set()

    for test in tests_in_cluster:
        if test in direct_calls:
            called_methods |= direct_calls[test]
        else:
            tests_not_matched.add(test)

    matched_called_methods = called_methods & methods
    called_in_cluster = matched_called_methods & methods_in_cluster

    n = len(called_in_cluster)
    m = len(matched_called_methods)
    c = n / m if m > 0 else 0

    r = Result(
        cluster=cluster,
        tests_in_cluster = len(tests_in_cluster),
        tests_in_cluster_nm = len(tests_not_matched),
        methods_in_cluster = len(methods_in_cluster),
        called_methods = len(called_methods),
        called_methods_nm = len(called_methods) - m,
        called_methods_in_cluster = n,
        confidence = c
    )
    print(r)
    results.append(r)

if results:
    with open(output_path, 'w') as output_file:
        w = csv.writer(output_file)
        w.writerow(('Cluster',
                    'Tests in the cluster',
                    'Tests in the cluster that did not match',
                    'Methods in the cluster',
                    'All methods called by the tests in the cluster',
                    'Called methods that did not match',
                    'Called methods in the cluster',
                    'Confidence'))
        w.writerows([(r.cluster,
                      r.tests_in_cluster,
                      r.tests_in_cluster_nm,
                      r.methods_in_cluster,
                      r.called_methods,
                      r.called_methods_nm,
                      r.called_methods_in_cluster,
                      r.confidence) for r in results])
