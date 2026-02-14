from typer.testing import CliRunner

from app.cli.main import app


def test_heatmap_command_runs():
    runner = CliRunner()
    result = runner.invoke(app, ["heatmap", "--date", "2026-02-10", "--hour", "19"])
    assert result.exit_code == 0


def test_events_command_placeholder():
    runner = CliRunner()
    result = runner.invoke(app, ["events", "--date", "2026-02-10", "--from-hour", "18"])
    assert result.exit_code == 0
    assert "TODO" in result.stdout
