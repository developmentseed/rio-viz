"""rio_viz.raster: raster tiles object."""

from typing import Tuple, Union
from typing.io import BinaryIO

import os

import mercantile
import rasterio
from rasterio.warp import transform_bounds, transform

from rio_tiler.main import metadata, tile as main_tiler
from rio_tiler.mercator import get_zooms

from .raster_to_mvt import mvtEncoder


class RasterTiles(object):
    """Raster tiles object."""

    def __init__(self, src_path: str):
        """Initialize RasterTiles object."""
        self.path = src_path
        self.layer_name = os.path.basename(self.path)

        with rasterio.open(self.path) as src_dst:
            self.bounds = transform_bounds(
                *[src_dst.crs, "epsg:4326"] + list(src_dst.bounds), densify_pts=21
            )
            self.center = [
                (self.bounds[0] + self.bounds[2]) / 2,
                (self.bounds[1] + self.bounds[3]) / 2,
            ]
            self.minzoom, self.maxzoom = get_zooms(src_dst)

            def _get_name(ix):
                name = src_dst.descriptions[ix - 1]
                if not name:
                    name = f"band{ix}"
                return name

            self.band_descriptions = [_get_name(ix) for ix in src_dst.indexes]

    def read_tile(
        self, z: int, x: int, y: int, tilesize: int = 256, indexes: Tuple[int] = None
    ) -> BinaryIO:
        """Read raster tile data and mask."""
        return main_tiler(self.path, x, y, z, tilesize=tilesize, indexes=indexes)

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

        tile, mask = main_tiler(
            self.path, x, y, z, tilesize=tilesize, resampling_method=resampling_method
        )

        return mvtEncoder(
            tile,
            mask,
            quadkey,
            self.band_descriptions,
            self.layer_name,
            feature_type=feature_type,
        )

    def point(
        self, coordinates: Tuple[float, float], indexes: Tuple[int] = None
    ) -> dict:
        """Read point value."""
        with rasterio.open(self.path) as src_dst:
            indexes = indexes if indexes is not None else src_dst.indexes
            lon_srs, lat_srs = transform(
                "EPSG:4326", src_dst.crs, [coordinates[0]], [coordinates[1]]
            )
            results = list(src_dst.sample([(lon_srs[0], lat_srs[0])], indexes=indexes))[
                0
            ]

        return {
            "coordinates": coordinates,
            "value": {b: r for b, r in zip(self.band_descriptions, results.tolist())},
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

        if histogram_bins is not None and isinstance(histogram_bins, str):
            histogram_bins = int(histogram_bins)

        if histogram_range is not None and isinstance(histogram_range, str):
            histogram_range = tuple(map(float, histogram_range.split(",")))

        return metadata(
            self.path,
            indexes=indexes,
            histogram_bins=histogram_bins,
            histogram_range=histogram_range,
        )
