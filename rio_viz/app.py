"""rio_viz app."""

import pathlib
import urllib.parse
from functools import partial
from typing import Any, Dict, List, Optional, Type, Union

import attr
import rasterio
import uvicorn
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Path, Query
from geojson_pydantic.features import Feature
from rio_tiler.io import AsyncBaseReader
from rio_tiler.models import BandStatistics, Info
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.types import ASGIApp
from starlette_cramjam.middleware import CompressionMiddleware

from rio_viz.resources.enums import RasterFormat, VectorTileFormat, VectorTileType

from titiler.core.dependencies import (
    AssetsBidxParams,
    AssetsParams,
    BandsExprParamsOptional,
    BandsParams,
    BidxExprParams,
    ColorMapParams,
    DatasetParams,
    DefaultDependency,
    HistogramParams,
    ImageParams,
    ImageRenderingParams,
    PostProcessParams,
    StatisticsParams,
)
from titiler.core.models.mapbox import TileJSON
from titiler.core.resources.responses import JSONResponse, XMLResponse

try:
    from rio_tiler_mvt import pixels_encoder  # noqa

    has_mvt = True
except ModuleNotFoundError:
    has_mvt = False
    pixels_encoder = None

src_dir = str(pathlib.Path(__file__).parent.joinpath("src"))
template_dir = str(pathlib.Path(__file__).parent.joinpath("templates"))
templates = Jinja2Templates(directory=template_dir)

TileFormat = Union[RasterFormat, VectorTileFormat]


class CacheControlMiddleware(BaseHTTPMiddleware):
    """MiddleWare to add CacheControl in response headers."""

    def __init__(self, app: ASGIApp, cachecontrol: str = "no-cache") -> None:
        """Init Middleware."""
        super().__init__(app)
        self.cachecontrol = cachecontrol

    async def dispatch(self, request: Request, call_next):
        """Add cache-control."""
        response = await call_next(request)
        if (
            not response.headers.get("Cache-Control")
            and self.cachecontrol
            and request.method in ["HEAD", "GET"]
            and response.status_code < 500
        ):
            response.headers["Cache-Control"] = self.cachecontrol
        return response


