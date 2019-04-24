"""raster_to_mvt: encode tile array to Mapbox Vector Tiles."""
# This module should move in it's own repo/module

import numpy 

from vtzero.tile import Tile, Layer, Point, Polygon

cimport numpy

cpdef bytes mvtEncoder(
    tile,
    mask,
    str quadkey,
    list bandnames,
    str layer_name,
    str feature_type = 'point',
    int mvtsize = 4096,
):
    cdef int sc = mvtsize // tile.shape[1]
    cdef tuple indexes = numpy.where(mask)

    cdef tuple idx
    cdef int x, y

    mvt = Tile()
    mvt_layer = Layer(mvt, layer_name.encode())
    for idx in zip(indexes[1], indexes[0]):
        x, y = idx
        x *= sc
        y *= sc

        if feature_type == 'point':
            feature = Point(mvt_layer)
            feature.add_point(x + sc / 2, y - sc / 2)
        
        elif feature_type == 'polygon':
            feature = Polygon(mvt_layer)
            feature.add_ring(5)
            feature.set_point(x, y)
            feature.set_point(x + sc, y)
            feature.set_point(x + sc, y - sc)
            feature.set_point(x, y - sc)
            feature.set_point(x, y)
        
        for bidx in range(tile.shape[0]):
            feature.add_property(
                bandnames[bidx].encode(), 
                str(tile[bidx, idx[1], idx[0]]).encode()
            )
        feature.commit()

    return mvt.serialize()