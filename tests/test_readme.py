from pathlib import Path


def test_readme_mentions_setup_and_run():
    text = Path("README.md").read_text(encoding="utf-8")
    assert "setup.sh" in text
    assert "python -m src.main run" in text
    assert "python -m src.main doctor" in text
    assert "python -m src.main devices" in text
