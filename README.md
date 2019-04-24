# rio-viz

[![CircleCI](https://circleci.com/gh/developmentseed/rio-viz.svg?style=svg&circle-token=4e1d294fbe0e9f1ad874a013434b91d22111b35e)](https://circleci.com/gh/developmentseed/rio-viz)

Rasterio plugin to visualize Cloud Optimized GeoTIFF in browser.

![](https://user-images.githubusercontent.com/10407788/56367726-e4674180-61c3-11e9-86e4-c8825cc75677.png)


Freely adapted from the great [mapbox/rio-glui](github.com/mapbox/rio-glui)

### Install

```
$ git clone https://github.com/developmentseed/rio-viz.git
$ cd rio-viz
$ pip install -e .
```

### How To

```bash 
$ rio viz --help
Usage: rio viz [OPTIONS] SRC_PATH

  Rasterio Viz cli.

Options:
  --style [satellite|basic]  Mapbox basemap
  --port INTEGER             Webserver port (default: 8080)
  --mapbox-token TOKEN       Pass Mapbox token
  --no-check                 Ignore COG validation
  --help                     Show this message and exit
```

### Docker

You can use rio-viz directly from a docker container

```bash
$ docker-compose build viz
$ file=myfile.tif style=satellite docker-compose up
```