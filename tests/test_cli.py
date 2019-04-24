"""tests rio_viz.server."""

import os
import pytest

from mock import patch

from click.testing import CliRunner

from rio_viz.scripts.cli import viz

cog_path = os.path.join(os.path.dirname(__file__), "fixtures", "cog.tif")
noncog_path = os.path.join(os.path.dirname(__file__), "fixtures", "noncog.tif")


@pytest.fixture(autouse=True)
def testing_env_var(monkeypatch):
    """Set testing env variable."""
    monkeypatch.delenv("MAPBOX_ACCESS_TOKEN", raising=False)


@patch("rio_viz.server.TileServer")
@patch("click.launch")
def test_viz_valid(launch, TileServer):
    """Should work as expected."""
    TileServer.return_value.get_template_url.return_value = (
        "http://127.0.0.1:8080/index.html"
    )
    TileServer.return_value.start.return_value = True

    launch.return_value = True

    runner = CliRunner()
    result = runner.invoke(viz, [cog_path])
    TileServer.assert_called_once()
    assert not result.exception
    assert result.exit_code == 0


@patch("rio_viz.server.TileServer")
@patch("click.launch")
def test_viz_valid_style(launch, TileServer):
    """Should work as expected."""
    TileServer.return_value.get_playround_url.return_value = (
        "http://127.0.0.1:8080/playground.html"
    )
    TileServer.return_value.start.return_value = True

    launch.return_value = True

    runner = CliRunner()
    result = runner.invoke(viz, [cog_path, "--style", "satellite"])
    TileServer.assert_called_once()
    assert not result.exception
    assert result.exit_code == 0


@patch("rio_viz.server.TileServer")
@patch("click.launch")
def test_viz_validEnvToken(launch, TileServer, monkeypatch):
    """Should work as expected."""
    monkeypatch.setenv("MAPBOX_ACCESS_TOKEN", "pk.afakemapboxtoken")

    TileServer.return_value.get_template_url.return_value = (
        "http://127.0.0.1:8080/index.html"
    )
    TileServer.return_value.start.return_value = True

    launch.return_value = True

    runner = CliRunner()
    result = runner.invoke(viz, [cog_path])
    TileServer.assert_called_once()
    assert not result.exception
    assert result.exit_code == 0


@patch("rio_viz.server.TileServer")
@patch("click.launch")
def test_viz_validToken(launch, TileServer):
    """Should work as expected."""
    TileServer.return_value.get_template_url.return_value = (
        "http://127.0.0.1:8080/index.html"
    )
    TileServer.return_value.start.return_value = True

    launch.return_value = True

    runner = CliRunner()
    result = runner.invoke(viz, [cog_path, "--mapbox-token", "pk.afakemapboxtoken"])
    TileServer.assert_called_once()
    assert not result.exception
    assert result.exit_code == 0


@patch("rio_viz.server.TileServer")
@patch("click.launch")
def test_viz_validInvalidToken(launch, TileServer):
    """Should work as expected."""
    runner = CliRunner()
    result = runner.invoke(viz, [cog_path, "--mapbox-token", "sk.afakemapboxtoken"])
    TileServer.assert_not_called()
    launch.assert_not_called()
    assert result.exception
    assert result.exit_code == 1


@patch("rio_viz.server.TileServer")
@patch("click.launch")
def test_viz_invalidCog(launch, TileServer):
    """Should work as expected."""
    TileServer.return_value.start.return_value = True
    launch.return_value = True

    runner = CliRunner()
    result = runner.invoke(viz, [noncog_path])
    raster = TileServer.call_args[0][0]
    assert raster.path is not noncog_path
    TileServer.assert_called_once()
    assert not result.exception
    assert result.exit_code == 0