@attr.s
class viz:
    """Creates a very minimal slippy map tile server using fastAPI + Uvicorn."""

    src_path: str = attr.ib()
    reader: Type[AsyncBaseReader] = attr.ib()

    app: FastAPI = attr.ib(default=attr.Factory(FastAPI))

    port: int = attr.ib(default=8080)
    host: str = attr.ib(default="127.0.0.1")
    config: Dict = attr.ib(default=dict)

    minzoom: Optional[int] = attr.ib(default=None)
    maxzoom: Optional[int] = attr.ib(default=None)

    layers: Optional[List[str]] = attr.ib(default=None)
    nodata: Optional[Union[str, int, float]] = attr.ib(default=None)

    # cog / bands / assets
    reader_type: str = attr.ib(default="cog")

    router: Optional[APIRouter] = attr.ib(init=False)

    layer_dependency: Type[DefaultDependency] = attr.ib(init=False)

    @reader_type.validator
    def check(self, attribute, value):
        """Validate reader_type."""
        if value not in ["cog", "bands", "assets"]:
            raise ValueError("`reader_type` must be one of `cog, bands or assets`")

    def __attrs_post_init__(self):
        """Update App."""
        self.router = APIRouter()

        if self.reader_type == "cog":
            # For simple BaseReader (e.g COGReader) we don't add more dependencies.
            self.info_dependency = DefaultDependency
            self.layer_dependency = BidxExprParams

        elif self.reader_type == "bands":
            self.info_dependency = BandsParams
            self.layer_dependency = BandsExprParamsOptional

        elif self.reader_type == "assets":
            self.info_dependency = AssetsParams
            self.layer_dependency = AssetsBidxParams

        self.register_middleware()
        self.register_routes()
        self.app.include_router(self.router)
        self.app.mount("/static", StaticFiles(directory=src_dir), name="static")

    def register_middleware(self):
        """Register Middleware to the FastAPI app."""
        self.app.add_middleware(
            CompressionMiddleware,
            minimum_size=0,
            exclude_mediatype={
                "image/jpeg",
                "image/jpg",
                "image/png",
                "image/jp2",
                "image/webp",
            },
        )
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["GET"],
            allow_headers=["*"],
        )
        self.app.add_middleware(CacheControlMiddleware)

    def _update_params(self, src_dst, options: Type[DefaultDependency]):
        """Create Reader options."""
        if not getattr(options, "expression", None):
            if self.reader_type == "bands":
                # get default bands from self.layers or reader.bands
                bands = self.layers or getattr(src_dst, "bands", None)
                # check if bands is not in options and overwrite
                if bands and not getattr(options, "bands", None):
                    options.bands = bands

            if self.reader_type == "assets":
                # get default assets from self.layers or reader.assets
                assets = self.layers or getattr(src_dst, "assets", None)
                # check if assets is not in options and overwrite
                if assets and not getattr(options, "assets", None):
                    options.assets = assets

    def register_routes(self):  # noqa
        """Register routes to the FastAPI app."""
        img_media_types = {
            "image/png": {},
            "image/jpeg": {},
            "image/webp": {},
            "image/jp2": {},
            "image/tiff; application=geotiff": {},
            "application/x-binary": {},
        }
        mvt_media_types = {
            "application/x-binary": {},
            "application/x-protobuf": {},
        }

        @self.router.get(
            "/info",
            # for MultiBaseReader the output in `Dict[str, Info]`
            response_model=Dict[str, Info] if self.reader_type == "assets" else Info,
            response_model_exclude={"minzoom", "maxzoom", "center"},
            response_model_exclude_none=True,
            response_class=JSONResponse,
            responses={200: {"description": "Return the info of the COG."}},
            tags=["API"],
        )
        async def info(params=Depends(self.info_dependency)):
            """Handle /info requests."""
            async with self.reader(self.src_path) as src_dst:
                # Adapt options for each reader type
                self._update_params(src_dst, params)
                return await src_dst.info(**params)

        @self.router.get(
            "/statistics",
            # for MultiBaseReader the output in `Dict[str, Dict[str, ImageStatistics]]`
            response_model=Dict[str, Dict[str, BandStatistics]]
            if self.reader_type == "assets"
            else Dict[str, BandStatistics],
            response_model_exclude_none=True,
            response_class=JSONResponse,
            responses={200: {"description": "Return the statistics of the COG."}},
            tags=["API"],
        )
        async def statistics(
            layer_params=Depends(self.layer_dependency),
            image_params: ImageParams = Depends(),
            dataset_params: DatasetParams = Depends(),
            stats_params: StatisticsParams = Depends(),
            histogram_params: HistogramParams = Depends(),
        ):
            """Handle /stats requests."""
            async with self.reader(self.src_path) as src_dst:
                if self.nodata is not None and dataset_params.nodata is not None:
                    dataset_params.nodata = self.nodata

                # Adapt options for each reader type
                self._update_params(src_dst, layer_params)

                return await src_dst.statistics(
                    **layer_params,
                    **dataset_params,
                    **image_params,
                    **stats_params,
                    hist_options={**histogram_params},
                )

        @self.router.get(
            "/point",
            responses={200: {"description": "Return a point value."}},
            response_class=JSONResponse,
            tags=["API"],
        )
        async def point(
            coordinates: str = Query(
                ..., description="Coma (',') delimited lon,lat coordinates"
            ),
            layer_params=Depends(self.layer_dependency),
            dataset_params: DatasetParams = Depends(),
        ):
            """Handle /point requests."""
            lon, lat = list(map(float, coordinates.split(",")))
            async with self.reader(self.src_path) as src_dst:  # type: ignore
                if self.nodata is not None and dataset_params.nodata is not None:
                    dataset_params.nodata = self.nodata

                # Adapt options for each reader type
                self._update_params(src_dst, layer_params)

                results = await src_dst.point(
                    lon,
                    lat,
                    **layer_params,
                    **dataset_params,
                )

            return {"coordinates": [lon, lat], "values": results}

        preview_params = dict(
            responses={
                200: {"content": img_media_types, "description": "Return a preview."}
            },
            response_class=Response,
            description="Return a preview.",
        )

        @self.router.get(r"/preview", **preview_params, tags=["API"])
        @self.router.get(r"/preview.{format}", **preview_params, tags=["API"])
        async def preview(
            format: Optional[RasterFormat] = None,
            layer_params=Depends(self.layer_dependency),
            img_params: ImageParams = Depends(),
            dataset_params: DatasetParams = Depends(),
            render_params: ImageRenderingParams = Depends(),
            postprocess_params: PostProcessParams = Depends(),
            colormap: ColorMapParams = Depends(),
        ):
            """Handle /preview requests."""
            async with self.reader(self.src_path) as src_dst:  # type: ignore
                if self.nodata is not None and dataset_params.nodata is not None:
                    dataset_params.nodata = self.nodata

                # Adapt options for each reader type
                self._update_params(src_dst, layer_params)

                data = await src_dst.preview(
                    **layer_params,
                    **dataset_params,
                    **img_params,
                )
                dst_colormap = getattr(src_dst, "colormap", None)

            if not format:
                format = RasterFormat.jpeg if data.mask.all() else RasterFormat.png

            image = data.post_process(**postprocess_params)

            content = image.render(
                img_format=format.driver,
                colormap=colormap or dst_colormap,
                **format.profile,
                **render_params,
            )

            return Response(content, media_type=format.mediatype)

        part_params = dict(
            responses={
                200: {
                    "content": img_media_types,
                    "description": "Return a part of a dataset.",
                }
            },
            response_class=Response,
            description="Return a part of a dataset.",
        )

        @self.router.get(
            r"/crop/{minx},{miny},{maxx},{maxy}.{format}",
            **part_params,
            tags=["API"],
        )
        @self.router.get(
            r"/crop/{minx},{miny},{maxx},{maxy}/{width}x{height}.{format}",
            **part_params,
            tags=["API"],
        )
        async def part(
            minx: float = Path(..., description="Bounding box min X"),
            miny: float = Path(..., description="Bounding box min Y"),
            maxx: float = Path(..., description="Bounding box max X"),
            maxy: float = Path(..., description="Bounding box max Y"),
            format: RasterFormat = Query(
                RasterFormat.png, description="Output image type."
            ),
            layer_params=Depends(self.layer_dependency),
            img_params: ImageParams = Depends(),
            dataset_params: DatasetParams = Depends(),
            render_params: ImageRenderingParams = Depends(),
            postprocess_params: PostProcessParams = Depends(),
            colormap: ColorMapParams = Depends(),
        ):
            """Create image from part of a dataset."""
            async with self.reader(self.src_path) as src_dst:  # type: ignore
                if self.nodata is not None and dataset_params.nodata is not None:
                    dataset_params.nodata = self.nodata

                # Adapt options for each reader type
                self._update_params(src_dst, layer_params)

                data = await src_dst.part(
                    [minx, miny, maxx, maxy],
                    **layer_params,
                    **dataset_params,
                    **img_params,
                )
                dst_colormap = getattr(src_dst, "colormap", None)

            image = data.post_process(**postprocess_params)

            content = image.render(
                img_format=format.driver,
                colormap=colormap or dst_colormap,
                **format.profile,
                **render_params,
            )

            return Response(content, media_type=format.mediatype)

        feature_params = dict(
            responses={
                200: {
                    "content": img_media_types,
                    "description": "Return part of a dataset defined by a geojson feature.",
                }
            },
            response_class=Response,
            description="Return part of a dataset defined by a geojson feature.",
        )

        @self.router.post(r"/crop", **feature_params, tags=["API"])
        @self.router.post(r"/crop.{format}", **feature_params, tags=["API"])
        @self.router.post(
            r"/crop/{width}x{height}.{format}", **feature_params, tags=["API"]
        )
        async def geojson_part(
            geom: Feature,
            format: Optional[RasterFormat] = Query(
                None, description="Output image type."
            ),
            layer_params=Depends(self.layer_dependency),
            img_params: ImageParams = Depends(),
            dataset_params: DatasetParams = Depends(),
            render_params: ImageRenderingParams = Depends(),
            postprocess_params: PostProcessParams = Depends(),
            colormap: ColorMapParams = Depends(),
        ):
            """Handle /feature requests."""
            async with self.reader(self.src_path) as src_dst:  # type: ignore
                if self.nodata is not None and dataset_params.nodata is not None:
                    dataset_params.nodata = self.nodata

                # Adapt options for each reader type
                self._update_params(src_dst, layer_params)

                data = await src_dst.feature(
                    geom.dict(exclude_none=True), **layer_params, **dataset_params
                )
                dst_colormap = getattr(src_dst, "colormap", None)

            if not format:
                format = RasterFormat.jpeg if data.mask.all() else RasterFormat.png

            image = data.post_process(**postprocess_params)

            content = image.render(
                img_format=format.driver,
                colormap=colormap or dst_colormap,
                **format.profile,
                **render_params,
            )

            return Response(content, media_type=format.mediatype)

        tile_params = dict(
            responses={
                200: {
                    "content": {**img_media_types, **mvt_media_types},
                    "description": "Return a tile.",
                }
            },
            response_class=Response,
            description="Read COG and return a tile",
        )

        @self.router.get(r"/tiles/{z}/{x}/{y}", **tile_params, tags=["API"])
        @self.router.get(r"/tiles/{z}/{x}/{y}.{format}", **tile_params, tags=["API"])
        async def tile(
            z: int,
            x: int,
            y: int,
            format: Optional[TileFormat] = None,
            layer_params=Depends(self.layer_dependency),
            dataset_params: DatasetParams = Depends(),
            render_params: ImageRenderingParams = Depends(),
            postprocess_params: PostProcessParams = Depends(),
            colormap: ColorMapParams = Depends(),
            feature_type: Optional[VectorTileType] = Query(
                None,
                title="Feature type (Only for MVT)",
            ),
        ):
            """Handle /tiles requests."""
            tilesize = 256

            if format and format in VectorTileFormat:
                tilesize = 128

            async with self.reader(self.src_path) as src_dst:  # type: ignore
                if self.nodata is not None and dataset_params.nodata is not None:
                    dataset_params.nodata = self.nodata

                # Adapt options for each reader type
                self._update_params(src_dst, layer_params)

                tile_data = await src_dst.tile(
                    x,
                    y,
                    z,
                    tilesize=tilesize,
                    **layer_params,
                    **dataset_params,
                )

                dst_colormap = getattr(src_dst, "colormap", None)

            # Vector Tile
            if format and format in VectorTileFormat:
                if not pixels_encoder:
                    raise HTTPException(
                        status_code=500,
                        detail="rio-tiler-mvt not found, please do pip install rio-viz['mvt']",
                    )

                if not feature_type:
                    raise HTTPException(
                        status_code=500,
                        detail="missing feature_type for vector tile.",
                    )
                _mvt_encoder = partial(run_in_threadpool, pixels_encoder)

                content = await _mvt_encoder(
                    tile_data.data,
                    tile_data.mask,
                    tile_data.band_names,
                    feature_type=feature_type.value,
                )  # type: ignore

            # Raster Tile
            else:
                if not format:
                    format = (
                        RasterFormat.jpeg if tile_data.mask.all() else RasterFormat.png
                    )

                image = tile_data.post_process(**postprocess_params)

                content = image.render(
                    img_format=format.driver,
                    colormap=colormap or dst_colormap,
                    **format.profile,
                    **render_params,
                )

            return Response(content, media_type=format.mediatype)

        @self.router.get(
            "/tilejson.json",
            response_model=TileJSON,
            responses={200: {"description": "Return a tilejson"}},
            response_model_exclude_none=True,
            tags=["API"],
        )
        async def tilejson(
            request: Request,
            tile_format: Optional[TileFormat] = None,
            layer_params=Depends(self.layer_dependency),  # noqa
            dataset_params: DatasetParams = Depends(),  # noqa
            render_params: ImageRenderingParams = Depends(),  # noqa
            postprocess_params: PostProcessParams = Depends(),  # noqa
            colormap: ColorMapParams = Depends(),  # noqa
            feature_type: str = Query(  # noqa
                None, title="Feature type", regex="^(point)|(polygon)$"
            ),
        ):
            """Handle /tilejson.json requests."""
            kwargs: Dict[str, Any] = {"z": "{z}", "x": "{x}", "y": "{y}"}
            if tile_format:
                kwargs["format"] = tile_format.value

            tile_url = request.url_for("tile", **kwargs)

            qs = [
                (key, value)
                for (key, value) in request.query_params._list
                if key not in ["tile_format"]
            ]
            if qs:
                tile_url += f"?{urllib.parse.urlencode(qs)}"

            async with self.reader(self.src_path) as src_dst:  # type: ignore
                bounds = src_dst.geographic_bounds
                minzoom = self.minzoom if self.minzoom is not None else src_dst.minzoom
                maxzoom = self.maxzoom if self.maxzoom is not None else src_dst.maxzoom

            return dict(
                bounds=bounds,
                minzoom=minzoom,
                maxzoom=maxzoom,
                name="rio-viz",
                tilejson="2.1.0",
                tiles=[tile_url],
            )

        @self.router.get(
            "/WMTSCapabilities.xml", response_class=XMLResponse, tags=["API"]
        )
        async def wmts(
            request: Request,
            tile_format: RasterFormat = Query(
                RasterFormat.png, description="Output image type. Default is png."
            ),
            layer_params=Depends(self.layer_dependency),  # noqa
            dataset_params: DatasetParams = Depends(),  # noqa
            render_params: ImageRenderingParams = Depends(),  # noqa
            postprocess_params: PostProcessParams = Depends(),  # noqa
            colormap: ColorMapParams = Depends(),  # noqa
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

            qs = [
                (key, value)
                for (key, value) in request.query_params._list
                if key not in ["tile_format", "REQUEST", "SERVICE"]
            ]
            if qs:
                tiles_endpoint += f"?{urllib.parse.urlencode(qs)}"

            async with self.reader(self.src_path) as src_dst:  # type: ignore
                bounds = src_dst.geographic_bounds
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

            return templates.TemplateResponse(
                "wmts.xml",
                {
                    "request": request,
                    "tiles_endpoint": tiles_endpoint,
                    "bounds": bounds,
                    "tileMatrix": tileMatrix,
                    "title": "Cloud Optimized GeoTIFF",
                    "layer_name": "cogeo",
                    "media_type": tile_format.mediatype,
                },
                media_type="application/xml",
            )

        @self.router.get(
            "/",
            responses={200: {"description": "Simple COG viewer."}},
            response_class=HTMLResponse,
            tags=["Viewer"],
        )
        @self.router.get(
            "/index.html",
            responses={200: {"description": "Simple COG viewer."}},
            response_class=HTMLResponse,
            tags=["Viewer"],
        )
        def viewer(request: Request):
            """Handle /index.html."""
            if self.reader_type == "cog":
                name = "index.html"
            elif self.reader_type == "bands":
                name = "bands.html"
            elif self.reader_type == "assets":
                name = "assets.html"

            return templates.TemplateResponse(
                name=name,
                context={
                    "request": request,
                    "tilejson_endpoint": request.url_for("tilejson"),
                    "stats_endpoint": request.url_for("statistics"),
                    "info_endpoint": request.url_for("info"),
                    "point_endpoint": request.url_for("point"),
                    "allow_3d": has_mvt,
                },
                media_type="text/html",
            )

    @property
    def endpoint(self) -> str:
        """Get endpoint url."""
        return f"http://{self.host}:{self.port}"

    @property
    def template_url(self) -> str:
        """Get simple app template url."""
        return f"http://{self.host}:{self.port}/index.html"

    @property
    def docs_url(self) -> str:
        """Get simple app template url."""
        return f"http://{self.host}:{self.port}/docs"

    def start(self):
        """Start tile server."""
        with rasterio.Env(**self.config):
            uvicorn.run(app=self.app, host=self.host, port=self.port, log_level="info")
