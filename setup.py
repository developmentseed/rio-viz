"""setup: rio-viz."""

from setuptools.extension import Extension
from setuptools import setup, find_packages
from Cython.Build import cythonize

import numpy

# Parse the version from the fiona module.
with open("rio_viz/__init__.py") as f:
    for line in f:
        if line.find("__version__") >= 0:
            version = line.split("=")[1].strip()
            version = version.strip('"')
            version = version.strip("'")
            continue

# Runtime requirements.
inst_reqs = ["tornado==4.5.3", "rio-tiler~=1.2", "click", "vtzero", "rio-cogeo"]

extra_reqs = {
    "test": ["mock", "pytest", "pytest-cov"],
    "dev": ["mock", "pytest", "pytest-cov", "pre-commit"],
}

ext_options = {"include_dirs": [numpy.get_include()]}
ext_modules = cythonize(
    [Extension("rio_viz.raster_to_mvt", ["rio_viz/raster_to_mvt.pyx"], **ext_options)]
)

setup(
    name="rio-viz",
    version=version,
    python_requires=">=3",
    description=u"Visualize Cloud Optimized GeoTIFF in browser",
    classifiers=[
        "Intended Audience :: Information Technology",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 3.6",
        "Topic :: Scientific/Engineering :: GIS",
    ],
    keywords="COG COGEO Rasterio GIS MVT",
    author=u"Vincent Sarago",
    author_email="vincent@developmentseed.org",
    url="https://github.com/developmentseed/rio-viz",
    packages=find_packages(exclude=["ez_setup", "examples", "tests"]),
    include_package_data=True,
    zip_safe=False,
    ext_modules=ext_modules,
    install_requires=inst_reqs,
    extras_require=extra_reqs,
    entry_points="""
      [rasterio.rio_plugins]
      viz=rio_viz.scripts.cli:viz
      """,
)
