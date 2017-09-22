#!/bin/bash

# atalakitja az ellistat (test1.edges.txt) a progi belso reprezentaciojara (test1.bin)
# az ellista fajl <src> <dst>, vagy sulyozott esetben <src> <dst> <w> alaku sorokat tartalmaz,
# ahol <src> es <dst> egy-egy integer <w> pedig egy double (sulyozatlan esetben <w>=1.0 automatikusan)
./convert -i $1.edges.txt -o $1.bin

# kiszamolja a community-ket, alapbol a Newman-Girvan Modularity quality-t optimalizalja (-q 0)
# a -v kapcsoloval kiir egy rakat infot (futasido, aktualis quality, hanyadik osszevonasi korben jar, stb)
# a -l -1 azert kell, hogy a kovetkezo lepes tudjon mibol dolgozni, ezzel egyebken a stdout-ra dump-olja
# az aktualis kor grafjat - ez lesz a test1.tree fajl, ebbol dolgozik a hierarchy tool
./louvain -v -l -1 $1.bin > $1.tree

# <node-id> <community-id> formaban kiirja a stdout-ra, hogy melyik node melyik community tagja lett vegul az utolso kor vegen (-m)
./hierarchy -m $1.tree
