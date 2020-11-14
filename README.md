# rio-viz

<p align="center">
  <img src="https://user-images.githubusercontent.com/10407788/60689165-78be7780-9e88-11e9-84b9-9a3602156ef2.jpg" style="max-width: 500px;"/>
  <p align="center">A Rasterio plugin to visualize Cloud Optimized GeoTIFF in browser.</p>
</p>

<p align="center">
  <a href="https://github.com/developmentseed/rio-viz/actions?query=workflow%3ACI" target="_blank">
      <img src="https://github.com/developmentseed/rio-viz/workflows/CI/badge.svg" alt="Test">
  </a>
  <a href="https://codecov.io/gh/developmentseed/rio-viz" target="_blank">
      <img src="https://codecov.io/gh/developmentseed/rio-viz/branch/master/graph/badge.svg" alt="Coverage">
  </a>
  <a href="https://pypi.org/project/rio-viz" target="_blank">
      <img src="https://img.shields.io/pypi/v/rio-viz?color=%2334D058&label=pypi%20package" alt="Package version">
  </a>
  <a href="https://github.com/developmentseed/rio-viz/blob/master/LICENSE" target="_blank">
      <img src="https://img.shields.io/github/license/developmentseed/rio-viz.svg" alt="Downloads">
  </a>
</p>


## Install

You can install rio-viz using pip

```bash
$ pip install rio-viz
```
with 3d feature

```bash
# 3d visualization features is optional, you'll need to have `cython==0.28` installed before being able to install `rio-viz["mvt"]`
$ pip install -U pip cython==0.28
$ pip install rio-viz["mvt"]
```

Built from source

```bash
$ git clone https://github.com/developmentseed/rio-viz.git
$ cd rio-viz
$ pip install -e .
```


## CLI

```bash
$ rio viz --help
Usage: rio viz [OPTIONS] SRC_PATH

  Rasterio Viz cli.

Options:
  --nodata NUMBER|nan        Set nodata masking values for input dataset.
  --minzoom INTEGER          Overwrite minzoom
  --maxzoom INTEGER          Overwrite maxzoom
  --style [satellite|basic]  Mapbox basemap
  --port INTEGER             Webserver port (default: 8080)
  --host TEXT                Webserver host url (default: 127.0.0.1)
  --mapbox-token TOKEN       Pass Mapbox token
  --no-check                 Ignore COG validation
  --reader TEXT              rio-tiler Reader (BaseReader or AsyncBaseReader). Default is `rio_tiler.io.COGReader`
  --layers TEXT              limit to specific layers (indexes, bands, assets)
  --server-only              Launch API without opening the rio-viz web-page.
  --config NAME=VALUE        GDAL configuration options.
  --help                     Show this message and exit.

```

## 3D (Experimental)

rio-viz supports Mapbox VectorTiles encoding from a raster array. This feature was added to visualize sparse data stored as raster but will also work for dense array. This is highly experimental and might be slow to render in certain browser and/or for big rasters.

![](https://user-images.githubusercontent.com/10407788/56853984-4713b800-68fd-11e9-86a2-efbb041daeb0.gif)


## Multi Reader support

rio-viz support multiple/custom reader as long they are subclass of `rio_tiler.io.base.BaseReader` or `rio_tiler.io.base.AsyncBaseReader`.

```bash
# MultiFiles
$ rio viz "cog_band{2,3,4}.tif" \
  --reader rio_viz.io.reader.MultiFilesReader

# Landsat 8 - rio-tiler-pds
$ rio viz LC08_L1TP_013031_20130930_20170308_01_T1 \
  --reader rio_tiler_pds.landsat.aws.landsat8.L8Reader \
  --layers B1,B2 \
  --config GDAL_DISABLE_READDIR_ON_OPEN=FALSE \
  --config CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".TIF,.ovr"

# aiocogeo
$ rio viz https://naipblobs.blob.core.windows.net/naip/v002/al/2019/al_60cm_2019/30087/m_3008701_ne_16_060_20191115.tif \
  --reader aiocogeo.tiler.COGTiler
```

## RestAPI

When launching rio-viz, the application will create a FastAPI application to access and read the data you want. By default the CLI will open a web-page for you to explore your file but you can use `--server-only` option to ignore this.

```bash
$ rio viz my.tif --server-only

# In another console
$ curl http://127.0.0.1:8080/info | jq
{
  "bounds": [6.608576517072109, 51.270642883468895, 11.649386808679436, 53.89267160832534],
  "band_metadata": [...],
  "band_descriptions": [...],
  "dtype": "uint8",
  "nodata_type": "Mask",
  "colorinterp": [
    "red",
    "green",
    "blue"
  ]
}
```

You can see the full API documentation over `http://127.0.0.1:8080/docs`

![API documentation](https://user-images.githubusercontent.com/10407788/99135093-a7a53b80-25ee-11eb-98ba-0ce932775791.png)


## Contribution & Development

See [CONTRIBUTING.md](https://github.com/developmentseed/rio-viz/blob/master/CONTRIBUTING.md)

## Authors

Created by [Development Seed](<http://developmentseed.org>)

## Changes

See [CHANGES.md](https://github.com/developmentseed/rio-viz/blob/master/CHANGES.md).

## License

See [LICENSE.txt](https://github.com/developmentseed/rio-viz/blob/master/LICENSE)
