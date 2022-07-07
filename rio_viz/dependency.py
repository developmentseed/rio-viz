"""rio_viz dependency."""

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from fastapi import Query

from rio_viz.algorithm import AVAILABLE_ALGORITHM
from rio_viz.algorithm.base import BaseAlgorithm

Algorithm = Enum(  # type: ignore
    "Algorithm", [(a, a) for a in AVAILABLE_ALGORITHM.keys()]
)


@dataclass
class PostProcessParams:
    """Data Post-Processing options."""

    rescale: Optional[List[str]] = Query(
        None,
        title="Min/Max data Rescaling",
        description="comma (',') delimited Min,Max range. Can set multiple time for multiple bands.",
        example=["0,2000", "0,1000", "0,10000"],  # band 1  # band 2  # band 3
    )
    color_formula: Optional[str] = Query(
        None,
        title="Color Formula",
        description="rio-color formula (info: https://github.com/mapbox/rio-color)",
    )
    algorithm: Algorithm = Query(None, description="Algorithm name", alias="algo")
    algorithm_params: str = Query(
        None, description="Algorithm parameter", alias="algo_params"
    )

    image_process: Optional[BaseAlgorithm] = field(init=False, default=None)

    def __post_init__(self):
        """Post Init."""
        if self.rescale:
            self.rescale = [  # type: ignore
                tuple(map(float, r.replace(" ", "").split(","))) for r in self.rescale
            ]

        kwargs = json.loads(self.algorithm_params) if self.algorithm_params else {}
        if self.algorithm:
            self.image_process = AVAILABLE_ALGORITHM[self.algorithm.name](**kwargs)
