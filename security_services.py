"""Cryptographic helpers: RSA key generation, JWE for JSON, Fernet file encryption, and zip key archives."""
# Copyright (c) 2026 Gheorghii Mosin
# Licensed under the MIT License
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, cast

import pyzipper
from cryptography import fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from jwcrypto import jwe, jwk


def generate_key_pair(
    configured_exponent: int = 65537,
    configured_key_size: int = 4096,
    backend=default_backend(),
    encoding=serialization.Encoding.PEM,
    password: bytes | None = None,
    private_format=serialization.PrivateFormat.PKCS8,
    public_format=serialization.PublicFormat.SubjectPublicKeyInfo,
) -> tuple[bytes, bytes]:
    """Generate an RSA keypair and return ``(private_pem, public_pem)``.

    When *password* is set, the private key PEM is encrypted with best-available PKCS#8 encryption.
    """
    private_key = rsa.generate_private_key(
        public_exponent=configured_exponent,
        key_size=configured_key_size,
        backend=backend,
    )

    encoded_private_key = private_key.private_bytes(
        encoding=encoding,
        format=private_format,
        encryption_algorithm=(
            serialization.NoEncryption()
            if password is None
            else serialization.BestAvailableEncryption(password)
        ),
    )

    encoded_public_key = private_key.public_key().public_bytes(
        encoding=encoding,
        format=public_format,
    )

    return encoded_private_key, encoded_public_key


def package_keys(
    private_key: bytes,
    public_key: bytes,
    archive_path,
    private_key_name: str = "private_key.pem",
    public_key_name: str = "public_key.pem",
    archive_password: bytes | None = None,
):
    """Write *private_key* and *public_key* into an AES-encrypted zip at *archive_path*."""
    archive_path = Path(archive_path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    with pyzipper.AESZipFile(
        archive_path,
        "w",
        compression=pyzipper.ZIP_DEFLATED,
    ) as zf:
        if archive_password is not None:
            zf.setpassword(archive_password)
            zf.setencryption(pyzipper.WZ_AES, nbits=256)

        zf.writestr(private_key_name, private_key)
        zf.writestr(public_key_name, public_key)

    return archive_path

def unpack_keys(
    archive_path,
    destination_dir=".",
    archive_password: bytes | None = None,
) -> list[Path]:
    """Extract a key archive into *destination_dir*, blocking zip-slip paths.

    Returns paths to extracted files (directories in the archive are skipped).
    """
    archive_path = Path(archive_path)
    destination_dir = Path(destination_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    dest_root = destination_dir.resolve()

    extracted: list[Path] = []
    with pyzipper.AESZipFile(archive_path) as zf:
        if archive_password is not None:
            zf.setpassword(archive_password)
        for name in zf.namelist():
            if not name or name.endswith("/"):
                continue
            if ".." in Path(name).parts:
                raise ValueError(f"Unsafe archive entry: {name!r}")
            out_path = (destination_dir / name).resolve()
            if out_path != dest_root and dest_root not in out_path.parents:
                raise ValueError(f"Archive entry escapes destination: {name!r}")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name, "r") as src, open(out_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted.append(out_path)
    return extracted

def check_key_pair(
    private_key_pem: bytes,
    public_key_pem: bytes,
    private_key_password: bytes | None = None,
) -> bool:
    """Return True if *public_key_pem* matches the public half of *private_key_pem*."""
    try:
        private_key = serialization.load_pem_private_key(
            private_key_pem,
            password=private_key_password,
            backend=default_backend(),
        )

        derived_public_key = private_key.public_key()

        check_public_key = serialization.load_pem_public_key(
            public_key_pem,
            backend=default_backend(),
        )

        if isinstance(private_key, rsa.RSAPrivateKey) and isinstance(check_public_key, rsa.RSAPublicKey):
            return (
                derived_public_key.public_numbers().n == check_public_key.public_numbers().n
                and derived_public_key.public_numbers().e == check_public_key.public_numbers().e
            )

        return derived_public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ) == public_key_pem

    except ValueError:
        return False


def encrypt_text(public_key: bytes, json_text) -> str:
    """JWE-encrypt JSON-serializable *json_text* for the RSA public key in *public_key* (compact serialization)."""
    public_jwk = jwk.JWK.from_pem(public_key)
    plaintext = json.dumps(json_text)

    protected_header = cast(Any, {
        "alg": "RSA-OAEP-256",
        "enc": "A256GCM",
        "cty": "JWT",
    })

    token = jwe.JWE(
        plaintext.encode("utf-8"),
        protected=protected_header,
    )
    token.add_recipient(public_jwk)

    return token.serialize(compact=True)


def decrypt_text(
    private_key: bytes,
    encrypted_jwt: str,
    password: bytes | None = None,
) -> dict:
    """Decrypt a compact JWE produced by :func:`encrypt_text` and parse the payload as JSON."""
    private_jwk = jwk.JWK.from_pem(private_key, password=password)

    token = jwe.JWE()
    token.deserialize(encrypted_jwt, key=private_jwk)

    return json.loads(token.payload.decode("utf-8"))


def encrypt_file(public_key: bytes, file_path: Path) -> str | None:
    """Encrypt *file_path* with a random Fernet key, wrap the key with RSA-OAEP, write ``*.enc`` beside the file."""

    file_key = fernet.Fernet.generate_key()
    fernet_file = fernet.Fernet(file_key)

    with open(file_path, "rb") as f:
        original_data = f.read()
    encrypted_data = fernet_file.encrypt(original_data)

    rsa_public_key: rsa.RSAPublicKey = serialization.load_pem_public_key(public_key)
    encrypted_file_key = rsa_public_key.encrypt(
        file_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    file_path = Path(file_path)
    encrypted_file_path = f"{file_path}.enc"
    with open(encrypted_file_path, "wb") as f:
        f.write(len(encrypted_file_key).to_bytes(4, 'big'))  # Store key length
        f.write(encrypted_file_key)
        f.write(encrypted_data)

    if Path(encrypted_file_path).exists():
        return encrypted_file_path
    else:
        return None


def decrypt_file(private_key: bytes, key_pass: bytes, encrypted_file_path: str) -> str | None:
    """Inverse of :func:`encrypt_file`; writes plaintext next to the ``.enc`` file and returns that path."""
    with open(encrypted_file_path, "rb") as f:
        print(f"Attempting to decrypt: {encrypted_file_path}")
        key_length = int.from_bytes(f.read(4), 'big')
        encrypted_file_key = f.read(key_length)
        encrypted_data = f.read()

    rsa_private_key: rsa.RSAPrivateKey = serialization.load_pem_private_key(
        private_key,
        password=key_pass,
    )
    file_key = rsa_private_key.decrypt(
        encrypted_file_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

    f = fernet.Fernet(file_key)
    decrypted_data = f.decrypt(encrypted_data)

    decrypted_file_path = encrypted_file_path.removesuffix(".enc")

    with open(decrypted_file_path, "wb") as f:
        f.write(decrypted_data)

    if Path(decrypted_file_path).exists():
        return decrypted_file_path
    else:
        return None
