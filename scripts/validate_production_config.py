"""Validate a production environment file without printing configuration values."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.production_security import production_config_errors


def read_environment(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not key.strip().isidentifier() or key.strip() in values:
            raise ValueError("environment file has malformed or duplicate assignments")
        value = value.strip()
        if value[:1] in {"'", '"'}:
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError("environment file has malformed quoting")
            value = value[1:-1]
        values[key.strip()] = value
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment-file", type=Path)
    parser.add_argument("--require-production", action="store_true")
    args = parser.parse_args()
    try:
        values = read_environment(args.environment_file) if args.environment_file else dict(os.environ)
        errors = production_config_errors(values)
        if args.require_production and values.get("APP_ENV") != "prod":
            errors.append("APP_ENV must be prod for production deployment")
        if errors:
            raise ValueError("; ".join(errors))
    except (ValueError, OSError) as error:
        message = str(error) if isinstance(error, ValueError) else "environment file unavailable"
        raise SystemExit(f"Production preflight failed: {message}") from None
    print("Production configuration validation passed")


if __name__ == "__main__":
    main()
