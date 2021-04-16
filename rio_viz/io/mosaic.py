"""rio-viz mosaic reader."""

from typing import Any, Dict, List, Type

import attr
from braceexpand import braceexpand
from morecantile import TileMatrixSet

from rio_tiler.constants import WEB_MERCATOR_TMS
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
    reader_options: Dict = attr.ib(factory=dict)
    tms: TileMatrixSet = attr.ib(default=WEB_MERCATOR_TMS)

    def __attrs_post_init__(self):
        """Fetch Reference band to get the bounds."""
        self.datasets = {
            src_path: COGReader(src_path, tms=self.tms)
            for src_path in braceexpand(self.filepath)
        }

        self.minzoom = min([cog.minzoom for cog in self.datasets.values()])
        self.maxzoom = max([cog.maxzoom for cog in self.datasets.values()])

        xs = []
        ys = []
        for dataset in self.datasets.values():
            left, bottom, right, top = dataset.bounds
            xs.extend([left, right])
            ys.extend([bottom, top])
        self.bounds = (min(xs), min(ys), max(xs), max(ys))

        # TODO
        # colormap

    def __exit__(self, exc_type, exc_value, traceback):
        """Support using with Context Managers."""
        for dataset in self.datasets.values():
            dataset.close()

    def tile(  # type: ignore
        self, x: int, y: int, z: int, reverse: bool = False, **kwargs: Any,
    ) -> ImageData:
        """Get Tile"""
        mosaic_assets = (
            list(reversed(self.datasets.keys()))
            if reverse
            else list(self.datasets.keys())
        )

        def _reader(asset: str, x: int, y: int, z: int, **kwargs: Any) -> ImageData:
            return self.datasets[asset].tile(x, y, z, **kwargs)

        return mosaic_reader(mosaic_assets, _reader, x, y, z, threads=0, **kwargs)[0]

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
        # FOR NOW WE ONLY RETURN VALUE FROM THE FIRST FILE
        item = list(self.datasets.keys())[0]
        info_metadata = (
            self.datasets[item]
            .info()
            .dict(exclude={"bounds", "center", "minzoom", "maxzoom"})
        )
        spatial_metadata = self.spatial_info.dict()
        return Info(**info_metadata, **spatial_metadata)

    def stats(
        self, pmin: float = 2.0, pmax: float = 98.0, **kwargs: Any,
    ) -> Dict[str, ImageStatistics]:
        """Return Dataset's statistics.

        Args:
            pmin (float, optional): Histogram minimum cut. Defaults to `2.0`.
            pmax (float, optional): Histogram maximum cut. Defaults to `98.0`.

        Returns:
            rio_tile.models.ImageStatistics: Dataset statistics.

        """
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
