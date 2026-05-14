"""Tests for ingest preseed path resolution."""

from pathlib import Path

import yaml

from secretzero.config import ConfigLoader
from secretzero.ingest_preseed import secret_names_for_ingest_source


def test_secret_names_for_ingest_source_matches_relative_path(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    env_path = root / ".env"
    env_path.write_text("X=1\n", encoding="utf-8")
    sf_path = root / "Secretfile.yml"
    sf_path.write_text(
        yaml.dump(
            {
                "secrets": [
                    {
                        "name": "my_secret",
                        "kind": "static",
                        "config": {"default": "${MY_SECRET}"},
                        "targets": [
                            {
                                "provider": "local",
                                "kind": "file",
                                "config": {"path": ".env", "format": "dotenv", "key": "MY_SECRET"},
                            }
                        ],
                    },
                    {
                        "name": "other",
                        "kind": "random_string",
                        "config": {"length": 8, "charset": "hex"},
                        "targets": [
                            {
                                "provider": "local",
                                "kind": "file",
                                "config": {"path": "other.env", "format": "dotenv"},
                            }
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    loader = ConfigLoader()
    sf = loader.load_file(sf_path)
    names = secret_names_for_ingest_source(
        sf, source=env_path.resolve(), secretfile_dir=sf_path.parent
    )
    assert names == ["my_secret"]
