"""rio_viz app."""

import pathlib
import urllib.parse
from functools import partial
from typing import Any, Dict, Optional, Type, Union

import attr
import rasterio
import uvicorn
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from geojson_pydantic.features import Feature
from rio_tiler.io import AsyncBaseReader
from rio_tiler.models import Info, Metadata
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.templating import Jinja2Templates
from starlette.types import ASGIApp

from rio_viz.dependencies import AssetsParams, BandsParams, IndexesParams
from rio_viz.resources.enums import RasterFormat, VectorTileFormat, VectorTileType

from titiler.core.dependencies import (
    ColorMapParams,
    DatasetParams,
    DefaultDependency,
    ImageParams,
    MetadataParams,
    RenderParams,
)
from titiler.core.models.mapbox import TileJSON
from titiler.core.resources.responses import XMLResponse

try:
    from rio_tiler_mvt import pixels_encoder  # noqa

    has_mvt = True
except ModuleNotFoundError:
    has_mvt = False
    pixels_encoder = None

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

    token: Optional[str] = attr.ib(default=None)
    port: int = attr.ib(default=8080)
    host: str = attr.ib(default="127.0.0.1")
    style: str = attr.ib(default="satellite")
    config: Dict = attr.ib(default=dict)

    minzoom: Optional[int] = attr.ib(default=None)
    maxzoom: Optional[int] = attr.ib(default=None)

    layers: Optional[str] = attr.ib(default=None)
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
            self.layer_dependency = IndexesParams

        elif self.reader_type == "bands":
            self.layer_dependency = type(
                "BandsParams",
                (BandsParams,),
                {"default_bands": self.layers.split(",") if self.layers else None},
            )

        elif self.reader_type == "assets":
            self.layer_dependency = type(
                "AssetsParams",
                (AssetsParams,),
                {"default_assets": self.layers.split(",") if self.layers else None},
            )

        self.register_middleware()
        self.register_routes()
        self.app.include_router(self.router)

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
        self.app.add_middleware(CacheControlMiddleware)

    def _update_layer_params(self, src_dst, options: Dict[str, Any]):
        """Create Reader options."""
        assets = getattr(src_dst, "assets", None)
        if assets and not options.get("assets"):
            options["assets"] = assets

        bands = getattr(src_dst, "bands", None)
        if bands and not options.get("bands"):
            options["bands"] = bands

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

        preview_params = dict(
            responses={
                200: {"content": img_media_types, "description": "Return a preview."}
            },
            response_class=Response,
            description="Return a preview.",
        )

        @self.router.get(r"/preview", **preview_params)
        @self.router.get(r"/preview.{format}", **preview_params)
        async def preview(
            format: Optional[RasterFormat] = None,
            layer_params=Depends(self.layer_dependency),
            img_params: ImageParams = Depends(),
            dataset_params: DatasetParams = Depends(),
            render_params: RenderParams = Depends(),
            colormap: ColorMapParams = Depends(),
        ):
            """Handle /preview requests."""
            async with self.reader(self.src_path) as src_dst:  # type: ignore
                dataset_kwargs = dataset_params.kwargs
                if self.nodata is not None and not dataset_kwargs.get("nodata"):
                    dataset_kwargs["nodata"] = self.nodata

                # Adapt options for each reader type
                layer_kwargs = layer_params.kwargs
                self._update_layer_params(src_dst, layer_kwargs)
                data = await src_dst.preview(
                    **img_params.kwargs, **layer_kwargs, **dataset_kwargs,
                )
                dst_colormap = getattr(src_dst, "colormap", None)

            if not format:
                format = RasterFormat.jpeg if data.mask.all() else RasterFormat.png

            image = data.post_process(
                in_range=render_params.rescale_range,
                color_formula=render_params.color_formula,
            )

            content = image.render(
                img_format=format.driver,
                colormap=colormap or dst_colormap,
                add_mask=render_params.return_mask,
                **format.profile,
                **render_params.kwargs,
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

        @self.router.get(r"/part", **part_params)
        @self.router.get(r"/part.{format}", **part_params)
        async def part(
            format: Optional[RasterFormat] = Query(
                None, description="Output image type."
            ),
            bbox: str = Query(
                ..., description="Bounding box in form of 'minx,miny,maxx,maxy'"
            ),
            layer_params=Depends(self.layer_dependency),
            img_params: ImageParams = Depends(),
            dataset_params: DatasetParams = Depends(),
            render_params: RenderParams = Depends(),
            colormap: ColorMapParams = Depends(),
        ):
            """Handle /part requests."""
            async with self.reader(self.src_path) as src_dst:  # type: ignore
                dataset_kwargs = dataset_params.kwargs
                if self.nodata is not None and not dataset_kwargs.get("nodata"):
                    dataset_kwargs["nodata"] = self.nodata

                # Adapt options for each reader type
                layer_kwargs = layer_params.kwargs
                self._update_layer_params(src_dst, layer_kwargs)

                data = await src_dst.part(
                    list(map(float, bbox.split(","))),
                    **img_params.kwargs,
                    **layer_kwargs,
                    **dataset_kwargs,
                )
                dst_colormap = getattr(src_dst, "colormap", None)

            if not format:
                format = RasterFormat.jpeg if data.mask.all() else RasterFormat.png

            image = data.post_process(
                in_range=render_params.rescale_range,
                color_formula=render_params.color_formula,
            )

            content = image.render(
                img_format=format.driver,
                colormap=colormap or dst_colormap,
                add_mask=render_params.return_mask,
                **format.profile,
                **render_params.kwargs,
            )

            return Response(content, media_type=format.mediatype)

        @self.router.get(
            "/point", responses={200: {"description": "Return a point value."}},
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
                dataset_kwargs = dataset_params.kwargs
                if self.nodata is not None and not dataset_kwargs.get("nodata"):
                    dataset_kwargs["nodata"] = self.nodata

                # Adapt options for each reader type
                layer_kwargs = layer_params.kwargs
                self._update_layer_params(src_dst, layer_kwargs)

                results = await src_dst.point(
                    lon, lat, **layer_kwargs, **dataset_kwargs
                )

            return {"coordinates": [lon, lat], "value": results}

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

        @self.router.post(r"/feature", **feature_params)
        @self.router.post(r"/feature.{format}", **feature_params)
        async def feature(
            geom: Feature,
            format: Optional[RasterFormat] = Query(
                None, description="Output image type."
            ),
            layer_params=Depends(self.layer_dependency),
            img_params: ImageParams = Depends(),
            dataset_params: DatasetParams = Depends(),
            render_params: RenderParams = Depends(),
            colormap: ColorMapParams = Depends(),
        ):
            """Handle /feature requests."""
            async with self.reader(self.src_path) as src_dst:  # type: ignore
                dataset_kwargs = dataset_params.kwargs
                if self.nodata is not None and not dataset_kwargs.get("nodata"):
                    dataset_kwargs["nodata"] = self.nodata

                # Adapt options for each reader type
                layer_kwargs = layer_params.kwargs
                self._update_layer_params(src_dst, layer_kwargs)

                data = await src_dst.feature(
                    geom.dict(exclude_none=True), **layer_kwargs, **dataset_kwargs
                )
                dst_colormap = getattr(src_dst, "colormap", None)

            if not format:
                format = RasterFormat.jpeg if data.mask.all() else RasterFormat.png

            image = data.post_process(
                in_range=render_params.rescale_range,
                color_formula=render_params.color_formula,
            )

            content = image.render(
                img_format=format.driver,
                colormap=colormap or dst_colormap,
                add_mask=render_params.return_mask,
                **format.profile,
                **render_params.kwargs,
            )

            return Response(content, media_type=format.mediatype)

        @self.router.get(
            "/metadata",
            response_model=Union[Dict[str, Metadata], Metadata],
            response_model_exclude={"minzoom", "maxzoom", "center"},
            response_model_exclude_none=True,
            responses={200: {"description": "Return the metadata of the COG."}},
        )
        async def metadata(
            metadata_params: MetadataParams = Depends(),
            layer_params=Depends(self.layer_dependency),
            dataset_params: DatasetParams = Depends(),
        ):
            """Handle /metadata requests."""
            async with self.reader(self.src_path) as src_dst:  # type: ignore
                dataset_kwargs = dataset_params.kwargs
                if self.nodata is not None and not dataset_kwargs.get("nodata"):
                    dataset_kwargs["nodata"] = self.nodata

                # Adapt options for each reader type
                layer_kwargs = layer_params.kwargs
                self._update_layer_params(src_dst, layer_kwargs)

                return await src_dst.metadata(
                    metadata_params.pmin,
                    metadata_params.pmax,
                    **layer_kwargs,
                    **dataset_kwargs,
                    **metadata_params.kwargs,
                )

        @self.router.get(
            "/info",
            response_model=Union[Dict[str, Info], Info],
            response_model_exclude={"minzoom", "maxzoom", "center"},
            response_model_exclude_none=True,
            responses={200: {"description": "Return the metadata of the COG."}},
        )
        async def info(layer_params=Depends(self.layer_dependency)):
            """Handle /info requests."""
            async with self.reader(self.src_path) as src_dst:  # type: ignore
                # Adapt options for each reader type
                layer_kwargs = layer_params.kwargs
                self._update_layer_params(src_dst, layer_kwargs)
                return await src_dst.info(**layer_kwargs)

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

        @self.router.get(r"/tiles/{z}/{x}/{y}", **tile_params)
        @self.router.get(r"/tiles/{z}/{x}/{y}.{format}", **tile_params)
        async def tile(
            z: int,
            x: int,
            y: int,
            format: Optional[TileFormat] = None,
            layer_params=Depends(self.layer_dependency),
            dataset_params: DatasetParams = Depends(),
            render_params: RenderParams = Depends(),
            colormap: ColorMapParams = Depends(),
            feature_type: Optional[VectorTileType] = Query(
                None, title="Feature type (Only for MVT)",
            ),
        ):
            """Handle /tiles requests."""
            tilesize = 256

            if format and format in VectorTileFormat:
                tilesize = 128

            async with self.reader(self.src_path) as src_dst:  # type: ignore
                dataset_kwargs = dataset_params.kwargs
                if self.nodata is not None and not dataset_kwargs.get("nodata"):
                    dataset_kwargs["nodata"] = self.nodata

                # Adapt options for each reader type
                layer_kwargs = layer_params.kwargs
                self._update_layer_params(src_dst, layer_kwargs)

                tile_data = await src_dst.tile(
                    x, y, z, tilesize=tilesize, **dataset_kwargs, **layer_kwargs,
                )

                bandnames = layer_kwargs.get(
                    "bands", layer_kwargs.get("assets", None)
                ) or [f"{ix + 1}" for ix in range(tile_data.count)]

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
                        status_code=500, detail="missing feature_type for vector tile.",
                    )
                _mvt_encoder = partial(run_in_threadpool, pixels_encoder)

                content = await _mvt_encoder(
                    tile_data.data,
                    tile_data.mask,
                    bandnames,
                    feature_type=feature_type.value,
                )  # type: ignore

            # Raster Tile
            else:
                if not format:
                    format = (
                        RasterFormat.jpeg if tile_data.mask.all() else RasterFormat.png
                    )

                image = tile_data.post_process(
                    in_range=render_params.rescale_range,
                    color_formula=render_params.color_formula,
                )

                content = image.render(
                    img_format=format.driver,
                    colormap=colormap or dst_colormap,
                    add_mask=render_params.return_mask,
                    **format.profile,
                    **render_params.kwargs,
                )

            return Response(content, media_type=format.mediatype)

        @self.router.get(
            "/tilejson.json",
            response_model=TileJSON,
            responses={200: {"description": "Return a tilejson"}},
            response_model_exclude_none=True,
        )
        async def tilejson(
            request: Request,
            tile_format: Optional[TileFormat] = None,
            layer_params=Depends(self.layer_dependency),  # noqa
            dataset_params: DatasetParams = Depends(),  # noqa
            render_params: RenderParams = Depends(),  # noqa
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

        @self.router.get(
            "/index.html",
            responses={200: {"description": "Simple COG viewer."}},
            response_class=HTMLResponse,
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
                    "metadata_endpoint": request.url_for("metadata"),
                    "point_endpoint": request.url_for("point"),
                    "mapbox_access_token": self.token,
                    "mapbox_style": self.style,
                    "allow_3d": has_mvt,
                },
                media_type="text/html",
            )

        @self.router.get("/WMTSCapabilities.xml", response_class=XMLResponse)
        async def wmts(
            request: Request,
            tile_format: RasterFormat = Query(
                RasterFormat.png, description="Output image type. Default is png."
            ),
            layer_params=Depends(self.layer_dependency),  # noqa
            dataset_params: DatasetParams = Depends(),  # noqa
            render_params: RenderParams = Depends(),  # noqa
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
