import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError

from app.core import authentication as auth


@pytest.fixture(autouse=True)
def reset_jwks_cache(monkeypatch):
    # Each test starts with an empty module-level JWKS cache.
    monkeypatch.setattr(auth, "_jwks_cache", None)


def _creds(token: str = "tok") -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


class TestGetJwks:
    async def test_fetches_once_then_serves_from_cache(self, monkeypatch):
        calls = {"n": 0}

        async def fake_fetch():
            calls["n"] += 1
            return {"keys": [{"kid": "a"}]}

        monkeypatch.setattr(auth, "_fetch_jwks", fake_fetch)

        first = await auth.get_jwks()
        second = await auth.get_jwks()

        assert first == {"keys": [{"kid": "a"}]}
        assert second == first
        assert calls["n"] == 1  # second call served from cache

    async def test_force_refresh_refetches(self, monkeypatch):
        calls = {"n": 0}

        async def fake_fetch():
            calls["n"] += 1
            return {"keys": []}

        monkeypatch.setattr(auth, "_fetch_jwks", fake_fetch)

        await auth.get_jwks()
        await auth.get_jwks(force_refresh=True)
        assert calls["n"] == 2


class TestVerifyToken:
    async def test_refreshes_jwks_when_kid_unknown(self, monkeypatch):
        calls = {"n": 0}

        async def fake_fetch():
            calls["n"] += 1
            # First fetch has the old key; refresh returns the rotated key.
            return {"keys": [{"kid": "new"}]} if calls["n"] > 1 else {"keys": [{"kid": "old"}]}

        monkeypatch.setattr(auth, "_fetch_jwks", fake_fetch)
        monkeypatch.setattr(auth.jwt, "get_unverified_header", lambda token: {"kid": "new"})
        monkeypatch.setattr(
            auth.jwt,
            "decode",
            lambda *a, **k: {"sub": "user-1", "app_metadata": {"role": "admin"}, "email": "e@x.com"},
        )

        result = await auth.verify_token(_creds())

        assert result.sub == "user-1"
        assert result.role == "admin"
        assert calls["n"] == 2  # refreshed because 'new' kid was absent from the first set

    async def test_defaults_role_to_worker_when_absent(self, monkeypatch):
        async def fake_fetch():
            return {"keys": [{"kid": "old"}]}

        monkeypatch.setattr(auth, "_fetch_jwks", fake_fetch)
        monkeypatch.setattr(auth.jwt, "get_unverified_header", lambda token: {"kid": "old"})
        monkeypatch.setattr(auth.jwt, "decode", lambda *a, **k: {"sub": "user-1"})

        result = await auth.verify_token(_creds())
        assert result.role == "worker"

    async def test_invalid_token_raises_401(self, monkeypatch):
        async def fake_fetch():
            return {"keys": [{"kid": "old"}]}

        monkeypatch.setattr(auth, "_fetch_jwks", fake_fetch)
        monkeypatch.setattr(auth.jwt, "get_unverified_header", lambda token: {"kid": "old"})

        def boom(*a, **k):
            raise JWTError("bad signature")

        monkeypatch.setattr(auth.jwt, "decode", boom)

        with pytest.raises(HTTPException) as exc:
            await auth.verify_token(_creds())
        assert exc.value.status_code == 401

    async def test_missing_sub_raises_401(self, monkeypatch):
        async def fake_fetch():
            return {"keys": [{"kid": "old"}]}

        monkeypatch.setattr(auth, "_fetch_jwks", fake_fetch)
        monkeypatch.setattr(auth.jwt, "get_unverified_header", lambda token: {"kid": "old"})
        monkeypatch.setattr(auth.jwt, "decode", lambda *a, **k: {"app_metadata": {"role": "admin"}})

        with pytest.raises(HTTPException) as exc:
            await auth.verify_token(_creds())
        assert exc.value.status_code == 401
