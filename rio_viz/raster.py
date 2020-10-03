"""rio_viz.raster: raster tiles object."""

from dataclasses import dataclass, field
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Type, Union

import numpy
from rio_color.operations import parse_operations
from rio_color.utils import scale_dtype, to_math_type

from rio_tiler.io import BaseReader, COGReader
from rio_tiler.utils import _chunks, linear_rescale

try:
    from rio_tiler_mvt import mvt
except ModuleNotFoundError:
    mvt = None


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


@dataclass
class RasterTiles:
    """Raster tiles object."""

    src_path: str
    reader: Type[BaseReader] = field(default=COGReader)
    nodata: Optional[Union[str, int, float]] = None
    minzoom: Optional[int] = None
    maxzoom: Optional[int] = None

    layers: Optional[str] = field(default=None)
    assets: Optional[Tuple[str]] = field(init=False)
    bands: Optional[Tuple[str]] = field(init=False)

    bounds: Tuple[float, float, float, float] = field(init=False)
    center: Tuple[float, float, int] = field(init=False)
    colormap: Dict = field(init=False)
    band_descriptions: List = field(init=False)
    data_type: str = field(init=False)

    def __post_init__(self):
        """Post Init."""
        with self.reader(self.src_path) as src_dst:
            self.bounds = src_dst.bounds
            self.center = src_dst.center

            self.minzoom = self.minzoom if self.minzoom is not None else src_dst.minzoom
            self.maxzoom = self.maxzoom if self.maxzoom is not None else src_dst.maxzoom
            self.colormap = getattr(src_dst, "colormap", None)

            params = {}

            self.assets = getattr(src_dst, "assets", None)
            if self.assets:
                params["assets"] = (
                    self.layers.split(",") if self.layers else self.assets
                )

            self.bands = getattr(src_dst, "bands", None)
            if self.bands:
                params["bands"] = self.layers.split(",") if self.layers else self.bands

            metadata = src_dst.info(**params)

            # TODO: For STAC the metadata format will be different than for other Reader
            self.band_descriptions = metadata["band_descriptions"]
            self.data_type = metadata["dtype"]

    @property
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

    def tile(
        self,
        z: int,
        x: int,
        y: int,
        indexes: Optional[str] = None,
        tilesize: int = 256,
        **kwargs: Any,
    ) -> Tuple[numpy.ndarray, numpy.ndarray]:
        """Read raster tile data and mask."""
        if indexes:
            bidx = tuple(int(s) for s in indexes.split(","))
            if self.assets:
                kwargs["assets"] = [self.assets[b - 1] for b in bidx]
            elif self.bands:
                kwargs["bands"] = [self.bands[b - 1] for b in bidx]
            else:
                kwargs["indexes"] = bidx
        else:
            if self.assets:
                kwargs["assets"] = (
                    self.layers.split(",") if self.layers else self.assets
                )

            if self.bands:
                kwargs["bands"] = self.layers.split(",") if self.layers else self.bands

        with self.reader(self.src_path) as src_dst:
            if self.nodata is not None:
                kwargs["nodata"] = self.nodata
            return src_dst.tile(x, y, z, tilesize=tilesize, **kwargs)

    def mvt_tile(
        self,
        z: int,
        x: int,
        y: int,
        indexes: Optional[str] = None,
        tilesize: int = 128,
        feature_type: str = "point",
        **kwargs: Any,
    ) -> BinaryIO:
        """Read raster tile data and encode to MVT."""
        tile, mask = self.tile(z, x, y, indexes, tilesize=tilesize, **kwargs)
        bands = [b for (_, b) in self.band_descriptions]
        return mvt.encoder(tile, mask, bands, feature_type=feature_type)  # type: ignore

    def point(
        self, lon: float, lat: float, indexes: Optional[str] = None, **kwargs: Any,
    ) -> dict:
        """Read point value."""
        if indexes:
            bidx = tuple(int(s) for s in indexes.split(","))
            if self.assets:
                kwargs["assets"] = [self.assets[b - 1] for b in bidx]
            elif self.bands:
                kwargs["bands"] = [self.bands[b - 1] for b in bidx]
            else:
                kwargs["indexes"] = bidx
        else:
            if self.assets:
                kwargs["assets"] = (
                    self.layers.split(",") if self.layers else self.assets
                )

            if self.bands:
                kwargs["bands"] = self.layers.split(",") if self.layers else self.bands

        with self.reader(self.src_path) as src_dst:
            if self.nodata is not None:
                kwargs["nodata"] = self.nodata
            results = src_dst.point(lon, lat, **kwargs)

        return {
            "coordinates": [lon, lat],
            "value": {b[1]: r for b, r in zip(self.band_descriptions, results)},
        }

    def metadata(
        self,
        pmin: float = 2.0,
        pmax: float = 98.0,
        indexes: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        """Get Raster metadata."""
        if indexes:
            bidx = tuple(int(s) for s in indexes.split(","))
            if self.assets:
                kwargs["assets"] = [self.assets[b - 1] for b in bidx]
            elif self.bands:
                kwargs["bands"] = [self.bands[b - 1] for b in bidx]
            else:
                kwargs["indexes"] = bidx
        else:
            if self.assets:
                kwargs["assets"] = (
                    self.layers.split(",") if self.layers else self.assets
                )

            if self.bands:
                kwargs["bands"] = self.layers.split(",") if self.layers else self.bands

        with self.reader(self.src_path) as src_dst:
            if self.nodata is not None:
                kwargs["nodata"] = self.nodata
            return src_dst.metadata(pmin, pmax, **kwargs)
