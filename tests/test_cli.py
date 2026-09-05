from typer.testing import CliRunner

from tessera.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "tessera" in result.stdout.lower() or "1.0.0" in result.stdout


def test_detect_runs():
    result = runner.invoke(app, ["detect"])
    assert result.exit_code == 0
    assert "cpu" in result.stdout.lower() or "cpu" in result.output.lower()


def test_recommend_json():
    result = runner.invoke(app, ["recommend", "--json"])
    assert result.exit_code == 0
    assert "power" in result.stdout
