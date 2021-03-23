"""rio-viz app dependencies."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

from fastapi import Query

from .resources.enums import ColorMaps, ResamplingNames


@dataclass
class ImageParams:
    """Image Rendering options."""

    rescale: Optional[str] = Query(
        None,
        title="Min/Max data Rescaling",
        description="comma (',') delimited Min,Max bounds",
    )
    color_formula: Optional[str] = Query(
        None,
        title="Color Formula",
        description="rio-color formula (info: https://github.com/mapbox/rio-color)",
    )
    color_map: Optional[ColorMaps] = Query(  # type: ignore
        None, description="rio-tiler's colormap name"
    )
    resampling_method: ResamplingNames = Query(
        None, description="Resampling method."  # type: ignore
    )
    rescale_range: Optional[List[Union[float, int]]] = field(init=False)
    colormap: Optional[Dict[int, Tuple[int, int, int, int]]] = field(init=False)

    def __post_init__(self):
        """Post Init."""
        if self.resampling_method is None:
            self.resampling_method = ResamplingNames.nearest

        self.rescale_range = (
            list(map(float, self.rescale.split(","))) if self.rescale else None
        )

        self.colormap = self.color_map.data if self.color_map else None


@dataclass
class DefaultDependency:
    """Dependency Base Class"""

    kwargs: Dict = field(init=False, default_factory=dict)


# Dependencies for simple BaseReader
@dataclass
class IndexesParams(DefaultDependency):
    """Band Indexes parameters."""

    bidx: Optional[List[int]] = Query(
        None, title="Band indexes", description="band indexes",
    )

    def __post_init__(self):
        """Post Init."""
        if self.bidx is not None:
            self.kwargs["indexes"] = self.bidx


# Dependencies for  MultiBaseReader
@dataclass
class AssetsParams(DefaultDependency):
    """Asset and Band indexes parameters."""

    asset: Optional[List[str]] = Query(
        None, title="Asset indexes", description="asset names."
    )
    bidx: Optional[List[int]] = Query(
        None, title="Band indexes", description="band indexes",
    )

    default_asset: Optional[List[str]] = field(init=False)

    def __post_init__(self):
        """Post Init."""
        if self.asset or self.default_asset:
            self.kwargs["assets"] = self.asset or self.default_asset
        if self.bidx is not None:
            self.kwargs["indexes"] = self.bidx


# Dependencies for  MultiBandReader
@dataclass
class BandsParams(DefaultDependency):
    """Band names parameters."""

    band: Optional[List[str]] = Query(
        None, title="bands names", description="bands names.",
    )
    bidx: Optional[List[int]] = Query(
        [1], title="Band indexes", description="band indexes",
    )

    default_band: Optional[List[str]] = field(init=False)

    def __post_init__(self):
        """Post Init."""
        if self.band or self.default_band:
            self.kwargs["bands"] = self.band or self.default_band
        if self.bidx is not None:
            self.kwargs["indexes"] = self.bidx
