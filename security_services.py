from __future__ import annotations

import json
from pathlib import Path
from typing import cast, Any, Iterable

import pyzipper
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from jwcrypto import jwk, jwe

from cryptography.fernet import Fernet

def generate_key_pair(
    configured_exponent: int = 65537,
    configured_key_size: int = 4096,
    backend=default_backend(),
    encoding=serialization.Encoding.PEM,
    password: bytes | None = None,
    private_format=serialization.PrivateFormat.PKCS8,
    public_format=serialization.PublicFormat.SubjectPublicKeyInfo,
) -> tuple[bytes, bytes]:
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
    archive_password: bytes = None,
):
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

def unpack_keys(archive_path,
                destination_dir=".",
                archive_password: bytes = None):
    archive_path = Path(archive_path)
    destination_dir = Path(destination_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)

    with pyzipper.AESZipFile(archive_path) as zf:
        if archive_password is not None:
            zf.setpassword(archive_password)
        zf.extractall(destination_dir)
        return [destination_dir / name for name in zf.namelist()]

def check_key_pair(
    private_key_pem: bytes,
    public_key_pem: bytes,
    private_key_password: bytes | None = None,
) -> bool:
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
    private_jwk = jwk.JWK.from_pem(private_key, password=password)

    token = jwe.JWE()
    token.deserialize(encrypted_jwt, key=private_jwk)

    return json.loads(token.payload.decode("utf-8"))


def encrypt_file(public_key: rsa.RSAPublicKey, file_path: Path) -> str | None:
    # encrypts the file before sending

    file_key = Fernet.generate_key()
    fernet = Fernet(Fernet.generate_key())

    with open(file_path, "rb") as f:
        original_data = f.read()
    encrypted_data = fernet.encrypt(original_data)

    encrypted_file_key = public_key.encrypt(
        file_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
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


def decrypt_file(private_key: rsa.RSAPrivateKey, encrypted_file_path: str) -> str | None:
    with open(encrypted_file_path, "rb") as f:
        key_length = int.from_bytes(f.read(4), 'big')
        encrypted_file_key = f.read(key_length)
        encrypted_data = f.read()

    file_key = private_key.decrypt(
        encrypted_file_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

    fernet = Fernet(file_key)
    decrypted_data = fernet.decrypt(encrypted_data)

    decrypted_file_path = encrypted_file_path.removesuffix(".enc")

    with open(decrypted_file_path, "wb") as f:
        f.write(decrypted_data)

    if Path(decrypted_file_path).exists():
        return decrypted_file_path
    else:
        return None
