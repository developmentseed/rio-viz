"""rio-viz app dependencies."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

from fastapi import Query

from .ressources.enums import ColorMaps, ResamplingNames


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
        ResamplingNames.nearest, description="Resampling method."  # type: ignore
    )
    rescale_range: Optional[List[Union[float, int]]] = field(init=False)
    colormap: Optional[Dict[int, Tuple[int, int, int, int]]] = field(init=False)

    def __post_init__(self):
        """Post Init."""
        self.rescale_range = (
            list(map(float, self.rescale.split(","))) if self.rescale else None
        )
        self.colormap = self.color_map.data if self.color_map else None
