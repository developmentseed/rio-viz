"""rio_viz app."""

import urllib.parse
from typing import Any, Dict, List, Literal, Optional, Tuple, Type, Union

import attr
import jinja2
import rasterio
import uvicorn
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Path, Query
from geojson_pydantic.features import Feature
from geojson_pydantic.geometries import MultiPolygon, Polygon
from rio_tiler.constants import WGS84_CRS
from rio_tiler.io import BaseReader, MultiBandReader, MultiBaseReader, Reader
from rio_tiler.models import BandStatistics, Info
from server_thread import ServerManager, ServerThread
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.templating import Jinja2Templates
from starlette_cramjam.middleware import CompressionMiddleware
from typing_extensions import Annotated

from rio_viz.resources.enums import RasterFormat, VectorTileFormat

from titiler.core.algorithm import algorithms as available_algorithms
from titiler.core.dependencies import (
    AssetsBidxExprParamsOptional,
    AssetsBidxParams,
    AssetsParams,
    BandsExprParamsOptional,
    BandsParams,
    BidxExprParams,
    ColorMapParams,
    CoordCRSParams,
    CRSParams,
    DatasetParams,
    DefaultDependency,
    DstCRSParams,
    HistogramParams,
    ImageRenderingParams,
    PartFeatureParams,
    PreviewParams,
    StatisticsParams,
    TileParams,
)
from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers
from titiler.core.middleware import CacheControlMiddleware
from titiler.core.models.mapbox import TileJSON
from titiler.core.models.responses import (
    InfoGeoJSON,
    MultiBaseInfo,
    MultiBaseInfoGeoJSON,
)
from titiler.core.resources.responses import GeoJSONResponse, JSONResponse, XMLResponse
from titiler.core.utils import render_image

try:
    from rio_tiler_mvt import pixels_encoder  # noqa

    has_mvt = True
except ModuleNotFoundError:
    has_mvt = False
    pixels_encoder = None

jinja2_env = jinja2.Environment(
    loader=jinja2.ChoiceLoader([jinja2.PackageLoader(__package__, "templates")])
)
templates = Jinja2Templates(env=jinja2_env)

TileFormat = Union[RasterFormat, VectorTileFormat]


