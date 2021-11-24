"""Compatibility layer.

Create an AsyncBaseReader from a BaseReader subclass.

"""

from typing import Any, Coroutine, Dict, List, Optional, Tuple, Type, Union

import attr
from rio_tiler.io import (
    AsyncBaseReader,
    BaseReader,
    COGReader,
    MultiBandReader,
    MultiBaseReader,
)
from rio_tiler.models import BandStatistics, ImageData, Info
from starlette.concurrency import run_in_threadpool


@attr.s
class AsyncReader(AsyncBaseReader):
    """Async Reader class."""

    dataset: Union[Type[BaseReader], Type[MultiBandReader], Type[MultiBaseReader]]

    assets: Optional[List[str]]
    bands: Optional[List[str]]
    colormap: Optional[Dict]

    reader: Union[
        Type[BaseReader],
        Type[MultiBandReader],
        Type[MultiBaseReader],
    ] = COGReader

    def __attrs_post_init__(self):
        """PostInit."""
        self.dataset = self.reader(self.input)
        self.bounds = self.dataset.bounds
        self.crs = self.dataset.crs

        self.minzoom = self.dataset.minzoom
        self.maxzoom = self.dataset.maxzoom

        # MultiBase or MultiBand
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

    async def statistics(
        self,
        **kwargs: Any,
    ) -> Coroutine[Any, Any, Dict[str, BandStatistics]]:
        """Return Dataset's statistics."""
        return await run_in_threadpool(self.dataset.statistics, **kwargs)  # type: ignore

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

    async def feature(
        self, shape: Dict, **kwargs: Any
    ) -> Coroutine[Any, Any, ImageData]:
        """Return a preview of a Dataset."""
        return await run_in_threadpool(self.dataset.feature, shape, **kwargs)  # type: ignore
