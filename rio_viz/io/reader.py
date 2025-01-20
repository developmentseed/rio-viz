"""rio-viz multifile reader."""

from typing import List, Type

import attr
from braceexpand import braceexpand
from rio_tiler import io
from rio_tiler.errors import InvalidBandName
from rio_tiler.types import AssetInfo


@attr.s
class MultiFilesBandsReader(io.MultiBandReader):
    """Multiple Files as Bands."""

    reader: Type[io.BaseReader] = attr.ib(default=io.Reader, init=False)

    _files: List[str] = attr.ib(init=False)

    def __attrs_post_init__(self):
        """Fetch Reference band to get the bounds."""
        self._files = list(braceexpand(self.input))
        self.bands = [f"b{ix + 1}" for ix in range(len(self._files))]

        with self.reader(self._files[0], tms=self.tms, **self.reader_options) as cog:
            self.bounds = cog.bounds
            self.crs = cog.crs
            self.minzoom = cog.minzoom
            self.maxzoom = cog.maxzoom

    def _get_band_url(self, band: str) -> str:
        """Validate band's name and return band's url."""
        if band not in self.bands:
            raise InvalidBandName(f"{band} is not valid")

        index = self.bands.index(band)
        return self._files[index]


@attr.s
class MultiFilesAssetsReader(io.MultiBaseReader):
    """Multiple Files as Assets."""

    reader: Type[io.BaseReader] = attr.ib(default=io.Reader, init=False)

    _files: List[str] = attr.ib(init=False)

    def __attrs_post_init__(self):
        """Fetch Reference band to get the bounds."""
        self._files = list(braceexpand(self.input))
        self.assets = [f"asset{ix + 1}" for ix in range(len(self._files))]

        with self.reader(self._files[0], tms=self.tms, **self.reader_options) as cog:
            self.bounds = cog.bounds
            self.crs = cog.crs
            self.minzoom = cog.minzoom
            self.maxzoom = cog.maxzoom

    def _get_asset_info(self, asset: str) -> AssetInfo:
        """Validate band's name and return band's url."""
        if asset not in self.assets:
            raise InvalidBandName(f"{asset} is not valid")

        index = self.assets.index(asset)
        return AssetInfo(url=self._files[index])
