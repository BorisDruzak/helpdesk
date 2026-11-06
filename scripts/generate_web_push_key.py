"""Provision one VAPID P-256 PEM without printing or overwriting its secret."""
import argparse
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Private PEM path outside the checkout/release directory")
    args = parser.parse_args()
    target = args.output.resolve()
    workspace = Path(__file__).resolve().parents[1]
    if target.is_relative_to(workspace):
        parser.error("Store the private key outside the checkout/release directory")
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(pem)
    print("Web Push private key created. Configure the key-file path and contact subject; keep this file private.")


if __name__ == "__main__":
    main()
