"""Consumer schemas must bind to Git bytes across Windows/Linux checkouts."""
import hashlib
import json
from pathlib import Path
import subprocess

import pytest
from scripts.generate_endpoint_tool_contracts import FILES, render

pytestmark = pytest.mark.no_db


def test_schema_digests_use_committed_bytes_even_with_crlf_checkout(tmp_path):
    provider = tmp_path / "provider"
    provider.mkdir()
    def git(*args):
        return subprocess.check_output(["git", "-C", str(provider), *args])
    git("init", "-q")
    git("config", "user.name", "Contract test")
    git("config", "user.email", "contract-test@example.test")
    git("config", "core.autocrlf", "true")
    folder = provider / "contracts/jsonschema"
    folder.mkdir(parents=True)
    for index, filename in enumerate(FILES):
        schema = {"title": f"Fixture{index}", "type": "object", "properties": {"value": {"type": "string"}},
                  "required": ["value"], "additionalProperties": False}
        (folder / filename).write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8", newline="\r\n")
    git("add", "--", "contracts/jsonschema")
    git("commit", "-qm", "test: seed canonical schemas")
    _, digests = render(provider)
    decoded = json.loads(digests)
    for filename in FILES:
        expected = hashlib.sha256(git("show", "HEAD:contracts/jsonschema/" + filename)).hexdigest()
        assert decoded[filename] == expected
