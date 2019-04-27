"""rio_viz.raster: raster tiles object."""

from typing import Tuple, Union
from typing.io import BinaryIO

import os
from functools import partial
from concurrent import futures

import numpy

import mercantile
import rasterio
from rasterio.warp import transform_bounds, transform

from rio_tiler.main import metadata, tile as main_tiler
from rio_tiler.mercator import get_zooms

from .raster_to_mvt import mvtEncoder


def _get_info(src_path):
    bname = os.path.basename(src_path).split(os.path.extsep)[0]
    with rasterio.open(src_path) as src_dst:
        bounds = transform_bounds(
            *[src_dst.crs, "epsg:4326"] + list(src_dst.bounds), densify_pts=21
        )
        center = [(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2]
        minzoom, maxzoom = get_zooms(src_dst)

        def _get_name(ix):
            name = src_dst.descriptions[ix - 1]
            if not name:
                name = f"{bname}_band{ix}"
            return name

        band_descriptions = [_get_name(ix) for ix in src_dst.indexes]

    return bounds, center, minzoom, maxzoom, band_descriptions


class RasterTiles(object):
    """Raster tiles object."""

    def __init__(self, src_path: str):
        """Initialize RasterTiles object."""
        if isinstance(src_path, str):
            src_path = [src_path]
        elif isinstance(src_path, tuple):
            src_path = list(src_path)

        self.path = src_path
        self.layer_name = os.path.basename(self.path[0])

        with futures.ThreadPoolExecutor() as executor:
            responses = list(executor.map(_get_info, self.path))

        self.bounds = responses[0][0]
        self.center = responses[0][1]
        self.minzoom = responses[0][2]
        self.maxzoom = responses[0][3]
        if len(self.path) != 1:
            self.band_descriptions = [r[4][0] for r in responses]
        else:
            self.band_descriptions = responses[0][4]

    def read_tile(
        self,
        z: int,
        x: int,
        y: int,
        tilesize: int = 256,
        resampling_method: str = "bilinear",
        indexes: Tuple[int] = None,
    ) -> [numpy.ndarray, numpy.ndarray]:
        """Read raster tile data and mask."""
        if isinstance(indexes, int):
            indexes = [indexes]
        elif isinstance(indexes, tuple):
            indexes = list(indexes)

        if len(self.path) != 1 and indexes:
            path = [self.path[ii - 1] for ii in indexes]
            indexes = None
        else:
            path = self.path

        _tiler = partial(
            main_tiler,
            tile_x=x,
            tile_y=y,
            tile_z=z,
            tilesize=tilesize,
            indexes=indexes,
            resampling_method=resampling_method,
        )
        with futures.ThreadPoolExecutor() as executor:
            data, masks = zip(*list(executor.map(_tiler, path)))
            data = numpy.concatenate(data)
            mask = numpy.all(masks, axis=0).astype(numpy.uint8) * 255

        return data, mask

    def read_tile_mvt(
        self,
        z: int,
        x: int,
        y: int,
        tilesize: int = 256,
        resampling_method: str = "bilinear",
        feature_type: str = "point",
    ) -> BinaryIO:
        """Read raster tile data and encode to MVT."""
        mercator_tile = mercantile.Tile(x=x, y=y, z=z)
        quadkey = mercantile.quadkey(*mercator_tile)

        tile, mask = self.read_tile(
            z, x, y, tilesize=tilesize, resampling_method=resampling_method
        )

        return mvtEncoder(
            tile,
            mask,
            quadkey,
            self.band_descriptions,
            self.layer_name,
            feature_type=feature_type,
        )

    def _get_point(self, src_path: str, coordinates: Tuple[float, float]) -> dict:
        with rasterio.open(src_path) as src_dst:
            lon_srs, lat_srs = transform(
                "EPSG:4326", src_dst.crs, [coordinates[0]], [coordinates[1]]
            )
            return list(
                src_dst.sample([(lon_srs[0], lat_srs[0])], indexes=src_dst.indexes)
            )[0].tolist()

    def point(self, coordinates: Tuple[float, float]) -> dict:
        """Read point value."""
        _points = partial(self._get_point, coordinates=coordinates)
        with futures.ThreadPoolExecutor() as executor:
            results = list(executor.map(_points, self.path))

        if len(self.path) != 1:
            results = [r[0] for r in results]
        else:
            results = results[0]

        return {
            "coordinates": coordinates,
            "value": {b: r for b, r in zip(self.band_descriptions, results)},
        }

    def tile_exists(self, z: int, x: int, y: int) -> bool:
        """Check if a mercator tile is within raster bounds."""
        mintile = mercantile.tile(self.bounds[0], self.bounds[3], z)
        maxtile = mercantile.tile(self.bounds[2], self.bounds[1], z)
        return (
            (x <= maxtile.x + 1)
            and (x >= mintile.x)
            and (y <= maxtile.y + 1)
            and (y >= mintile.y)
        )

    def metadata(
        self,
        indexes: str = None,
        histogram_bins: Union[str, int] = 20,
        histogram_range: str = None,
    ) -> dict:
        """Get Raster metadata."""
        if indexes is not None and isinstance(indexes, str):
            indexes = list(map(int, indexes.split(",")))

        if indexes:
            band_descriptions = [(ix, self.band_descriptions[ix - 1]) for ix in indexes]
        else:
            band_descriptions = [
                (ix + 1, d) for ix, d in enumerate(self.band_descriptions)
            ]

        if len(self.path) != 1 and indexes:
            path = [self.path[ii - 1] for ii in indexes]
            indexes = None
        else:
            path = self.path

        if histogram_bins is not None and isinstance(histogram_bins, str):
            histogram_bins = int(histogram_bins)

        if histogram_range is not None and isinstance(histogram_range, str):
            histogram_range = tuple(map(float, histogram_range.split(",")))

        _metadata = partial(
            metadata,
            indexes=indexes,
            histogram_bins=histogram_bins,
            histogram_range=histogram_range,
        )
        with futures.ThreadPoolExecutor() as executor:
            results = list(executor.map(_metadata, path))

        info = {
            "bounds": results[0]["bounds"],
            "minzoom": self.minzoom,
            "maxzoom": self.maxzoom,
        }
        info["band_descriptions"] = band_descriptions

        if len(self.path) != 1:
            info["statistics"] = {
                band_descriptions[ix][0]: r["statistics"][1]
                for ix, r in enumerate(results)
            }
        else:
            info["statistics"] = results[0]["statistics"]

        return info
