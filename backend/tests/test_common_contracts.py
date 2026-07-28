"""Tests for shared API response contracts."""

import unittest

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.errors import AppError, setup_error_handlers
from app.schemas.common import Page


class CommonContractTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        setup_error_handlers(app)

        @app.get("/app-error")
        async def app_error():
            raise AppError("THING_CONFLICT", "对象冲突", 409, {"field": "name"})

        @app.get("/http-error")
        async def http_error():
            raise HTTPException(status_code=404, detail="对象不存在")

        @app.get("/validate")
        async def validate(page: int):
            return {"page": page}

        self.client = TestClient(app)

    def test_app_error_has_stable_shape_and_request_id(self):
        response = self.client.get("/app-error", headers={"X-Request-ID": "test-request"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "THING_CONFLICT")
        self.assertEqual(response.json()["error"]["diagnostic_id"], "test-request")
        self.assertEqual(response.headers["X-Request-ID"], "test-request")

    def test_http_error_is_normalized(self):
        response = self.client.get("/http-error")
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")

    def test_validation_error_lists_fields(self):
        response = self.client.get("/validate?page=wrong")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(response.json()["error"]["details"][0]["field"], "query.page")

    def test_page_contract(self):
        page = Page[str](items=["a"], page=1, page_size=20, total=21, has_more=True)
        self.assertTrue(page.has_more)


if __name__ == "__main__":
    unittest.main()
