"""rio_viz.raster: raster tiles object."""

from typing import BinaryIO, Tuple, Union

import os
from functools import partial
from concurrent import futures

import numpy

import mercantile
import rasterio
from rasterio.warp import transform_bounds, transform

from rio_tiler import main as cogTiler
from rio_tiler.mercator import get_zooms
from rio_tiler.utils import linear_rescale, _chunks
from rio_tiler_mvt.mvt import encoder as mvtEncoder

from rio_color.operations import parse_operations
from rio_color.utils import scale_dtype, to_math_type


def _get_info(src_path):
    with rasterio.open(src_path) as src_dst:
        bounds = transform_bounds(
            *[src_dst.crs, "epsg:4326"] + list(src_dst.bounds), densify_pts=21
        )
        center = [(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2]
        minzoom, maxzoom = get_zooms(src_dst)

        def _get_name(ix):
            name = src_dst.descriptions[ix - 1]
            if not name:
                name = f"band{ix}"
            return name

        band_descriptions = [_get_name(ix) for ix in src_dst.indexes]

    return bounds, center, minzoom, maxzoom, band_descriptions


def postprocess_tile(
    tile: numpy.ndarray,
    mask: numpy.ndarray,
    rescale: str = None,
    color_formula: str = None,
) -> Tuple[numpy.ndarray, numpy.ndarray]:
    """Post-process tile data."""
    if rescale:
        rescale_arr = list(map(float, rescale.split(",")))
        rescale_arr = list(_chunks(rescale_arr, 2))
        if len(rescale_arr) != tile.shape[0]:
            rescale_arr = ((rescale_arr[0]),) * tile.shape[0]

        for bdx in range(tile.shape[0]):
            tile[bdx] = numpy.where(
                mask,
                linear_rescale(
                    tile[bdx], in_range=rescale_arr[bdx], out_range=[0, 255]
                ),
                0,
            )
        tile = tile.astype(numpy.uint8)

    if color_formula:
        # make sure one last time we don't have
        # negative value before applying color formula
        tile[tile < 0] = 0
        for ops in parse_operations(color_formula):
            tile = scale_dtype(ops(to_math_type(tile)), numpy.uint8)

    return tile, mask


class RasterTiles(object):
    """Raster tiles object."""

    def __init__(self, src_path: str):
        """Initialize RasterTiles object."""
        if isinstance(src_path, str):
            src_path = [src_path]
        elif isinstance(src_path, tuple):
            src_path = list(src_path)
        self.path = src_path

        with futures.ThreadPoolExecutor() as executor:
            responses = list(executor.map(_get_info, self.path))

        self.bounds = responses[0][0]
        self.center = responses[0][1]
        self.minzoom = responses[0][2]
        self.maxzoom = responses[0][3]
        if len(self.path) != 1:
            self.band_descriptions = [
                os.path.basename(p).split(os.path.extsep)[0] for p in self.path
            ]
        else:
            self.band_descriptions = responses[0][4]

    def read_tile(
        self,
        z: int,
        x: int,
        y: int,
        tilesize: int = 256,
        indexes: Tuple[int] = None,
        nodata: Union[str, int, float] = None,
        resampling_method: str = "bilinear",
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
            cogTiler.tile,
            tile_x=x,
            tile_y=y,
            tile_z=z,
            tilesize=tilesize,
            indexes=indexes,
            nodata=nodata,
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
        tilesize: int = 128,
        nodata: Union[str, int, float] = None,
        resampling_method: str = "bilinear",
        feature_type: str = "point",
    ) -> BinaryIO:
        """Read raster tile data and encode to MVT."""
        tile, mask = self.read_tile(
            z,
            x,
            y,
            tilesize=tilesize,
            resampling_method=resampling_method,
            nodata=nodata,
        )
        return mvtEncoder(tile, mask, self.band_descriptions, feature_type=feature_type)

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
        pmin: float = 2.0,
        pmax: float = 98.0,
        nodata: Union[str, int, float] = None,
        histogram_bins: int = 20,
        histogram_range: Tuple = None,
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

        _metadata = partial(
            cogTiler.metadata,
            indexes=indexes,
            nodata=nodata,
            pmin=pmin,
            pmax=pmax,
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
