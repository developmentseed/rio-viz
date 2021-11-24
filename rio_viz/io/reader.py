"""rio-viz multifile reader."""

from typing import Any, Dict, List, Type

import attr
from braceexpand import braceexpand
from morecantile import TileMatrixSet
from rio_tiler.constants import WEB_MERCATOR_TMS
from rio_tiler.errors import InvalidBandName
from rio_tiler.io import BaseReader, COGReader, MultiBandReader, MultiBaseReader


@attr.s
class MultiFilesBandsReader(MultiBandReader):
    """Multiple Files as Bands."""

    input: Any = attr.ib()
    tms: TileMatrixSet = attr.ib(default=WEB_MERCATOR_TMS)

    reader_options: Dict = attr.ib(factory=dict)
    reader: Type[BaseReader] = attr.ib(default=COGReader)

    files: List[str] = attr.ib(init=False)

    def __attrs_post_init__(self):
        """Fetch Reference band to get the bounds."""
        self.files = list(braceexpand(self.input))
        self.bands = [f"b{ix + 1}" for ix in range(len(self.files))]

        with self.reader(self.files[0], tms=self.tms, **self.reader_options) as cog:
            self.bounds = cog.bounds
            self.crs = cog.crs
            self.minzoom = cog.minzoom
            self.maxzoom = cog.maxzoom

    def _get_band_url(self, band: str) -> str:
        """Validate band's name and return band's url."""
        if band not in self.bands:
            raise InvalidBandName(f"{band} is not valid")

        index = self.bands.index(band)
        return self.files[index]


@attr.s
class MultiFilesAssetsReader(MultiBaseReader):
    """Multiple Files as Assets."""

    input: Any = attr.ib()
    tms: TileMatrixSet = attr.ib(default=WEB_MERCATOR_TMS)

    reader_options: Dict = attr.ib(factory=dict)
    reader: Type[BaseReader] = attr.ib(default=COGReader)

    files: List[str] = attr.ib(init=False)

    def __attrs_post_init__(self):
        """Fetch Reference band to get the bounds."""
        self.files = list(braceexpand(self.input))
        self.assets = [f"asset{ix + 1}" for ix in range(len(self.files))]

        with self.reader(self.files[0], tms=self.tms, **self.reader_options) as cog:
            self.bounds = cog.bounds
            self.crs = cog.crs
            self.minzoom = cog.minzoom
            self.maxzoom = cog.maxzoom

    def _get_asset_url(self, asset: str) -> str:
        """Validate band's name and return band's url."""
        if asset not in self.assets:
            raise InvalidBandName(f"{asset} is not valid")

        index = self.assets.index(asset)
        return self.files[index]
