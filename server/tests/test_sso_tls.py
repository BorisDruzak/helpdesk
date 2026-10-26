"""An internal IdP CA is trusted explicitly on every OIDC HTTP surface."""
from datetime import datetime, timedelta, timezone
import ipaddress
import ssl

from aiohttp import web
from aiohttp.test_utils import TestServer
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
import httpx
import pytest

import auth.oidc as oidc
import config


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_oidc_private_ca_tls_discovery_jwks_exchange_refresh_introspection(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Disposable test root")])
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1)).add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=True, crl_sign=True,
            encipher_only=None, decipher_only=None), critical=True)
        .sign(ca_key, hashes.SHA256()))
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
        .issuer_name(ca_name).public_key(leaf_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(leaf_key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
        .sign(ca_key, hashes.SHA256()))
    ca_file, cert_file, key_file = tmp_path / "root-ca.pem", tmp_path / "leaf.pem", tmp_path / "leaf-key.pem"
    ca_file.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    cert_file.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(leaf_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                serialization.NoEncryption()))
    server_tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_tls.load_cert_chain(cert_file, key_file)
    app = web.Application()
    requests = []
    async def discovery(request):
        origin = str(server.make_url("/")).rstrip("/")
        return web.json_response(dict(issuer=origin, code_challenge_methods_supported=["S256"],
            authorization_endpoint=origin + "/auth", token_endpoint=origin + "/token",
            jwks_uri=origin + "/certs", introspection_endpoint=origin + "/introspect"))
    async def certs(request):
        requests.append("jwks")
        return web.json_response({"keys": []})
    async def token(request):
        form = await request.post()
        requests.append(form["grant_type"])
        return web.json_response({"access_token": "disposable-access", "refresh_token": "disposable-refresh",
                                  "token_type": "Bearer", "expires_in": 60})
    async def introspect(request):
        requests.append("introspection")
        return web.json_response({"active": True})
    app.router.add_get("/.well-known/openid-configuration", discovery)
    app.router.add_get("/certs", certs)
    app.router.add_post("/token", token)
    app.router.add_post("/introspect", introspect)
    server = TestServer(app)
    await server.start_server(ssl=server_tls)
    try:
        origin = str(server.make_url("/")).rstrip("/")
        monkeypatch.setattr(config, "OIDC_ISSUER", origin)
        monkeypatch.setattr(config, "OIDC_CLIENT_ID", "test-client")
        monkeypatch.setattr(config, "OIDC_CLIENT_SECRET", "test-only-secret")
        monkeypatch.setattr(config, "OIDC_REDIRECT_URI", "https://helpdesk.example/api/web/session/oidc/callback")
        monkeypatch.setattr(config, "OIDC_CA_FILE", "")
        # System trust does not accidentally accept the generated private CA.
        with pytest.raises(httpx.ConnectError):
            await oidc._json(origin + "/.well-known/openid-configuration")
        monkeypatch.setattr(config, "OIDC_CA_FILE", str(ca_file))
        meta = await oidc._json(origin + "/.well-known/openid-configuration")
        assert meta["issuer"] == origin
        assert await oidc._json(meta["jwks_uri"]) == {"keys": []}
        async with oidc.oauth_client() as client:
            assert (await client.fetch_token(meta["token_endpoint"], code="disposable-code", code_verifier="x" * 64))["access_token"] == "disposable-access"
            assert (await client.refresh_token(meta["token_endpoint"], refresh_token="disposable-refresh"))["refresh_token"] == "disposable-refresh"
            assert (await client.introspect_token(meta["introspection_endpoint"], token="disposable-access")).json()["active"] is True
        assert requests == ["jwks", "authorization_code", "refresh_token", "introspection"]
        monkeypatch.setattr(config, "OIDC_CA_FILE", str(tmp_path / "missing-ca.pem"))
        with pytest.raises(FileNotFoundError):
            oidc.oauth_client()
    finally:
        await server.close()
