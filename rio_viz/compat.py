"""Compatibility layer.

Create an AsyncBaseReader from a BaseReader subclass.

"""

from typing import Any, Coroutine, Dict, List, Tuple, Type

import attr
import morecantile
from starlette.concurrency import run_in_threadpool

from rio_tiler import constants
from rio_tiler.io import AsyncBaseReader, BaseReader, COGReader
from rio_tiler.models import ImageData, ImageStatistics, Info, Metadata


@attr.s
class AsyncReader(AsyncBaseReader):
    """Async Reader class."""

    src_path: str = attr.ib()
    tms: morecantile.TileMatrixSet = attr.ib(default=constants.WEB_MERCATOR_TMS)

    reader: Type[BaseReader] = COGReader

    def __attrs_post_init__(self):
        """PostInit."""
        self.dataset = self.reader(self.src_path)
        self.bounds = self.dataset.bounds
        self.minzoom = self.dataset.minzoom
        self.maxzoom = self.dataset.maxzoom

        self.assets = getattr(self.dataset, "assets", None)
        self.bands = getattr(self.dataset, "bands", None)
        self.colormap = getattr(self.dataset, "colormap", None)

        return self

    def close(self):
        """Close rasterio dataset."""
        if getattr(self.dataset, "close", None):
            self.dataset.close()

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Support using with Context Managers."""
        self.close()

    async def info(self, **kwargs: Any) -> Coroutine[Any, Any, Info]:
        """Return Dataset's info."""
        return await run_in_threadpool(self.dataset.info, **kwargs)  # type: ignore

    async def stats(
        self, pmin: float = 2.0, pmax: float = 98.0, **kwargs: Any
    ) -> Coroutine[Any, Any, Dict[str, ImageStatistics]]:
        """Return Dataset's statistics."""
        return await run_in_threadpool(self.dataset.stats, pmin, pmax, **kwargs)  # type: ignore

    async def metadata(
        self, pmin: float = 2.0, pmax: float = 98.0, **kwargs: Any
    ) -> Coroutine[Any, Any, Metadata]:
        """Return Dataset's statistics."""
        return await run_in_threadpool(self.dataset.metadata, pmin, pmax, **kwargs)  # type: ignore

    async def tile(
        self, tile_x: int, tile_y: int, tile_z: int, **kwargs: Any
    ) -> Coroutine[Any, Any, ImageData]:
        """Read a Map tile from the Dataset."""
        return await run_in_threadpool(
            self.dataset.tile, tile_x, tile_y, tile_z, **kwargs  # type: ignore
        )

    async def point(
        self, lon: float, lat: float, **kwargs: Any
    ) -> Coroutine[Any, Any, List]:
        """Read a value from a Dataset."""
        return await run_in_threadpool(self.dataset.point, lon, lat, **kwargs)  # type: ignore

    async def part(
        self, bbox: Tuple[float, float, float, float], **kwargs: Any
    ) -> Coroutine[Any, Any, ImageData]:
        """Read a Part of a Dataset."""
        return await run_in_threadpool(self.dataset.part, bbox, **kwargs)  # type: ignore

    async def preview(self, **kwargs: Any) -> Coroutine[Any, Any, ImageData]:
        """Return a preview of a Dataset."""
        return await run_in_threadpool(self.dataset.preview, **kwargs)  # type: ignore
