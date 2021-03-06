#!/usr/bin/env python

# Copyright (C) 2014  Open Data ("Open Data" refers to
# one or more of the following companies: Open Data Partners LLC,
# Open Data Research LLC, or Open Data Capital LLC.)
# 
# This file is part of Hadrian.
# 
# Licensed under the Hadrian Personal Use and Evaluation License (PUEL);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://raw.githubusercontent.com/opendatagroup/hadrian/master/LICENSE
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from titus.fcn import Fcn
from titus.fcn import LibFcn
from titus.signature import Sig
from titus.signature import Sigs
from titus.datatype import *
from titus.errors import *
from titus.util import callfcn, div
import titus.P as P
from titus.lib1.array import argLowestN

provides = {}
def provide(fcn):
    provides[fcn.name] = fcn

prefix = "model.cluster."

#################################################################### 

class Closest(LibFcn):
    name = prefix + "closest"
    sig = Sig([{"datum": P.Array(P.Wildcard("A"))}, {"clusters": P.Array(P.WildRecord("C", {"center": P.Array(P.Wildcard("B"))}))}, {"metric": P.Fcn([P.Array(P.Wildcard("A")), P.Array(P.Wildcard("B"))], P.Double())}], P.Wildcard("C"))
    def __call__(self, state, scope, paramTypes, datum, clusters, metric):
        if len(clusters) == 0:
            raise PFARuntimeException("no clusters")
        distances = [callfcn(state, scope, metric, [datum, x["center"]]) for x in clusters]
        index, = argLowestN(distances, 1, lambda a, b: a < b)
        return clusters[index]
provide(Closest())

class ClosestN(LibFcn):
    name = prefix + "closestN"
    sig = Sig([{"datum": P.Array(P.Wildcard("A"))}, {"clusters": P.Array(P.WildRecord("C", {"center": P.Array(P.Wildcard("B"))}))}, {"metric": P.Fcn([P.Array(P.Wildcard("A")), P.Array(P.Wildcard("B"))], P.Double())}, {"n": P.Int()}], P.Array(P.Wildcard("C")))
    def __call__(self, state, scope, paramTypes, datum, clusters, metric, n):
        distances = [callfcn(state, scope, metric, [datum, x["center"]]) for x in clusters]
        indexes = argLowestN(distances, n, lambda a, b: a < b)
        return [clusters[i] for i in indexes]
provide(ClosestN())

class RandomSeeds(LibFcn):
    name = prefix + "randomSeeds"
    sig = Sig([{"data": P.Array(P.Array(P.Wildcard("A")))}, {"k": P.Int()}, {"newCluster": P.Fcn([P.Int(), P.Array(P.Wildcard("A"))], P.WildRecord("C", {"center": P.Array(P.Wildcard("B"))}))}], P.Array(P.Wildcard("C")))
    def __call__(self, state, scope, paramTypes, data, k, newCluster):
        if k <= 0:
            raise PFARuntimeException("k must be greater than zero")

        uniques = list(set(map(tuple, data)))
        if len(uniques) < k:
            raise PFARuntimeException("not enough unique points")

        sizes = set(len(x) for x in uniques)
        if len(sizes) != 1:
            raise PFARuntimeException("dimensions of vectors do not match")

        state.rand.shuffle(uniques)
        selected = uniques[:k]
        
        return [callfcn(state, scope, newCluster, [i, list(vec)]) for i, vec in enumerate(selected)]
provide(RandomSeeds())

class KMeansIteration(LibFcn):
    name = prefix + "kmeansIteration"
    sig = Sig([{"data": P.Array(P.Array(P.Wildcard("A")))}, {"clusters": P.Array(P.WildRecord("C", {"center": P.Array(P.Wildcard("B"))}))}, {"metric": P.Fcn([P.Array(P.Wildcard("A")), P.Array(P.Wildcard("B"))], P.Double())}, {"update": P.Fcn([P.Array(P.Array(P.Wildcard("A"))), P.Wildcard("C")], P.Wildcard("C"))}], P.Array(P.Wildcard("C")))
    def __call__(self, state, scope, paramTypes, data, clusters, metric, update):
        if len(data) == 0:
            raise PFARuntimeException("no data")

        centers = [x["center"] for x in clusters]

        length = len(clusters)
        if length == 0:
            raise PFARuntimeException("no clusters")

        matched = [[] for i in xrange(length)]

        for datum in data:
            besti = 0
            bestCenter = None
            bestDistance = 0.0
            i = 0
            while i < length:
                thisCenter = centers[i]
                thisDistance = callfcn(state, scope, metric, [datum, thisCenter])
                if bestCenter is None or thisDistance < bestDistance:
                    besti = i
                    bestCenter = thisCenter
                    bestDistance = thisDistance
                i += 1
            matched[besti].append(datum)

        out = []
        for i, matchedData in enumerate(matched):
            if len(matchedData) == 0:
                out.append(clusters[i])
            else:
                out.append(callfcn(state, scope, update, [matchedData, clusters[i]]))
        return out
provide(KMeansIteration())

class UpdateMean(LibFcn):
    name = prefix + "updateMean"
    sig = Sig([{"data": P.Array(P.Array(P.Double()))}, {"cluster": P.WildRecord("C", {"center": P.Array(P.Double())})}, {"weight": P.Double()}], P.Wildcard("C"))
    def __call__(self, state, scope, paramTypes, data, cluster, weight):
        if len(data) == 0:
            raise PFARuntimeException("no data")

        dimension = len(data[0])
        summ = [0.0 for i in xrange(dimension)]

        for vec in data:
            if len(vec) != dimension:
                raise PFARuntimeException("dimensions of vectors do not match")
            for i in xrange(dimension):
                summ[i] += vec[i]

        vec = cluster["center"]
        if len(vec) != dimension:
            raise PFARuntimeException("dimensions of vectors do not match")
        for i in xrange(dimension):
            summ[i] += weight * vec[i]

        denom = len(data) + weight
        for i in xrange(dimension):
            summ[i] = div(summ[i], denom)

        return dict(cluster, center=summ)
provide(UpdateMean())
