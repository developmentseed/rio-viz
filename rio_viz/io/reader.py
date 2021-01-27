"""rio-viz multifile reader."""

from typing import Dict, Type

import attr
from braceexpand import braceexpand
from morecantile import TileMatrixSet

from rio_tiler.constants import WEB_MERCATOR_TMS
from rio_tiler.errors import InvalidBandName
from rio_tiler.io import BaseReader, COGReader, MultiBandReader


@attr.s
class MultiFilesReader(MultiBandReader):
    """Multiple Files reader.

    Args:
        filepath (str): Brace Expandable path (e.g: band{1,2,3}.tif).

    """

    filepath: str = attr.ib()
    reader: Type[BaseReader] = attr.ib(default=COGReader)
    reader_options: Dict = attr.ib(factory=dict)
    tms: TileMatrixSet = attr.ib(default=WEB_MERCATOR_TMS)

    def __attrs_post_init__(self):
        """Fetch Reference band to get the bounds."""
        self.files = list(braceexpand(self.filepath))
        self.indexes = [ix + 1 for ix in range(len(self.files))]
        self.bands = [f"file{ix}" for ix in self.indexes]

        with self.reader(self.files[0], tms=self.tms, **self.reader_options) as cog:
            self.bounds = cog.bounds
            self.minzoom = cog.minzoom
            self.maxzoom = cog.maxzoom

    def _get_band_url(self, band: str) -> str:
        """Validate band's name and return band's url."""
        if band not in self.bands:
            raise InvalidBandName(f"{band} is not valid")

        index = self.bands.index(band)
        return self.files[index]
