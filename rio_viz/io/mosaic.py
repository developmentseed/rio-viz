"""rio-viz mosaic reader."""

from typing import Any, Dict, List, Type

import attr
from braceexpand import braceexpand
from morecantile import TileMatrixSet
from rio_tiler.constants import WEB_MERCATOR_TMS, BBox
from rio_tiler.errors import PointOutsideBounds
from rio_tiler.io import BaseReader, COGReader
from rio_tiler.models import ImageData, ImageStatistics, Info
from rio_tiler.mosaic import mosaic_reader
from rio_tiler.tasks import multi_values


@attr.s
class MosaicReader(BaseReader):
    """Simple Mosaic reader.

    Args:
        filepath (str): Brace Expandable path (e.g: file{1,2,3}.tif).

    """

    filepath: str = attr.ib()
    reader: Type[BaseReader] = attr.ib(default=COGReader)
    tms: TileMatrixSet = attr.ib(default=WEB_MERCATOR_TMS)
    bounds: BBox = attr.ib(init=False)
    minzoom: int = attr.ib(init=False)
    maxzoom: int = attr.ib(init=False)

    colormap: Dict = attr.ib(init=False)

    def __attrs_post_init__(self):
        """Fetch Reference band to get the bounds."""
        self.datasets = {
            src_path: COGReader(src_path, tms=self.tms)
            for src_path in braceexpand(self.filepath)
        }

        self.minzoom = min([cog.minzoom for cog in self.datasets.values()])
        self.maxzoom = max([cog.maxzoom for cog in self.datasets.values()])

        # check for unique dtype
        dtypes = {cog.dataset.dtypes[0] for cog in self.datasets.values()}
        if len(dtypes) > 1:
            raise Exception("Datasets must be of the same data type.")

        # check for same number of band
        nbands = {cog.dataset.count for cog in self.datasets.values()}
        if len(nbands) > 1:
            raise Exception("Datasets must be have the same number of bands.")

        cmaps = [cog.colormap for cog in self.datasets.values() if cog.colormap]
        if len(cmaps) > 0:
            # !!! We take the first one ¡¡¡
            self.colormap = list(cmaps)[0]

        xs = []
        ys = []
        for dataset in self.datasets.values():
            left, bottom, right, top = dataset.bounds
            xs.extend([left, right])
            ys.extend([bottom, top])
        self.bounds = (min(xs), min(ys), max(xs), max(ys))

    def __exit__(self, exc_type, exc_value, traceback):
        """Support using with Context Managers."""
        for dataset in self.datasets.values():
            dataset.close()

    def tile(
        self,
        tile_x: int,
        tile_y: int,
        tile_z: int,
        reverse: bool = False,
        **kwargs: Any,
    ) -> ImageData:
        """Get Tile"""
        mosaic_assets = (
            list(reversed(self.datasets.keys()))
            if reverse
            else list(self.datasets.keys())
        )

        def _reader(
            asset: str, tile_x: int, tile_y: int, tile_z: int, **kwargs: Any
        ) -> ImageData:
            return self.datasets[asset].tile(tile_x, tile_y, tile_z, **kwargs)

        return mosaic_reader(
            mosaic_assets, _reader, tile_x, tile_y, tile_z, threads=0, **kwargs
        )[0]

    def point(
        self, lon: float, lat: float, reverse: bool = False, **kwargs: Any,
    ) -> List:
        """Get Point value."""
        mosaic_assets = (
            list(reversed(self.datasets.keys()))
            if reverse
            else list(self.datasets.keys())
        )

        def _reader(asset: str, lon: float, lat: float, **kwargs) -> List:
            return self.datasets[asset].point(lon, lat, **kwargs)

        if "allowed_exceptions" not in kwargs:
            kwargs.update({"allowed_exceptions": (PointOutsideBounds,)})

        return [
            # FOR NOW WE ONLY RETURN VALUE FROM THE FIRST FILE
            list(r)[0]
            for r in zip(
                *multi_values(
                    mosaic_assets, _reader, lon, lat, threads=0, **kwargs
                ).values()
            )
        ]

    def info(self) -> Info:
        """info."""
        # !!! We return info from the first dataset
        # Most of the info should be simirlar in other files ¡¡¡
        item = list(self.datasets.keys())[0]
        info_metadata = (
            self.datasets[item]
            .info()
            .dict(
                exclude={
                    "bounds",
                    "center",
                    "minzoom",
                    "maxzoom",
                    "width",
                    "height",
                    "overviews",
                }
            )
        )
        spatial_metadata = self.spatial_info.dict()
        return Info(**info_metadata, **spatial_metadata)

    def stats(
        self, pmin: float = 2.0, pmax: float = 98.0, **kwargs: Any,
    ) -> Dict[str, ImageStatistics]:
        """Return Dataset's statistics."""
        # FOR NOW WE ONLY RETURN VALUE FROM THE FIRST FILE
        item = list(self.datasets.keys())[0]
        return self.datasets[item].stats(pmin, pmax, **kwargs)

    ############################################################################
    # Not Implemented methods
    # BaseReader required those method to be implemented
    def preview(self):
        """PlaceHolder for BaseReader.preview."""
        raise NotImplementedError

    def part(self):
        """PlaceHolder for BaseReader.part."""
        raise NotImplementedError

    def feature(self):
        """PlaceHolder for BaseReader.feature."""
        raise NotImplementedError
