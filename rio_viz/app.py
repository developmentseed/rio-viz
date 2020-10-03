"""rio_viz app."""

import urllib.parse
from enum import Enum
from functools import partial
from typing import Any, Dict, Optional, Tuple, Union

import pkg_resources
import rasterio
import uvicorn
from fastapi import FastAPI, Query
from rasterio.enums import Resampling
from starlette.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.templating import Jinja2Templates

from rio_tiler.colormap import cmap
from rio_tiler.profiles import img_profiles
from rio_tiler.utils import render

from . import version as rioviz_version
from .models.mapbox import TileJSON
from .models.responses import MetadataModel
from .raster import postprocess_tile
from .ressources.common import drivers, mimetype
from .ressources.enums import ImageType, VectorType
from .ressources.responses import TileResponse, XMLResponse

try:
    import rio_tiler_mvt  # noqa

    has_mvt = True
except ModuleNotFoundError:
    has_mvt = False


template_dir = pkg_resources.resource_filename("rio_viz", "templates")
templates = Jinja2Templates(directory=template_dir)

_postprocess_tile = partial(run_in_threadpool, postprocess_tile)
_render = partial(run_in_threadpool, render)

ResamplingNames = Enum(  # type: ignore
    "ResamplingNames", [(r.name, r.name) for r in Resampling]
)


