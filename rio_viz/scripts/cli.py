"""rio_viz.cli."""

import os
import tempfile
from contextlib import contextmanager, ExitStack

import numpy

import click
from rio_viz import app, raster

from rio_cogeo.cogeo import cog_validate, cog_translate
from rio_cogeo.profiles import cog_profiles


@contextmanager
def TemporaryRasterFile(dst_path, suffix=".tif"):
    """Create temporary file."""
    fileobj = tempfile.NamedTemporaryFile(
        dir=os.path.dirname(dst_path), suffix=suffix, delete=False
    )
    fileobj.close()
    try:
        yield fileobj
    finally:
        os.remove(fileobj.name)


class MbxTokenType(click.ParamType):
    """Mapbox token type."""

    name = "token"

    def convert(self, value, param, ctx):
        """Validate token."""
        try:
            if not value:
                return ""

            assert value.startswith("pk")
            return value

        except (AttributeError, AssertionError):
            raise click.ClickException(
                "Mapbox access token must be public (pk). "
                "Please sign up at https://www.mapbox.com/signup/ to get a public token. "
                "If you already have an account, you can retreive your "
                "token at https://www.mapbox.com/account/."
            )


class NodataParamType(click.ParamType):
    """Nodata inddex type."""

    name = "nodata"

    def convert(self, value, param, ctx):
        """Validate and parse band index."""
        try:
            if value.lower() == "nan":
                return numpy.nan
            elif value.lower() in ["nil", "none", "nada"]:
                return None
            else:
                return float(value)
        except (TypeError, ValueError):
            raise click.ClickException("{} is not a valid nodata value.".format(value))


@click.command()
@click.argument("src_paths", type=str, nargs=-1, required=True)
@click.option(
    "--nodata",
    type=NodataParamType(),
    metavar="NUMBER|nan",
    help="Set nodata masking values for input dataset.",
)
@click.option(
    "--minzoom", type=int, help="Overwrite minzoom",
)
@click.option(
    "--maxzoom", type=int, help="Overwrite maxzoom",
)
@click.option(
    "--style",
    type=click.Choice(["satellite", "basic"]),
    default="basic",
    help="Mapbox basemap",
)
@click.option("--port", type=int, default=8080, help="Webserver port (default: 8080)")
@click.option(
    "--host",
    type=str,
    default="127.0.0.1",
    help="Webserver host url (default: 127.0.0.1)",
)
@click.option(
    "--mapbox-token",
    type=MbxTokenType(),
    metavar="TOKEN",
    default=lambda: os.environ.get("MAPBOX_ACCESS_TOKEN", ""),
    help="Pass Mapbox token",
)
@click.option("--no-check", is_flag=True, help="Ignore COG validation")
@click.option("--simple", is_flag=True, default=False, help="Launch simple viewer")
def viz(
    src_paths,
    nodata,
    minzoom,
    maxzoom,
    style,
    port,
    host,
    mapbox_token,
    no_check,
    simple,
):
    """Rasterio Viz cli."""
    # Check if cog
    src_paths = list(src_paths)
    with ExitStack() as ctx:
        for ii, src_path in enumerate(src_paths):
            if not no_check and not cog_validate(src_path):
                # create tmp COG
                click.echo("create temporaty COG")
                tmp_path = ctx.enter_context(TemporaryRasterFile(src_path))

                output_profile = cog_profiles.get("deflate")
                output_profile.update(dict(blockxsize="256", blockysize="256"))
                config = dict(
                    GDAL_TIFF_INTERNAL_MASK=os.environ.get(
                        "GDAL_TIFF_INTERNAL_MASK", True
                    ),
                    GDAL_TIFF_OVR_BLOCKSIZE="128",
                )
                cog_translate(src_path, tmp_path.name, output_profile, config=config)
                src_paths[ii] = tmp_path.name

        src_dst = raster.RasterTiles(
            src_paths, nodata=nodata, minzoom=minzoom, maxzoom=maxzoom
        )
        application = app.viz(
            src_dst, token=mapbox_token, port=port, host=host, style=style
        )
        url = (
            application.get_simple_template_url()
            if simple
            else application.get_template_url()
        )
        click.echo(f"Viewer started at {url}", err=True)
        click.launch(url)
        application.start()
