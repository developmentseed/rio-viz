"""rio_viz.raster: raster tiles object."""

from typing import Dict, BinaryIO, Tuple, Union, Sequence, Optional

import re
from pathlib import Path
from functools import partial
from concurrent import futures

import numpy

from rio_tiler.io import COGReader
from rio_tiler.io.cogeo import multi_metadata, multi_tile, multi_point

from rio_tiler.utils import linear_rescale, _chunks

from rio_color.operations import parse_operations
from rio_color.utils import scale_dtype, to_math_type

from starlette.concurrency import run_in_threadpool


def _get_info(src_path: str) -> Dict:
    with COGReader(src_path) as cog:
        info = cog.info.copy()
        info["dtype"] = cog.dataset.meta["dtype"]
        info["band_descriptions"] = [band for _, band in info["band_descriptions"]]
    return info


def postprocess_tile(
    tile: numpy.ndarray,
    mask: numpy.ndarray,
    rescale: str = None,
    color_formula: str = None,
) -> numpy.ndarray:
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

    return tile


class RasterTiles(object):
    """Raster tiles object."""

    def __init__(
        self,
        src_path: Sequence[str],
        nodata: Union[str, int, float] = None,
        minzoom: Optional[int] = None,
        maxzoom: Optional[int] = None,
    ):
        """Initialize RasterTiles object."""
        if isinstance(src_path, str):
            src_path = (src_path,)

        self.path = src_path
        self.nodata = nodata

        with futures.ThreadPoolExecutor() as executor:
            responses = list(executor.map(_get_info, self.path))

        self.bounds = responses[0]["bounds"]
        self.center = responses[0]["center"]
        self.minzoom = minzoom if minzoom is not None else responses[0]["minzoom"]
        self.maxzoom = maxzoom if maxzoom is not None else responses[0]["maxzoom"]
        self.data_type = responses[0]["dtype"]
        self.colormap = responses[0].get("colormap")

        if len(self.path) != 1:
            self.band_descriptions = [
                Path(p).stem
                if re.match(r"^band[0-9]+$", responses[idx]["band_descriptions"][0])
                else responses[idx]["band_descriptions"][0]
                for idx, p in enumerate(self.path)
            ]
        else:
            self.band_descriptions = responses[0]["band_descriptions"]

    def info(self) -> Dict:
        """Return general info about the images."""
        return dict(
            bounds=self.bounds,
            center=self.center,
            minzoom=self.minzoom,
            maxzoom=self.maxzoom,
            band_descriptions=[
                (ix + 1, bd) for ix, bd in enumerate(self.band_descriptions)
            ],
            dtype=self.data_type,
        )

    def read_tile(
        self,
        z: int,
        x: int,
        y: int,
        tilesize: int = 256,
        indexes: Sequence[int] = None,
        resampling_method: str = "bilinear",
    ) -> Tuple[numpy.ndarray, numpy.ndarray]:
        """Read raster tile data and mask."""
        if len(self.path) != 1 and indexes:
            path: Sequence[str] = [self.path[ii - 1] for ii in indexes]
            indexes = None
        else:
            path = self.path

        return multi_tile(
            path,
            x,
            y,
            z,
            tilesize=tilesize,
            indexes=indexes,
            nodata=self.nodata,
            resampling_method=resampling_method,
        )

    async def read_tile_mvt(
        self,
        z: int,
        x: int,
        y: int,
        tilesize: int = 128,
        resampling_method: str = "bilinear",
        feature_type: str = "point",
    ) -> BinaryIO:
        """Read raster tile data and encode to MVT."""
        from rio_tiler_mvt import mvt

        mvt_encoder = partial(run_in_threadpool, mvt.encoder)

        tile, mask = self.read_tile(
            z, x, y, tilesize=tilesize, resampling_method=resampling_method
        )
        return await mvt_encoder(
            tile, mask, self.band_descriptions, feature_type=feature_type
        )

    def point(self, coordinates: Tuple[float, float]) -> dict:
        """Read point value."""
        results = multi_point(self.path, *coordinates)
        if len(self.path) != 1:
            results = [r[0] for r in results]
        else:
            results = results[0]

        return {
            "coordinates": coordinates,
            "value": {b: r for b, r in zip(self.band_descriptions, results)},
        }

    def metadata(
        self, pmin: float = 2.0, pmax: float = 98.0, indexes: Sequence[int] = None,
    ) -> dict:
        """Get Raster metadata."""
        if indexes:
            band_descriptions = [(ix, self.band_descriptions[ix - 1]) for ix in indexes]
        else:
            band_descriptions = [
                (ix + 1, d) for ix, d in enumerate(self.band_descriptions)
            ]

        if len(self.path) != 1 and indexes:
            path: Sequence[str] = [self.path[ii - 1] for ii in indexes]
            indexes = None
        else:
            path = self.path

        hist_options = dict()
        if self.colormap:
            hist_options.update(
                dict(bins=[k for k, v in self.colormap.items() if v != (0, 0, 0, 255)])
            )

        results = multi_metadata(
            path,
            pmin,
            pmax,
            indexes=indexes,
            nodata=self.nodata,
            hist_options=hist_options,
        )

        info = {"bounds": self.bounds, "minzoom": self.minzoom, "maxzoom": self.maxzoom}
        info["band_descriptions"] = band_descriptions

        if len(self.path) != 1:
            info["statistics"] = {
                band_descriptions[ix][0]: r["statistics"][1]
                for ix, r in enumerate(results)
            }
        else:
            info["statistics"] = results[0]["statistics"]

        info["dtype"] = self.data_type

        return info
