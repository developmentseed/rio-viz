"""rio-viz mosaic reader."""

from typing import Any, Dict, List, Type

import attr
from braceexpand import braceexpand
from morecantile import TileMatrixSet
from rio_tiler.constants import WEB_MERCATOR_TMS, WGS84_CRS
from rio_tiler.errors import PointOutsideBounds
from rio_tiler.io import BaseReader, COGReader
from rio_tiler.models import BandStatistics, ImageData, Info
from rio_tiler.mosaic import mosaic_reader
from rio_tiler.tasks import multi_values


@attr.s
class MosaicReader(BaseReader):
    """Simple Mosaic reader.

    Args:
        input (str): Brace Expandable path (e.g: file{1,2,3}.tif).

    """

    input: str = attr.ib()
    tms: TileMatrixSet = attr.ib(default=WEB_MERCATOR_TMS)

    reader: Type[COGReader] = attr.ib(default=COGReader)

    colormap: Dict = attr.ib(init=False)

    datasets: Dict[str, Type[COGReader]] = attr.ib(init=False)

    def __attrs_post_init__(self):
        """Fetch Reference band to get the bounds."""
        self.datasets = {
            src_path: self.reader(src_path, tms=self.tms)
            for src_path in braceexpand(self.input)
        }

        self.minzoom = min([cog.minzoom for cog in self.datasets.values()])
        self.maxzoom = max([cog.maxzoom for cog in self.datasets.values()])

        self.crs = WGS84_CRS
        bounds = [cog.geographic_bounds for cog in self.datasets.values()]
        minx, miny, maxx, maxy = zip(*bounds)
        self.bounds = [min(minx), min(miny), max(maxx), max(maxy)]

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
        """Get Tile."""
        mosaic_assets = (
            list(reversed(list(self.datasets))) if reverse else list(self.datasets)
        )

        def _reader(
            asset: str, tile_x: int, tile_y: int, tile_z: int, **kwargs: Any
        ) -> ImageData:
            return self.datasets[asset].tile(tile_x, tile_y, tile_z, **kwargs)

        return mosaic_reader(
            mosaic_assets, _reader, tile_x, tile_y, tile_z, threads=0, **kwargs
        )[0]

    def point(
        self,
        lon: float,
        lat: float,
        reverse: bool = False,
        **kwargs: Any,
    ) -> List:
        """Get Point value."""
        mosaic_assets = (
            list(reversed(list(self.datasets))) if reverse else list(self.datasets)
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
        # Most of the info should be similar in other files ¡¡¡
        item = list(self.datasets)[0]
        info_metadata = (
            self.datasets[item]
            .info()
            .dict(
                exclude={
                    "bounds",
                    "minzoom",
                    "maxzoom",
                    "width",
                    "height",
                    "overviews",
                },
            )
        )
        info_metadata["bounds"] = self.bounds
        info_metadata["minzoom"] = self.minzoom
        info_metadata["maxzoom"] = self.maxzoom
        return Info(**info_metadata)

    def statistics(self, **kwargs: Any) -> Dict[str, BandStatistics]:
        """Return Dataset's statistics."""
        # FOR NOW WE ONLY RETURN VALUE FROM THE FIRST FILE
        item = list(self.datasets)[0]
        return self.datasets[item].statistics(**kwargs)

    ############################################################################
    # Not Implemented methods
    # BaseReader required those method to be implemented
    def preview(self, *args, **kwargs):
        """Placeholder for BaseReader.preview."""
        raise NotImplementedError

    def part(self, *args, **kwargs):
        """Placeholder for BaseReader.part."""
        raise NotImplementedError

    def feature(self, *args, **kwargs):
        """Placeholder for BaseReader.feature."""
        raise NotImplementedError
