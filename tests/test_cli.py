"""tests rio_viz.server."""

import os
from unittest.mock import patch

from click.testing import CliRunner

from rio_viz.scripts.cli import viz

cog_path = os.path.join(os.path.dirname(__file__), "fixtures", "cog.tif")
noncog_path = os.path.join(os.path.dirname(__file__), "fixtures", "noncog.tif")


@patch("rio_viz.app.viz")
@patch("click.launch")
def test_viz_valid(launch, app):
    """Should work as expected."""
    app.return_value.get_template_url.return_value = "http://127.0.0.1:8080/index.html"
    app.return_value.start.return_value = True

    launch.return_value = True

    runner = CliRunner()
    result = runner.invoke(viz, [cog_path])
    app.assert_called_once()
    assert not result.exception
    assert result.exit_code == 0


@patch("rio_viz.app.viz")
@patch("click.launch")
def test_viz_invalidCog(launch, app):
    """Should work as expected."""
    app.return_value.start.return_value = True
    launch.return_value = True

    runner = CliRunner()
    result = runner.invoke(viz, [noncog_path])
    assert app.call_args[0] is not noncog_path
    app.assert_called_once()
    assert not result.exception
    assert result.exit_code == 0
