"""rio_viz app."""

import pathlib
import urllib.parse
from enum import Enum
from functools import partial
from typing import Any, Dict, Optional, Type, Union

import attr
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
from rio_tiler.io import AsyncBaseReader
from rio_tiler.models import Info, Metadata

from .models.mapbox import TileJSON
from .ressources.enums import ImageType, MimeTypes, VectorType
from .ressources.responses import TileResponse, XMLResponse

try:
    from rio_tiler_mvt.mvt import encoder as mvt_encoder  # noqa

    has_mvt = True
except ModuleNotFoundError:
    has_mvt = False


template_dir = str(pathlib.Path(__file__).parent.joinpath("templates"))
templates = Jinja2Templates(directory=template_dir)


_mvt_encoder = partial(run_in_threadpool, mvt_encoder)

ResamplingNames = Enum(  # type: ignore
    "ResamplingNames", [(r.name, r.name) for r in Resampling]
)
ColorMapNames = Enum(  # type: ignore
    "ColorMapNames", [(a, a) for a in sorted(cmap.list())]
)


@attr.s
class viz:
    """Creates a very minimal slippy map tile server using fastAPI + Uvicorn."""

    src_path: str = attr.ib()
    reader: Type[AsyncBaseReader] = attr.ib()

    app: FastAPI = attr.ib(default=attr.Factory(FastAPI))

    token: Optional[str] = attr.ib(default=None)
    port: int = attr.ib(default=8080)
    host: str = attr.ib(default="127.0.0.1")
    style: str = attr.ib(default="satellite")
    config: Dict = attr.ib(default=dict)

    minzoom: Optional[int] = attr.ib(default=None)
    maxzoom: Optional[int] = attr.ib(default=None)

    layers: Optional[str] = attr.ib(default=None)
    nodata: Optional[Union[str, int, float]] = attr.ib(default=None)

    def __attrs_post_init__(self):
        """Update App."""
        self.register_middleware()
        self.register_routes()

    def register_middleware(self):
        """Register Middleware to the FastAPI app."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["GET"],
            allow_headers=["*"],
        )
        self.app.add_middleware(GZipMiddleware, minimum_size=0)

    def _get_options(self, src_dst, indexes: Optional[str] = None):
        """Create Reader options."""
        kwargs: Dict[str, Any] = {}

        assets = getattr(src_dst, "assets", None)
        bands = getattr(src_dst, "bands", None)

        if indexes:
            if assets:
                kwargs["assets"] = indexes.split(",")
            elif bands:
                kwargs["bands"] = indexes.split(",")
            else:
                kwargs["indexes"] = tuple(int(s) for s in indexes.split(","))
        else:
            if assets:
                kwargs["assets"] = self.layers.split(",") if self.layers else assets
            if bands:
                kwargs["bands"] = self.layers.split(",") if self.layers else bands

        if self.nodata is not None:
            kwargs["nodata"] = self.nodata

        return kwargs

    def register_routes(self):
        """Register routes to the FastAPI app."""

        @self.app.get(
            r"/tiles/{z}/{x}/{y}",
            responses={
                200: {
                    "content": {
                        "image/png": {},
                        "image/jpg": {},
                        "image/webp": {},
                        "application/x-protobuf": {},
                    },
                    "description": "Return a tile.",
                }
            },
            response_class=TileResponse,
            description="Read COG and return a tile",
        )
        @self.app.get(
            r"/tiles/{z}/{x}/{y}.{format}",
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
            format: Optional[Union[ImageType, VectorType]] = None,
            indexes: Optional[str] = Query(
                None, description="Coma (',') delimited band indexes"
            ),
            rescale: Optional[str] = Query(
                None, description="Coma (',') delimited Min,Max bounds"
            ),
            color_formula: Optional[str] = Query(None, description="rio-color formula"),
            color_map: Optional[ColorMapNames] = Query(
                None, description="rio-tiler's colormap name"
            ),
            resampling_method: ResamplingNames = Query(
                ResamplingNames.nearest, description="Resampling method."  # type: ignore
            ),
            feature_type: str = Query(
                None,
                title="Feature type (Only for Vector)",
                regex="^(point)|(polygon)$",
            ),
        ):
            """Handle /tiles requests."""
            tilesize = scale * 256

            if format and format in [VectorType.pbf, VectorType.mvt]:
                tilesize = 128

            async with self.reader(self.src_path) as src_dst:  # type: ignore
                kwargs = self._get_options(src_dst, indexes)
                tile_data = await src_dst.tile(
                    x,
                    y,
                    z,
                    tilesize=tilesize,
                    resampling_method=resampling_method.name,
                    **kwargs,
                )

                bands = kwargs.get("bands", kwargs.get("assets", None)) or [
                    f"{ix + 1}" for ix in range(tile_data.count)
                ]

            if format and format in [VectorType.pbf, VectorType.mvt]:
                content = await _mvt_encoder(
                    tile_data.data, tile_data.mask, bands, feature_type=feature_type,
                )  # type: ignore
            else:
                in_range = list(map(float, rescale.split(","))) if rescale else None
                image = tile_data.post_process(
                    in_range=in_range, color_formula=color_formula
                )

                if not format:
                    format = ImageType.jpg if tile_data.mask.all() else ImageType.png

                colormap = (
                    cmap.get(color_map.value)
                    if color_map
                    else getattr(src_dst, "colormap", None)
                )
                content = image.render(
                    img_format=format.driver, colormap=colormap, **format.profile,
                )

            return TileResponse(content, media_type=MimeTypes[format.value].value)

        @self.app.get(
            "/point", responses={200: {"description": "Return a point value."}},
        )
        async def point(
            coordinates: str = Query(
                ..., title="Coma (',') delimited lon,lat coordinates"
            ),
        ):
            """Handle /point requests."""
            lon, lat = list(map(float, coordinates.split(",")))
            async with self.reader(self.src_path) as src_dst:  # type: ignore
                kwargs = self._get_options(src_dst)
                results = await src_dst.point(lon, lat, **kwargs)

            return {"coordinates": [lon, lat], "value": results}

        @self.app.get(
            "/metadata",
            response_model=Union[Dict[str, Metadata], Metadata],
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
            async with self.reader(self.src_path) as src_dst:  # type: ignore
                kwargs = self._get_options(src_dst, indexes)
                return await src_dst.metadata(pmin, pmax, **kwargs)

        @self.app.get(
            "/info",
            response_model=Union[Dict[str, Info], Info],
            response_model_exclude={"minzoom", "maxzoom", "center"},
            response_model_exclude_none=True,
            responses={200: {"description": "Return the metadata of the COG."}},
        )
        async def info():
            """Handle /info requests."""
            async with self.reader(self.src_path) as src_dst:  # type: ignore
                kwargs = self._get_options(src_dst)
                return await src_dst.info(**kwargs)

        @self.app.get(
            "/tilejson.json",
            response_model=TileJSON,
            responses={200: {"description": "Return a tilejson"}},
            response_model_exclude_none=True,
        )
        async def tilejson(
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
            color_map: Optional[ColorMapNames] = Query(  # noqa
                None, description="rio-tiler's colormap name"
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
                kwargs["format"] = tile_format.value

            tile_url = request.url_for("tile", **kwargs)

            kwargs = dict(request.query_params)
            kwargs.pop("tile_format", None)
            qs = urllib.parse.urlencode(list(kwargs.items()))
            if qs:
                tile_url += f"?{qs}"

            async with self.reader(self.src_path) as src_dst:  # type: ignore
                bounds = src_dst.bounds
                center = src_dst.center
                minzoom = self.minzoom if self.minzoom is not None else src_dst.minzoom
                maxzoom = self.maxzoom if self.maxzoom is not None else src_dst.maxzoom

            return dict(
                bounds=bounds,
                center=center,
                minzoom=minzoom,
                maxzoom=maxzoom,
                name="rio-viz",
                tilejson="2.1.0",
                tiles=[tile_url],
            )

        @self.app.get(
            "/index.html",
            responses={200: {"description": "Simple COG viewer."}},
            response_class=HTMLResponse,
        )
        async def viewer(request: Request):
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
        async def wmts(
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
            color_map: Optional[ColorMapNames] = Query(  # noqa
                None, description="rio-tiler's colormap name"
            ),
            resampling_method: ResamplingNames = Query(  # noqa
                ResamplingNames.nearest, description="Resampling method."  # type: ignore
            ),
            feature_type: str = Query(  # noqa
                None, title="Feature type", regex="^(point)|(polygon)$"
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
                "format": tile_format.value,
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

            async with self.reader(self.src_path) as src_dst:  # type: ignore
                bounds = src_dst.bounds
                minzoom = self.minzoom if self.minzoom is not None else src_dst.minzoom
                maxzoom = self.maxzoom if self.maxzoom is not None else src_dst.maxzoom

            tileMatrix = []
            for zoom in range(minzoom, maxzoom + 1):
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

            media_type = MimeTypes[tile_format.value].value

            return templates.TemplateResponse(
                "wmts.xml",
                {
                    "request": request,
                    "tiles_endpoint": tiles_endpoint,
                    "bounds": bounds,
                    "tileMatrix": tileMatrix,
                    "title": "Cloud Optimized GeoTIFF",
                    "layer_name": "cogeo",
                    "media_type": media_type,
                },
                media_type="application/xml",
            )

    @property
    def endpoint(self) -> str:
        """Get endpoint url."""
        return f"http://{self.host}:{self.port}"

    @property
    def template_url(self) -> str:
        """Get simple app template url."""
        return f"http://{self.host}:{self.port}/index.html"

    def start(self):
        """Start tile server."""
        with rasterio.Env(**self.config):
            uvicorn.run(app=self.app, host=self.host, port=self.port, log_level="info")
