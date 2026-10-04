"""Generate a VAPID pair into a new private file. Never print the keys or overwrite an existing file."""

import argparse
import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New .env file path, kept out of source control")
    parser.add_argument("--subject", default="mailto:notifications@clastio.online")
    args = parser.parse_args()
    key = ec.generate_private_key(ec.SECP256R1())
    encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")  # noqa: E731
    private = encode(key.private_numbers().private_value.to_bytes(32, "big"))
    public = encode(key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
    if "\n" in args.subject or "\r" in args.subject:
        parser.error("Subject must be a single contact URL")
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write(f"WEB_PUSH_PUBLIC_KEY={public}\nWEB_PUSH_PRIVATE_KEY={private}\nWEB_PUSH_SUBJECT={args.subject}\n")
    print(f"Wrote Web Push settings to {args.output}. Copy these into the API and scheduler environments; keep the file private.")


if __name__ == "__main__":
    main()
