import json

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwcrypto import jwk, jwe

#TODO: expand configurable key pair encryption/decryption
def generate_key_pair(configured_exponent=65537,
                         configured_key_size=4096,
                         backend=default_backend(),
                         encoding=serialization.Encoding.PEM,
                         password: bytes = None,
                         private_format=serialization.PrivateFormat.PKCS8,
                         public_format=serialization.PublicFormat.SubjectPublicKeyInfo

                         ):
    private_key = rsa.generate_private_key(
        public_exponent=configured_exponent,
        key_size=configured_key_size,
        backend=backend
    )

    encoded_private_key = private_key.private_bytes(
        encoding=encoding,
        format=private_format,
        encryption_algorithm= serialization.NoEncryption() if password is None else serialization.BestAvailableEncryption(password),
    )

    encoded_public_key = private_key.public_key().public_bytes(
        encoding=encoding,
        format=public_format
    )

    return encoded_private_key, encoded_public_key


def check_key_pair(private_key_pem, public_key_pem, private_key_password=None):

    try:
        private_key = serialization.load_pem_private_key(
            private_key_pem,
            password=private_key_password,
            backend=default_backend()
        )

        derived_public_key = private_key.public_key()

        check_public_key = serialization.load_pem_public_key(
            public_key_pem,
            backend=default_backend()
        )

        if isinstance(private_key, rsa.RSAPrivateKey) and isinstance(check_public_key, rsa.RSAPublicKey):
            return derived_public_key.public_numbers().n == check_public_key.public_numbers().n and \
                derived_public_key.public_numbers().e == check_public_key.public_numbers().e

        return derived_public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ) == public_key_pem

    except ValueError:
        return False


def encrypt(public_key, json_text):
    public_jwk = jwk.JWK.from_pem(public_key)

    plaintext = json.dumps(json_text)

    token = jwe.JWE(
        plaintext.encode("utf-8"),
        protected={
            "alg": "RSA-OAEP-256",
            "enc": "A256GCM",
            "cty": "JWT"
        }
    )
    token.add_recipient(public_jwk)

    return token.serialize(compact=True)


def decrypt(private_key: bytes, encrypted_jwt: str, password: bytes | None = None) -> dict:
    private_jwk = jwk.JWK.from_pem(private_key, password=password)

    token = jwe.JWE()
    token.deserialize(encrypted_jwt, key=private_jwk)

    return json.loads(token.payload.decode("utf-8"))


if __name__ == "__main__":
    pwd = b"P@$$WRD"
    priv_key, pub_key = generate_key_pair(password=pwd)
    keys_match = check_key_pair(priv_key, pub_key, pwd)
    if keys_match:
        print("The public and private keys match.")
    else:
        print("The public and private keys do not match.")

    test_json = {
        "sub": "user123",
        "role": "admin",
        "scope": ["clipboard:read", "clipboard:write"]
    }

    print("Encrypting...")
    encrypted = encrypt(pub_key, json.dumps(test_json))
    print(f"Got encrypted result: \n\t{encrypted}")
    decrypted = decrypt(priv_key, encrypted, pwd)
    print(f"Got decrypted result: \n\t{decrypted}")

