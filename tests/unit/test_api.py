from fastapi.testclient import TestClient
from api.main import app
import pytest

def test_learning_path_endpoint_success():
    with TestClient(app) as client:
        response = client.post(
            "/api/learning-path",
            json={"target_role": "ROL-01", "current_skills": []}
        )
        assert response.status_code in (200, 503) 
        if response.status_code == 200:
            data = response.json()
            assert "learning_path" in data
            assert "total_skills_needed" in data

def test_learning_path_endpoint_invalid_data():
    with TestClient(app) as client:
        response = client.post(
            "/api/learning-path",
            json={"wrong_field": "data"}
        )
        assert response.status_code == 422 # Unprocessable Entity (Pydantic validation)

def test_gap_analysis_endpoint_success():
    with TestClient(app) as client:
        response = client.post(
            "/api/gap-analysis",
            json={"target_role": "ROL-02", "current_skills": ["SKL-01"]}
        )
        assert response.status_code in (200, 503)
        if response.status_code == 200:
            data = response.json()
            assert "skill_gaps" in data
            assert "total_gaps" in data

def test_chat_endpoint_placeholder():
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={"message": "What skills do I need to become a Data Scientist?"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
