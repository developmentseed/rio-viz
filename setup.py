"""setup: rio-viz."""

from setuptools import setup, find_packages

with open("README.md") as f:
    long_description = f.read()

# Runtime requirements.
inst_reqs = [
    "click",
    "rio-cogeo",
    "rio-tiler~=2.0a9",
    "rio-color",
    "fastapi",
    "uvicorn",
    "jinja2",
]

extra_reqs = {
    "mvt": ["rio-tiler-mvt"],
    "test": ["mock", "pytest", "pytest-cov", "pytest-asyncio", "requests"],
    "dev": ["mock", "pytest", "pytest-cov", "pytest-asyncio", "pre-commit"],
}

setup(
    name="rio-viz",
    version="0.2.3",
    python_requires=">=3",
    description=u"Visualize Cloud Optimized GeoTIFF in browser",
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Intended Audience :: Information Technology",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Scientific/Engineering :: GIS",
    ],
    keywords="COG COGEO Rasterio GIS MVT",
    author=u"Vincent Sarago",
    author_email="vincent@developmentseed.org",
    url="https://github.com/developmentseed/rio-viz",
    packages=find_packages(exclude=["ez_setup", "examples", "tests"]),
    include_package_data=True,
    zip_safe=False,
    license="MIT",
    install_requires=inst_reqs,
    extras_require=extra_reqs,
    entry_points="""
      [rasterio.rio_plugins]
      viz=rio_viz.scripts.cli:viz
      """,
)
