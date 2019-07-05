"""rio_viz app."""

from typing import BinaryIO, Union, Tuple

import re
import urllib

import numpy

from rio_viz import version as rioviz_version
from rio_viz.templates.viewer import viewer_template
from rio_viz.raster import postprocess_tile

from rio_tiler.profiles import img_profiles
from rio_tiler.utils import array_to_image, get_colormap

from starlette.requests import Request
from starlette.responses import Response, HTMLResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from fastapi import FastAPI, Path, Query
import uvicorn


def TileResponse(content: BinaryIO, media_type: str) -> Response:
    """Binary tile response."""
    headers = {"Content-Type": media_type}
    return Response(
        content=content, status_code=200, headers=headers, media_type=media_type
    )


class viz(object):
    """Creates a very minimal slippy map tile server using tornado.ioloop."""

    def __init__(
        self, raster, token: str = None, port: int = 8080, style: str = "satellite"
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
        async def mvt(
            z: int,
            x: int,
            y: int,
            tilesize: int = 128,
            nodata: Union[str, int, float] = None,
            feature_type: str = Query(
                None, title="Feature type", regex="^(point)|(polygon)$"
            ),
            resampling_method: str = Query("nearest", title="rasterio resampling"),
        ):
            """Handle /tiles requests."""
            if nodata is not None:
                nodata = numpy.nan if nodata == "nan" else float(nodata)

            tile = self.raster.read_tile_mvt(
                z,
                x,
                y,
                tilesize=tilesize,
                nodata=nodata,
                resampling_method=resampling_method,
                feature_type=feature_type,
            )

            return TileResponse(tile, media_type="application/x-protobuf")

        @self.app.get(
            "/tiles/{z}/{x}/{y}\\.{ext}",
            responses={
                200: {
                    "content": {"image/png": {}, "image/jpg": {}, "image/webp": {}},
                    "description": "Return an image.",
                }
            },
            description="Read COG and return a tile",
        )
        async def tile(
            z: int,
            x: int,
            y: int,
            ext: str = Path(..., regex="^(png)|(jpg)|(webp)$"),
            scale: int = 1,
            indexes: str = Query(None, title="Coma (',') delimited band indexes"),
            nodata: Union[str, int, float] = None,
            rescale: str = Query(None, title="Coma (',') delimited Min,Max bounds"),
            color_formula: str = Query(None, title="rio-color formula"),
            color_map: str = Query(None, title="rio-tiler color map names"),
            resampling_method: str = Query("bilinear", title="rasterio resampling"),
        ):
            """Handle /tiles requests."""
            if isinstance(indexes, str):
                indexes = tuple(int(s) for s in re.findall(r"\d+", indexes))

            if nodata is not None:
                nodata = numpy.nan if nodata == "nan" else float(nodata)

            tilesize = scale * 256
            tile, mask = self.raster.read_tile(
                z,
                x,
                y,
                tilesize=tilesize,
                indexes=indexes,
                nodata=nodata,
                resampling_method=resampling_method,
            )

            rtile, _ = postprocess_tile(
                tile, mask, rescale=rescale, color_formula=color_formula
            )

            if color_map:
                color_map = get_colormap(color_map, format="gdal")

            driver = "jpeg" if ext == "jpg" else ext
            options = img_profiles.get(driver, {})
            img = array_to_image(
                rtile, mask, img_format=driver, color_map=color_map, **options
            )
            return TileResponse(img, media_type=f"image/{ext}")

        @self.app.get(
            "/tilejson.json",
            responses={200: {"description": "Return a tilejson map metadata."}},
        )
        def tilejson(
            request: Request,
            response: Response,
            tile_format: str = Query("png", regex="^(png)|(jpg)|(webp)|(pbf)$"),
        ):
            """Handle /tilejson.json requests."""
            host = request.headers["host"]
            scheme = request.url.scheme
            kwargs = dict(request.query_params)
            kwargs.pop("tile_format", None)

            qs = urllib.parse.urlencode(list(kwargs.items()))
            tile_url = f"{scheme}://{host}/tiles/{{z}}/{{x}}/{{y}}.{tile_format}"
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
        def metadata(
            response: Response,
            pmin: float = 2.0,
            pmax: float = 98.0,
            nodata: Union[str, int, float] = None,
            indexes: str = Query(None, title="Coma (',') delimited band indexes"),
        ):
            """Handle /metadata requests."""
            if isinstance(indexes, str):
                indexes = tuple(int(s) for s in re.findall(r"\d+", indexes))

            if nodata is not None:
                nodata = numpy.nan if nodata == "nan" else float(nodata)

            return self.raster.metadata(
                pmin=pmin, pmax=pmax, nodata=nodata, indexes=indexes
            )

        @self.app.get(
            "/point", responses={200: {"description": "Return a point value."}}
        )
        def point(response: Response, coordinates: str):
            """Handle /point requests."""
            coordinates = list(map(float, coordinates.split(",")))

            return self.raster.point(coordinates)

        @self.app.get(
            "/index.html",
            responses={200: {"description": "Simple COG viewer."}},
            response_class=HTMLResponse,
        )
        def viewer():
            """Handle /requests."""
            return viewer_template(
                f"http://127.0.0.1:{self.port}",
                mapbox_access_token=self.token,
                mapbox_style=self.style,
            )

    def get_endpoint_url(self) -> str:
        """Get endpoint url."""
        return "http://127.0.0.1:{}".format(self.port)

    def get_template_url(self) -> str:
        """Get simple app template url."""
        return "http://127.0.0.1:{}/index.html".format(self.port)

    def get_bounds(self) -> str:
        """Get RasterTiles bounds."""
        return self.raster.bounds

    def get_center(self) -> Tuple:
        """Get RasterTiles center."""
        return self.raster.center

    def start(self):
        """Start tile server."""
        uvicorn.run(app=self.app, host="127.0.0.1", port=self.port, log_level="warning")
