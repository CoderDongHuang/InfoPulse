"""Acceptance labels must follow the backend instance, not the browser port."""
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.main import app, settings


class EnvironmentNoticeTests(unittest.TestCase):
    def test_health_explicitly_labels_acceptance_instances(self):
        with patch.object(settings, "ACCEPTANCE_MODE", True):
            response = TestClient(app).get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.json()["acceptance_mode"], True)

    def test_normal_instance_never_claims_acceptance_mode(self):
        with patch.object(settings, "ACCEPTANCE_MODE", False):
            response = TestClient(app).get("/api/v1/health")
        self.assertIs(response.json()["acceptance_mode"], False)
