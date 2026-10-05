import os
from pathlib import Path
import sys
import tempfile


TEST_DIR = Path(tempfile.mkdtemp(prefix="medika-fastapi-test-"))
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
os.environ["DATABASE_URL"] = f"sqlite:///{(TEST_DIR / 'api.db').as_posix()}"
os.environ["AUTO_CREATE_TABLES"] = "true"
os.environ["AUTO_SEED"] = "true"
os.environ["JWT_SECRET"] = "test-secret-only-with-at-least-32-bytes"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def auth(client):
    passwords = {
        "admin": "Admin123!",
        "perawat": "Perawat123!",
        "apoteker": "Apoteker123!",
        "fakih": "Dokter123!",
        "alia": "Dokter123!",
        "pasien": "Pasien123!",
        "ratna": "Pasien123!",
        "siti": "Pasien123!",
    }

    def headers(account: str) -> dict[str, str]:
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": f"{account}@medikahusada.local",
                "password": passwords[account],
            },
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['accessToken']}"}

    return headers