@attr.s
class viz:
    """Creates a very minimal slippy map tile server using fastAPI + Uvicorn."""

    src_path: str = attr.ib()
    reader: Union[Type[BaseReader], Type[MultiBandReader], Type[MultiBaseReader]] = (
        attr.ib(default=Reader)
    )
    reader_params: Dict = attr.ib(factory=dict)
    app: FastAPI = attr.ib(factory=FastAPI)

    port: int = attr.ib(default=8080)
    host: str = attr.ib(default="127.0.0.1")
    config: Dict = attr.ib(factory=dict)

    minzoom: Optional[int] = attr.ib(default=None)
    maxzoom: Optional[int] = attr.ib(default=None)
    bounds: Optional[Tuple[float, float, float, float]] = attr.ib(default=None)

    layers: Optional[List[str]] = attr.ib(default=None)
    nodata: Optional[Union[str, int, float]] = attr.ib(default=None)

    # cog / bands / assets
    reader_type: str = attr.ib(init=False)

    router: Optional[APIRouter] = attr.ib(init=False)

    statistics_dependency: Type[DefaultDependency] = attr.ib(init=False)
    layer_dependency: Type[DefaultDependency] = attr.ib(init=False)

    def __attrs_post_init__(self):
        """Update App."""
        self.router = APIRouter()

        if issubclass(self.reader, (MultiBandReader)):
            self.reader_type = "bands"
        elif issubclass(self.reader, (MultiBaseReader)):
            self.reader_type = "assets"
        else:
            self.reader_type = "cog"

        if self.reader_type == "cog":
            # For simple BaseReader (e.g Reader) we don't add more dependencies.
            self.info_dependency = DefaultDependency
            self.statistics_dependency = BidxExprParams
            self.layer_dependency = BidxExprParams

        elif self.reader_type == "bands":
            self.info_dependency = BandsParams
            self.statistics_dependency = BandsExprParamsOptional
            self.layer_dependency = BandsExprParamsOptional

        elif self.reader_type == "assets":
            self.info_dependency = AssetsParams
            self.statistics_dependency = AssetsBidxParams
            self.layer_dependency = AssetsBidxExprParamsOptional

        self.register_middleware()
        self.register_routes()
        self.app.include_router(self.router)
        add_exception_handlers(self.app, DEFAULT_STATUS_CODES)

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
        self.app.add_middleware(CacheControlMiddleware, cachecontrol="no-cache")

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
            response_model=MultiBaseInfo if self.reader_type == "assets" else Info,
            response_model_exclude_none=True,
            response_class=JSONResponse,
            responses={200: {"description": "Return the info of the COG."}},
            tags=["API"],
        )
        def info(params=Depends(self.info_dependency)):
            """Handle /info requests."""
            with self.reader(self.src_path, **self.reader_params) as src_dst:
                # Adapt options for each reader type
                self._update_params(src_dst, params)
                return src_dst.info(**params.as_dict())

        @self.router.get(
            "/info.geojson",
            # for MultiBaseReader the output in `Dict[str, Info]`
            response_model=MultiBaseInfoGeoJSON
            if self.reader_type == "assets"
            else InfoGeoJSON,
            response_model_exclude_none=True,
            response_class=GeoJSONResponse,
            responses={
                200: {
                    "content": {"application/geo+json": {}},
                    "description": "Return dataset's basic info as a GeoJSON feature.",
                }
            },
            tags=["API"],
        )
        def info_geojson(
            params=Depends(self.info_dependency),
            crs=Depends(CRSParams),
        ):
            """Handle /info requests."""
            with self.reader(self.src_path, **self.reader_params) as src_dst:
                bounds = src_dst.get_geographic_bounds(crs or WGS84_CRS)
                if bounds[0] > bounds[2]:
                    pl = Polygon.from_bounds(-180, bounds[1], bounds[2], bounds[3])
                    pr = Polygon.from_bounds(bounds[0], bounds[1], 180, bounds[3])
                    geometry = MultiPolygon(
                        type="MultiPolygon",
                        coordinates=[pl.coordinates, pr.coordinates],
                    )
                else:
                    geometry = Polygon.from_bounds(*bounds)

                # Adapt options for each reader type
                self._update_params(src_dst, params)
                return Feature(
                    type="Feature",
                    bbox=bounds,
                    geometry=geometry,
                    properties=src_dst.info(**params.as_dict()),
                )

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
        def statistics(
            layer_params=Depends(self.statistics_dependency),
            image_params: PreviewParams = Depends(),
            dataset_params: DatasetParams = Depends(),
            stats_params: StatisticsParams = Depends(),
            histogram_params: HistogramParams = Depends(),
        ):
            """Handle /stats requests."""
            with self.reader(self.src_path, **self.reader_params) as src_dst:
                if self.nodata is not None and dataset_params.nodata is None:
                    dataset_params.nodata = self.nodata

                # Adapt options for each reader type
                self._update_params(src_dst, layer_params)

                return src_dst.statistics(
                    **layer_params.as_dict(),
                    **dataset_params.as_dict(),
                    **image_params.as_dict(),
                    **stats_params.as_dict(),
                    hist_options=histogram_params.as_dict(),
                )

        @self.router.get(
            "/point",
            responses={200: {"description": "Return a point value."}},
            response_class=JSONResponse,
            tags=["API"],
        )
        def point(
            coordinates: Annotated[
                str,
                Query(description="Coma (',') delimited lon,lat coordinates"),
            ],
            layer_params=Depends(self.layer_dependency),
            dataset_params: DatasetParams = Depends(),
        ):
            """Handle /point requests."""
            lon, lat = list(map(float, coordinates.split(",")))
            with self.reader(self.src_path, **self.reader_params) as src_dst:  # type: ignore
                if self.nodata is not None and dataset_params.nodata is None:
                    dataset_params.nodata = self.nodata

                # Adapt options for each reader type
                self._update_params(src_dst, layer_params)

                pts = src_dst.point(
                    lon,
                    lat,
                    **layer_params.as_dict(),
                    **dataset_params.as_dict(),
                )

            return {
                "coordinates": [lon, lat],
                "values": pts.array.tolist(),
                "band_names": pts.band_names,
            }

        preview_params = {
            "responses": {
                200: {"content": img_media_types, "description": "Return a preview."}
            },
            "response_class": Response,
            "description": "Return a preview.",
        }

        @self.router.get("/preview", **preview_params, tags=["API"])
        @self.router.get("/preview.{format}", **preview_params, tags=["API"])
        def preview(
            format: Optional[RasterFormat] = None,
            layer_params=Depends(self.layer_dependency),
            img_params: PreviewParams = Depends(),
            dataset_params: DatasetParams = Depends(),
            render_params: ImageRenderingParams = Depends(),
            colormap: ColorMapParams = Depends(),
            post_process=Depends(available_algorithms.dependency),
        ):
            """Handle /preview requests."""
            with self.reader(self.src_path, **self.reader_params) as src_dst:  # type: ignore
                if self.nodata is not None and dataset_params.nodata is None:
                    dataset_params.nodata = self.nodata

                # Adapt options for each reader type
                self._update_params(src_dst, layer_params)

                image = src_dst.preview(
                    **layer_params.as_dict(),
                    **dataset_params.as_dict(),
                    **img_params.as_dict(),
                )
                dst_colormap = getattr(src_dst, "colormap", None)

            if post_process:
                image = post_process(image)

            content, media_type = render_image(
                image,
                output_format=format,
                colormap=colormap or dst_colormap,
                **render_params.as_dict(),
            )

            return Response(content, media_type=media_type)

        part_params = {
            "responses": {
                200: {
                    "content": img_media_types,
                    "description": "Return a part of a dataset.",
                }
            },
            "response_class": Response,
            "description": "Return a part of a dataset.",
        }

        @self.router.get(
            "/bbox/{minx},{miny},{maxx},{maxy}.{format}",
            **part_params,
            tags=["API"],
        )
        @self.router.get(
            "/bbox/{minx},{miny},{maxx},{maxy}/{width}x{height}.{format}",
            **part_params,
            tags=["API"],
        )
        def part(
            minx: Annotated[float, Path(description="Bounding box min X")],
            miny: Annotated[float, Path(description="Bounding box min Y")],
            maxx: Annotated[float, Path(description="Bounding box max X")],
            maxy: Annotated[float, Path(description="Bounding box max Y")],
            format: Annotated[
                RasterFormat,
                "Output image type.",
            ] = RasterFormat.png,
            layer_params=Depends(self.layer_dependency),
            img_params: PartFeatureParams = Depends(),
            dataset_params: DatasetParams = Depends(),
            render_params: ImageRenderingParams = Depends(),
            colormap: ColorMapParams = Depends(),
            dst_crs=Depends(DstCRSParams),
            coord_crs=Depends(CoordCRSParams),
            post_process=Depends(available_algorithms.dependency),
        ):
            """Create image from part of a dataset."""
            with self.reader(self.src_path, **self.reader_params) as src_dst:  # type: ignore
                if self.nodata is not None and dataset_params.nodata is None:
                    dataset_params.nodata = self.nodata

                # Adapt options for each reader type
                self._update_params(src_dst, layer_params)

                image = src_dst.part(
                    [minx, miny, maxx, maxy],
                    dst_crs=dst_crs,
                    bounds_crs=coord_crs or WGS84_CRS,
                    **layer_params.as_dict(),
                    **dataset_params.as_dict(),
                    **img_params.as_dict(),
                )
                dst_colormap = getattr(src_dst, "colormap", None)

            if post_process:
                image = post_process(image)

            content, media_type = render_image(
                image,
                output_format=format,
                colormap=colormap or dst_colormap,
                **render_params.as_dict(),
            )

            return Response(content, media_type=media_type)

        feature_params = {
            "responses": {
                200: {
                    "content": img_media_types,
                    "description": "Return part of a dataset defined by a geojson feature.",
                }
            },
            "response_class": Response,
            "description": "Return part of a dataset defined by a geojson feature.",
        }

        @self.router.post("/feature", **feature_params, tags=["API"])
        @self.router.post("/feature.{format}", **feature_params, tags=["API"])
        @self.router.post(
            "/feature/{width}x{height}.{format}", **feature_params, tags=["API"]
        )
        def geojson_part(
            geom: Feature,
            format: Annotated[Optional[RasterFormat], "Output image type."] = None,
            layer_params=Depends(self.layer_dependency),
            img_params: PartFeatureParams = Depends(),
            dataset_params: DatasetParams = Depends(),
            render_params: ImageRenderingParams = Depends(),
            colormap: ColorMapParams = Depends(),
            post_process=Depends(available_algorithms.dependency),
        ):
            """Handle /feature requests."""
            with self.reader(self.src_path, **self.reader_params) as src_dst:  # type: ignore
                if self.nodata is not None and dataset_params.nodata is None:
                    dataset_params.nodata = self.nodata

                # Adapt options for each reader type
                self._update_params(src_dst, layer_params)

                image = src_dst.feature(
                    geom.model_dump(exclude_none=True),
                    **layer_params.as_dict(),
                    **dataset_params.as_dict(),
                )
                dst_colormap = getattr(src_dst, "colormap", None)

            if post_process:
                image = post_process(image)

            content, media_type = render_image(
                image,
                output_format=format,
                colormap=colormap or dst_colormap,
                **render_params.as_dict(),
            )

            return Response(content, media_type=media_type)

        tile_params = {
            "responses": {
                200: {
                    "content": {**img_media_types, **mvt_media_types},
                    "description": "Return a tile.",
                }
            },
            "response_class": Response,
            "description": "Read COG and return a tile",
        }

        @self.router.get(
            "/tiles/WebMercatorQuad/{z}/{x}/{y}", **tile_params, tags=["API"]
        )
        @self.router.get(
            "/tiles/WebMercatorQuad/{z}/{x}/{y}.{format}", **tile_params, tags=["API"]
        )
        def tile(
            z: Annotated[
                int,
                Path(
                    description="Identifier (Z) selecting one of the scales defined in the TileMatrixSet and representing the scaleDenominator the tile.",
                ),
            ],
            x: Annotated[
                int,
                Path(
                    description="Column (X) index of the tile on the selected TileMatrix. It cannot exceed the MatrixHeight-1 for the selected TileMatrix.",
                ),
            ],
            y: Annotated[
                int,
                Path(
                    description="Row (Y) index of the tile on the selected TileMatrix. It cannot exceed the MatrixWidth-1 for the selected TileMatrix.",
                ),
            ],
            format: Annotated[TileFormat, "Output tile type."] = None,
            layer_params=Depends(self.layer_dependency),
            dataset_params: DatasetParams = Depends(),
            render_params: ImageRenderingParams = Depends(),
            tile_params: TileParams = Depends(),
            colormap: ColorMapParams = Depends(),
            feature_type: Annotated[
                Optional[Literal["point", "polygon"]],
                Query(title="Feature type (Only for MVT)"),
            ] = None,
            tilesize: Annotated[
                Optional[int],
                Query(description="Tile Size."),
            ] = None,
            post_process=Depends(available_algorithms.dependency),
        ):
            """Handle /tiles requests."""
            default_tilesize = 256

            if format and format in VectorTileFormat:
                default_tilesize = 128

            tilesize = tilesize or default_tilesize

            with self.reader(self.src_path, **self.reader_params) as src_dst:  # type: ignore
                if self.nodata is not None and dataset_params.nodata is None:
                    dataset_params.nodata = self.nodata

                # Adapt options for each reader type
                self._update_params(src_dst, layer_params)

                image = src_dst.tile(
                    x,
                    y,
                    z,
                    tilesize=tilesize,
                    **tile_params.as_dict(),
                    **layer_params.as_dict(),
                    **dataset_params.as_dict(),
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

                content = pixels_encoder(
                    image.data,
                    image.mask,
                    image.band_names,
                    feature_type=feature_type,
                )

                media_type = format.mediatype

            # Raster Tile
            else:
                if post_process:
                    image = post_process(image)

                content, media_type = render_image(
                    image,
                    output_format=format,
                    colormap=colormap or dst_colormap,
                    **render_params.as_dict(),
                )

            return Response(content, media_type=media_type)

        @self.router.get(
            "/tilejson.json",
            response_model=TileJSON,
            responses={200: {"description": "Return a tilejson"}},
            response_model_exclude_none=True,
            tags=["API"],
        )
        def tilejson(
            request: Request,
            tile_format: Annotated[
                Optional[TileFormat],
                "Output tile type.",
            ] = None,
            layer_params=Depends(self.layer_dependency),
            dataset_params: DatasetParams = Depends(),
            render_params: ImageRenderingParams = Depends(),
            colormap: ColorMapParams = Depends(),
            post_process=Depends(available_algorithms.dependency),
            feature_type: Annotated[
                Optional[Literal["point", "polygon"]],
                Query(title="Feature type (Only for MVT)"),
            ] = None,
            tilesize: Annotated[
                Optional[int],
                Query(description="Tile Size."),
            ] = None,
        ):
            """Handle /tilejson.json requests."""
            kwargs: Dict[str, Any] = {"z": "{z}", "x": "{x}", "y": "{y}"}
            if tile_format:
                kwargs["format"] = tile_format.value

            tile_url = str(request.url_for("tile", **kwargs))

            qs = [
                (key, value)
                for (key, value) in request.query_params._list
                if key not in ["tile_format"]
            ]
            if qs:
                tile_url += f"?{urllib.parse.urlencode(qs)}"

            with self.reader(self.src_path, **self.reader_params) as src_dst:  # type: ignore
                bounds = (
                    self.bounds
                    if self.bounds is not None
                    else src_dst.get_geographic_bounds(
                        src_dst.tms.rasterio_geographic_crs
                    )
                )
                minzoom = self.minzoom if self.minzoom is not None else src_dst.minzoom
                maxzoom = self.maxzoom if self.maxzoom is not None else src_dst.maxzoom

            return {
                "bounds": bounds,
                "minzoom": minzoom,
                "maxzoom": maxzoom,
                "name": "rio-viz",
                "tilejson": "2.1.0",
                "tiles": [tile_url],
            }

        @self.router.get(
            "/WMTSCapabilities.xml", response_class=XMLResponse, tags=["API"]
        )
        def wmts(
            request: Request,
            tile_format: Annotated[
                TileFormat,
                Query(description="Output image type. Default is png."),
            ] = RasterFormat.png,
            layer_params=Depends(self.layer_dependency),
            dataset_params: DatasetParams = Depends(),
            render_params: ImageRenderingParams = Depends(),
            colormap: ColorMapParams = Depends(),
            post_process=Depends(available_algorithms.dependency),
            feature_type: Annotated[
                Optional[Literal["point", "polygon"]],
                Query(title="Feature type (Only for MVT)"),
            ] = None,
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
            tiles_endpoint = str(request.url_for("tile", **kwargs))

            qs = [
                (key, value)
                for (key, value) in request.query_params._list
                if key not in ["tile_format", "REQUEST", "SERVICE"]
            ]
            if qs:
                tiles_endpoint += f"?{urllib.parse.urlencode(qs)}"

            with self.reader(self.src_path, **self.reader_params) as src_dst:  # type: ignore
                bounds = (
                    self.bounds
                    if self.bounds is not None
                    else src_dst.get_geographic_bounds(
                        src_dst.tms.rasterio_geographic_crs
                    )
                )
                minzoom = self.minzoom if self.minzoom is not None else src_dst.minzoom
                maxzoom = self.maxzoom if self.maxzoom is not None else src_dst.maxzoom

            tileMatrix = []
            for zoom in range(minzoom, maxzoom + 1):  # type: ignore
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
                request,
                name="wmts.xml",
                context={
                    "tiles_endpoint": tiles_endpoint,
                    "bounds": bounds,
                    "tileMatrix": tileMatrix,
                    "title": "Cloud Optimized GeoTIFF",
                    "layer_name": "cogeo",
                    "media_type": tile_format.mediatype,
                },
                media_type="application/xml",
            )

        @self.router.get("/map", response_class=HTMLResponse)
        def map_viewer(
            request: Request,
            tile_format: Annotated[
                Optional[RasterFormat],
                Query(description="Output raster tile type."),
            ] = None,
            layer_params=Depends(self.layer_dependency),
            dataset_params: DatasetParams = Depends(),
            render_params: ImageRenderingParams = Depends(),
            colormap: ColorMapParams = Depends(),
            post_process=Depends(available_algorithms.dependency),
            tilesize: Annotated[
                Optional[int],
                Query(description="Tile Size."),
            ] = None,
        ):
            """Return a simple map viewer."""
            tilejson_url = str(request.url_for("tilejson"))

            if request.query_params:
                tilejson_url += f"?{request.query_params}"

            return templates.TemplateResponse(
                request,
                name="map.html",
                context={
                    "tilejson_endpoint": tilejson_url,
                },
                media_type="text/html",
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
                request,
                name=name,
                context={
                    "tilejson_endpoint": str(request.url_for("tilejson")),
                    "stats_endpoint": str(request.url_for("statistics")),
                    "info_endpoint": str(request.url_for("info_geojson")),
                    "point_endpoint": str(request.url_for("point")),
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


@attr.s
class Client(viz):
    """Create a Client usable in Jupyter Notebook."""

    server: ServerThread = attr.ib(init=False)

    def __attrs_post_init__(self):
        """Update App."""
        super().__attrs_post_init__()

        key = f"{self.host}:{self.port}"
        if ServerManager.is_server_live(key):
            ServerManager.shutdown_server(key)

        self.server = ServerThread(self.app, port=self.port, host=self.host)
        ServerManager.add_server(key, self.server)

    def shutdown(self):
        """Stop server"""
        ServerManager.shutdown_server(f"{self.host}:{self.port}")