class viz(object):
    """Creates a very minimal slippy map tile server using fastAPI + Uvicorn."""

    def __init__(
        self,
        raster,
        token: str = None,
        port: int = 8080,
        host: str = "127.0.0.1",
        style: str = "satellite",
        config: Dict = None,
    ):
        """Initialize app."""

        self.config = config or {}

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
            "/tiles/{z}/{x}/{y}.{ext}",
            responses={
                200: {
                    "content": {"application/x-protobuf": {}},
                    "description": "Return a Mapbox Vector Tile.",
                }
            },
            description="Read COG and return a tile",
        )
        async def mvt(
            z: int,
            x: int,
            y: int,
            ext: VectorType,
            tilesize: int = 128,
            feature_type: str = Query(
                None, title="Feature type", regex="^(point)|(polygon)$"
            ),
            resampling_method: ResamplingNames = Query(
                ResamplingNames.nearest, description="Resampling method."  # type: ignore
            ),
        ):
            """Handle /mvt requests."""
            _mvt_tile = partial(run_in_threadpool, self.raster.mvt_tile)

            content = await _mvt_tile(
                z,
                x,
                y,
                tilesize=tilesize,
                resampling_method=resampling_method.name,
                feature_type=feature_type,
            )
            return TileResponse(content, media_type=mimetype[ext.value])

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
            r"/tiles/{z}/{x}/{y}.{ext}",
            responses={
                200: {
                    "content": {"image/png": {}, "image/jpg": {}, "image/webp": {}},
                    "description": "Return an image.",
                }
            },
            response_class=TileResponse,
            description="Read COG and return a tile",
        )
        async def tile(
            z: int,
            x: int,
            y: int,
            scale: int = Query(2, gt=0, lt=4),
            ext: ImageType = None,
            indexes: Optional[str] = Query(
                None, description="Coma (',') delimited band indexes"
            ),
            rescale: Optional[str] = Query(
                None, description="Coma (',') delimited Min,Max bounds"
            ),
            color_formula: Optional[str] = Query(None, description="rio-color formula"),
            color_map: Optional[str] = Query(
                None, description="rio-tiler color map names"
            ),
            resampling_method: ResamplingNames = Query(
                ResamplingNames.nearest, description="Resampling method."  # type: ignore
            ),
        ):
            """Handle /tiles requests."""
            _read_tile = partial(run_in_threadpool, self.raster.tile)

            tilesize = scale * 256
            tile, mask = await _read_tile(
                z,
                x,
                y,
                tilesize=tilesize,
                resampling_method=resampling_method.name,
                indexes=indexes,
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
            response_model_exclude_none=True,
        )
        def tilejson(
            request: Request,
            tile_format: Optional[Union[ImageType, VectorType]] = None,
            indexes: Optional[str] = Query(  # noqa
                None, description="Coma (',') delimited band indexes"
            ),
            rescale: Optional[str] = Query(  # noqa
                None, description="Coma (',') delimited Min,Max bounds"
            ),
            color_formula: Optional[str] = Query(
                None, description="rio-color formula"
            ),  # noqa
            color_map: Optional[str] = Query(  # noqa
                None, description="rio-tiler color map names"
            ),
            resampling_method: ResamplingNames = Query(  # noqa
                ResamplingNames.nearest, description="Resampling method."  # type: ignore
            ),
            feature_type: str = Query(  # noqa
                None, title="Feature type", regex="^(point)|(polygon)$"
            ),
        ):
            """Handle /tilejson.json requests."""
            kwargs: Dict[str, Any] = {"z": "{z}", "x": "{x}", "y": "{y}"}
            if tile_format:
                kwargs["ext"] = tile_format.value

            endpoint_name = (
                "mvt"
                if tile_format and tile_format in [VectorType.pbf, VectorType.mvt]
                else "tile"
            )

            tile_url = request.url_for(endpoint_name, **kwargs)

            kwargs = dict(request.query_params)
            kwargs.pop("tile_format", None)
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
            response_model=MetadataModel,
            response_model_exclude={"minzoom", "maxzoom", "center"},
            response_model_exclude_none=True,
            responses={200: {"description": "Return the metadata of the COG."}},
        )
        async def metadata(
            pmin: float = 2.0,
            pmax: float = 98.0,
            indexes: Optional[str] = Query(
                None, title="Coma (',') delimited band indexes"
            ),
        ):
            """Handle /metadata requests."""
            _read_metadata = partial(run_in_threadpool, self.raster.metadata)
            return await _read_metadata(pmin, pmax, indexes=indexes)

        @self.app.get(
            "/info",
            responses={200: {"description": "Return the metadata of the COG."}},
        )
        async def info():
            """Handle /info requests."""
            return self.raster.info

        @self.app.get(
            "/point", responses={200: {"description": "Return a point value."}},
        )
        async def point(
            coordinates: str = Query(
                ..., title="Coma (',') delimited lon,lat coordinates"
            ),
        ):
            """Handle /point requests."""
            _read_point = partial(run_in_threadpool, self.raster.point)

            lon, lat = list(map(float, coordinates.split(",")))
            return await _read_point(lon, lat)

        @self.app.get(
            "/index.html",
            responses={200: {"description": "Simple COG viewer."}},
            response_class=HTMLResponse,
        )
        def viewer(request: Request):
            """Handle /index.html."""
            return templates.TemplateResponse(
                name="index.html",
                context={
                    "request": request,
                    "tilejson_endpoint": request.url_for("tilejson"),
                    "metadata_endpoint": request.url_for("metadata"),
                    "point_endpoint": request.url_for("point"),
                    "mapbox_access_token": self.token,
                    "mapbox_style": self.style,
                    "allow_3d": has_mvt,
                },
                media_type="text/html",
            )

        @self.app.get("/WMTSCapabilities.xml", response_class=XMLResponse)
        def wmts(
            request: Request,
            tile_format: ImageType = Query(
                ImageType.png, description="Output image type. Default is png."
            ),
            indexes: Optional[str] = Query(  # noqa
                None, description="Coma (',') delimited band indexes"
            ),
            rescale: Optional[str] = Query(  # noqa
                None, description="Coma (',') delimited Min,Max bounds"
            ),
            color_formula: Optional[str] = Query(
                None, description="rio-color formula"
            ),  # noqa
            color_map: Optional[str] = Query(  # noqa
                None, description="rio-tiler color map names"
            ),
            resampling_method: ResamplingNames = Query(  # noqa
                ResamplingNames.nearest, description="Resampling method."  # type: ignore
            ),
        ):
            """
            This is a hidden gem.

            rio-viz is meant to be use to visualize your dataset in the browser but
            using this endpoint, you can also load it in you GIS software.

            """
            kwargs = {
                "z": "{TileMatrix}",
                "x": "{TileCol}",
                "y": "{TileRow}",
                "ext": tile_format.value,
            }
            tiles_endpoint = request.url_for("tile", **kwargs)

            q = dict(request.query_params)
            q.pop("tile_format", None)
            q.pop("minzoom", None)
            q.pop("maxzoom", None)
            q.pop("SERVICE", None)
            q.pop("REQUEST", None)
            qs = urllib.parse.urlencode(list(q.items()))
            if qs:
                tiles_endpoint += f"?{qs}"

            tileMatrix = []
            for zoom in range(self.raster.minzoom, self.raster.maxzoom + 1):
                tm = f"""<TileMatrix>
                    <ows:Identifier>{zoom}</ows:Identifier>
                    <ScaleDenominator>{559082264.02872 / 2 ** zoom / 1}</ScaleDenominator>
                    <TopLeftCorner>-20037508.34278925 20037508.34278925</TopLeftCorner>
                    <TileWidth>256</TileWidth>
                    <TileHeight>256</TileHeight>
                    <MatrixWidth>{2 ** zoom}</MatrixWidth>
                    <MatrixHeight>{2 ** zoom}</MatrixHeight>
                </TileMatrix>"""
                tileMatrix.append(tm)

            media_type = mimetype[tile_format.value]

            return templates.TemplateResponse(
                "wmts.xml",
                {
                    "request": request,
                    "tiles_endpoint": tiles_endpoint,
                    "bounds": self.raster.bounds,
                    "tileMatrix": tileMatrix,
                    "title": "Cloud Optimized GeoTIFF",
                    "layer_name": "cogeo",
                    "media_type": media_type,
                },
                media_type="application/xml",
            )

    @property
    def endpoint_url(self) -> str:
        """Get endpoint url."""
        return f"http://{self.host}:{self.port}"

    @property
    def template_url(self) -> str:
        """Get simple app template url."""
        return f"http://{self.host}:{self.port}/index.html"

    @property
    def bounds(self) -> str:
        """Get RasterTiles bounds."""
        return self.raster.bounds

    @property
    def center(self) -> Tuple:
        """Get RasterTiles center."""
        return self.raster.center

    def start(self):
        """Start tile server."""
        with rasterio.Env(**self.config):
            uvicorn.run(app=self.app, host=self.host, port=self.port, log_level="info")
