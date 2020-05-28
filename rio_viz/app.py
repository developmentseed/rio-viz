"""rio_viz app."""

from typing import Any, Optional, Tuple, Union

import re
import urllib.parse
from functools import partial

from starlette.concurrency import run_in_threadpool

from rio_viz import version as rioviz_version

from rio_viz.raster import postprocess_tile
from rio_viz.models.mapbox import TileJSON
from rio_viz.ressources.enums import ImageType, VectorType
from rio_viz.ressources.common import drivers, mimetype
from rio_viz.ressources.responses import TileResponse
from rio_viz.templates.template import index_template_factory, simple_template_factory

from rio_tiler.utils import render
from rio_tiler.colormap import cmap
from rio_tiler.profiles import img_profiles

from starlette.requests import Request
from starlette.responses import Response, HTMLResponse
from starlette.templating import _TemplateResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from fastapi import Depends, FastAPI, Query
import uvicorn

try:
    import rio_tiler_mvt  # noqa

    has_mvt = True
except ModuleNotFoundError:
    has_mvt = False


_postprocess_tile = partial(run_in_threadpool, postprocess_tile)
_render = partial(run_in_threadpool, render)


class viz(object):
    """Creates a very minimal slippy map tile server using fastAPI + Uvicorn."""

    def __init__(
        self,
        raster,
        token: str = None,
        port: int = 8080,
        host: str = "127.0.0.1",
        style: str = "satellite",
    ):
        """Initialize app."""
        self.app = FastAPI(
            title="titiler",
            description="A lightweight Cloud Optimized GeoTIFF tile server",
            version=rioviz_version,
        )
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["GET"],
            allow_headers=["*"],
        )
        self.app.add_middleware(GZipMiddleware, minimum_size=0)

        self.raster = raster
        self.port = port
        self.host = host
        self.style = style
        self.token = token

        @self.app.get(
            "/tiles/{z}/{x}/{y}\\.pbf",
            responses={
                200: {
                    "content": {"application/x-protobuf": {}},
                    "description": "Return a Mapbox Vector Tile.",
                }
            },
            description="Read COG and return a tile",
        )
        async def _mvt(
            z: int,
            x: int,
            y: int,
            tilesize: int = 128,
            feature_type: str = Query(
                None, title="Feature type", regex="^(point)|(polygon)$"
            ),
            resampling_method: str = Query("nearest", title="rasterio resampling"),
        ):
            """Handle /mvt requests."""
            content = await self.raster.read_tile_mvt(
                z,
                x,
                y,
                tilesize=tilesize,
                resampling_method=resampling_method,
                feature_type=feature_type,
            )
            return TileResponse(content, media_type=mimetype["pbf"])

        @self.app.get(
            r"/tiles/{z}/{x}/{y}",
            responses={
                200: {
                    "content": {"image/png": {}, "image/jpg": {}, "image/webp": {}},
                    "description": "Return an image.",
                }
            },
            response_class=TileResponse,
            description="Read COG and return a tile",
        )
        @self.app.get(
            r"/tiles/{z}/{x}/{y}\.{ext}",
            responses={
                200: {
                    "content": {"image/png": {}, "image/jpg": {}, "image/webp": {}},
                    "description": "Return an image.",
                }
            },
            response_class=TileResponse,
            description="Read COG and return a tile",
        )
        async def _tile(
            z: int,
            x: int,
            y: int,
            scale: int = Query(2, gt=0, lt=4),
            ext: ImageType = None,
            indexes: Any = Query(None, description="Coma (',') delimited band indexes"),
            rescale: Any = Query(
                None, description="Coma (',') delimited Min,Max bounds"
            ),
            color_formula: str = Query(None, description="rio-color formula"),
            color_map: str = Query(None, description="rio-tiler color map names"),
            resampling_method: str = Query(
                "bilinear", description="rasterio resampling"
            ),
        ):
            """Handle /tiles requests."""
            if isinstance(indexes, str):
                indexes = tuple(int(s) for s in re.findall(r"\d+", indexes))

            tilesize = scale * 256
            tile, mask = await self.raster.read_tile(
                z,
                x,
                y,
                tilesize=tilesize,
                indexes=indexes,
                resampling_method=resampling_method,
            )

            tile = await _postprocess_tile(
                tile, mask, rescale=rescale, color_formula=color_formula
            )

            if not ext:
                ext = ImageType.jpg if mask.all() else ImageType.png

            driver = drivers[ext]
            options = img_profiles.get(driver.lower(), {})
            options["colormap"] = (
                cmap.get(color_map) if color_map else self.raster.colormap
            )

            content = await _render(tile, mask, img_format=driver, **options)
            return TileResponse(content, media_type=mimetype[ext.value])

        @self.app.get(
            "/tilejson.json",
            response_model=TileJSON,
            responses={200: {"description": "Return a tilejson"}},
            response_model_include={
                "tilejson",
                "scheme",
                "version",
                "minzoom",
                "maxzoom",
                "bounds",
                "center",
                "tiles",
            },  # https://github.com/tiangolo/fastapi/issues/528#issuecomment-589659378
        )
        def _tilejson(
            request: Request,
            response: Response,
            tile_format: Optional[Union[ImageType, VectorType]] = None,
        ):
            """Handle /tilejson.json requests."""
            scheme = request.url.scheme
            host = request.headers["host"]

            kwargs = dict(request.query_params)
            kwargs.pop("tile_format", None)

            tile_url = f"{scheme}://{host}/tiles/{{z}}/{{x}}/{{y}}"
            if tile_format:
                tile_url += f".{tile_format}"

            qs = urllib.parse.urlencode(list(kwargs.items()))
            if qs:
                tile_url += f"?{qs}"

            return dict(
                bounds=self.raster.bounds,
                center=self.raster.center,
                minzoom=self.raster.minzoom,
                maxzoom=self.raster.maxzoom,
                name="rio-viz",
                tilejson="2.1.0",
                tiles=[tile_url],
            )

        @self.app.get(
            "/metadata",
            responses={200: {"description": "Return the metadata of the COG."}},
        )
        async def _metadata(
            response: Response,
            pmin: float = 2.0,
            pmax: float = 98.0,
            indexes: Any = Query(None, title="Coma (',') delimited band indexes"),
        ):
            """Handle /metadata requests."""
            if isinstance(indexes, str):
                indexes = tuple(int(s) for s in re.findall(r"\d+", indexes))

            return await self.raster.metadata(percentiles=(pmin, pmax), indexes=indexes)

        @self.app.get(
            "/info",
            responses={200: {"description": "Return the metadata of the COG."}},
        )
        def _info(response: Response,):
            """Handle /info requests."""
            return self.raster.info()

        @self.app.get(
            "/point", responses={200: {"description": "Return a point value."}}
        )
        def _point(response: Response, coordinates: Any):
            """Handle /point requests."""
            if isinstance(coordinates, str):
                coordinates = list(map(float, coordinates.split(",")))

            return self.raster.point(coordinates)

        @self.app.get(
            "/index.html",
            responses={200: {"description": "Simple COG viewer."}},
            response_class=HTMLResponse,
        )
        def _viewer(template: _TemplateResponse = Depends(index_template_factory)):
            """Handle /index.html."""
            template.context.update(
                {
                    "mapbox_access_token": self.token,
                    "mapbox_style": self.style,
                    "allow_3d": has_mvt,
                }
            )
            return template

        @self.app.get(
            "/index_simple.html",
            responses={200: {"description": "Simple COG viewer."}},
            response_class=HTMLResponse,
        )
        def _simple_viewer(
            template: _TemplateResponse = Depends(simple_template_factory),
        ):
            """Handle /index_simple."""
            template.context.update(
                {"mapbox_access_token": self.token, "mapbox_style": self.style}
            )
            return template

    def get_endpoint_url(self) -> str:
        """Get endpoint url."""
        return f"http://{self.host}:{self.port}"

    def get_template_url(self) -> str:
        """Get simple app template url."""
        return f"http://{self.host}:{self.port}/index.html"

    def get_simple_template_url(self) -> str:
        """Get simple app template url."""
        return f"http://{self.host}:{self.port}/index_simple.html"

    def get_bounds(self) -> str:
        """Get RasterTiles bounds."""
        return self.raster.bounds

    def get_center(self) -> Tuple:
        """Get RasterTiles center."""
        return self.raster.center

    def start(self):
        """Start tile server."""
        uvicorn.run(app=self.app, host=self.host, port=self.port, log_level="info")
