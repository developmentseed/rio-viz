ARG PYTHON_VERSION=3.9

FROM python:${PYTHON_VERSION}-slim

RUN apt-get update

COPY rio_viz rio_viz
COPY pyproject.toml pyproject.toml
COPY README.md README.md

RUN pip install . rasterio>=1.3b1 --no-cache-dir --upgrade

# We add additional readers provided by rio-tiler-pds
RUN pip install rio-tiler-pds

ENV GDAL_INGESTED_BYTES_AT_OPEN 32768
ENV GDAL_DISABLE_READDIR_ON_OPEN EMPTY_DIR
ENV GDAL_HTTP_MERGE_CONSECUTIVE_RANGES YES
ENV GDAL_HTTP_MULTIPLEX YES
ENV GDAL_HTTP_VERSION 2
ENV VSI_CACHE TRUE
ENV VSI_CACHE_SIZE 536870912
