"""
RepoMind — Phase 7 API Tests

Tests for:
    - Exception hierarchy
    - Auth middleware (dev mode)
    - FirebaseService (in-memory mode)
    - PipelineRegistry lifecycle
    - API endpoints (repos + query) via TestClient

All tests use mocks for the Pipeline (no real cloning/embedding).
"""

import unittest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient


# ═══════════════════════════════════════════════════════════════
# Exception Tests
# ═══════════════════════════════════════════════════════════════


class TestExceptions(unittest.TestCase):
    """Test the exception hierarchy."""

    def test_repomind_error_base(self):
        from app.exceptions import RepoMindError

        err = RepoMindError(
            code="TEST_ERROR",
            message="Test message",
            status_code=418,
            detail="Detail",
            suggestion="Fix it",
        )
        self.assertEqual(err.code, "TEST_ERROR")
        self.assertEqual(err.status_code, 418)
        self.assertEqual(str(err), "Test message")

    def test_repo_not_found(self):
        from app.exceptions import RepoNotFoundError

        err = RepoNotFoundError("rp_abc123")
        self.assertEqual(err.code, "REPO_NOT_FOUND")
        self.assertEqual(err.status_code, 404)

    def test_repo_limit_reached(self):
        from app.exceptions import RepoLimitReachedError

        err = RepoLimitReachedError(10)
        self.assertEqual(err.code, "REPO_LIMIT_REACHED")
        self.assertEqual(err.status_code, 429)

    def test_llm_api_error(self):
        from app.exceptions import LLMApiError

        err = LLMApiError("rate limited")
        self.assertEqual(err.code, "LLM_API_ERROR")
        self.assertEqual(err.status_code, 502)

    def test_auth_token_missing(self):
        from app.exceptions import AuthTokenMissingError

        err = AuthTokenMissingError()
        self.assertEqual(err.code, "AUTH_TOKEN_MISSING")
        self.assertEqual(err.status_code, 401)


# ═══════════════════════════════════════════════════════════════
# FirebaseService Tests (in-memory mode)
# ═══════════════════════════════════════════════════════════════


class TestFirebaseService(unittest.TestCase):
    """Test FirebaseService in dev/in-memory mode."""

    def setUp(self):
        from app.services.firebase_service import FirebaseService
        self.fb = FirebaseService()
        # Force dev mode
        self.fb._dev_mode = True
        self.fb._memory_store = {}

    def test_create_repo(self):
        repo_id = self.fb.create_repo("user1", {
            "name": "test-repo",
            "source": "github",
            "github_url": "https://github.com/test/repo",
        })
        self.assertTrue(repo_id.startswith("rp_"))

        repo = self.fb.get_repo(repo_id, "user1")
        self.assertIsNotNone(repo)
        self.assertEqual(repo["name"], "test-repo")
        self.assertEqual(repo["status"], "indexing")

    def test_get_repo_enforces_ownership(self):
        repo_id = self.fb.create_repo("user1", {"name": "test"})

        # Owner can access
        self.assertIsNotNone(self.fb.get_repo(repo_id, "user1"))
        # Non-owner cannot
        self.assertIsNone(self.fb.get_repo(repo_id, "user2"))

    def test_list_repos(self):
        self.fb.create_repo("user1", {"name": "repo1"})
        self.fb.create_repo("user1", {"name": "repo2"})
        self.fb.create_repo("user2", {"name": "repo3"})

        repos = self.fb.list_repos("user1")
        self.assertEqual(len(repos), 2)

    def test_update_repo_status(self):
        repo_id = self.fb.create_repo("user1", {"name": "test"})

        self.fb.update_repo_status(repo_id, "ready", {
            "file_count": 42,
            "total_chunks": 256,
        })

        repo = self.fb.get_repo(repo_id, "user1")
        self.assertEqual(repo["status"], "ready")
        self.assertEqual(repo["file_count"], 42)
        self.assertIsNotNone(repo["indexed_at"])

    def test_delete_repo(self):
        repo_id = self.fb.create_repo("user1", {"name": "test"})

        # Non-owner can't delete
        self.assertFalse(self.fb.delete_repo(repo_id, "user2"))

        # Owner can delete
        self.assertTrue(self.fb.delete_repo(repo_id, "user1"))

        # Verify it's gone
        self.assertIsNone(self.fb.get_repo(repo_id, "user1"))

    def test_count_repos(self):
        self.fb.create_repo("user1", {"name": "r1"})
        self.fb.create_repo("user1", {"name": "r2"})
        self.fb.create_repo("user2", {"name": "r3"})

        self.assertEqual(self.fb.count_repos("user1"), 2)
        self.assertEqual(self.fb.count_repos("user2"), 1)

    def test_find_repo_by_url(self):
        self.fb.create_repo("user1", {
            "name": "flask",
            "github_url": "https://github.com/pallets/flask",
        })

        found = self.fb.find_repo_by_url("user1", "https://github.com/pallets/flask")
        self.assertIsNotNone(found)

        not_found = self.fb.find_repo_by_url("user1", "https://github.com/other/repo")
        self.assertIsNone(not_found)


# ═══════════════════════════════════════════════════════════════
# PipelineRegistry Tests
# ═══════════════════════════════════════════════════════════════


class TestPipelineRegistry(unittest.TestCase):
    """Test PipelineRegistry lifecycle."""

    @patch("app.services.pipeline_registry.Embedder")
    @patch("app.services.pipeline_registry.LLMClient")
    def test_lifecycle(self, mock_llm_cls, mock_embedder_cls):
        from app.services.pipeline_registry import PipelineRegistry

        mock_embedder = MagicMock()
        mock_embedder.dimension = 384
        mock_embedder_cls.return_value = mock_embedder

        mock_llm = MagicMock()
        mock_llm.provider = "gemini"
        mock_llm.model = "gemini-3.6-flash"
        mock_llm_cls.return_value = mock_llm

        registry = PipelineRegistry()
        registry.initialize()

        self.assertTrue(registry.models_loaded)

        # Create
        pipeline = registry.create("rp_test")
        self.assertIsNotNone(pipeline)
        self.assertTrue(registry.has("rp_test"))

        # Get
        same = registry.get("rp_test")
        self.assertIs(pipeline, same)

        # Count
        self.assertEqual(registry.count, 1)

        # Delete
        registry.delete("rp_test")
        self.assertFalse(registry.has("rp_test"))
        self.assertEqual(registry.count, 0)

    def test_create_without_init_raises(self):
        from app.services.pipeline_registry import PipelineRegistry

        registry = PipelineRegistry()
        with self.assertRaises(RuntimeError):
            registry.create("rp_test")


# ═══════════════════════════════════════════════════════════════
# API Endpoint Tests
# ═══════════════════════════════════════════════════════════════


class TestHealthEndpoint(unittest.TestCase):
    """Test the health endpoint."""

    @patch("app.main.pipeline_registry")
    def test_health(self, mock_registry):
        mock_registry.models_loaded = True
        mock_registry.count = 0

        from app.main import app
        client = TestClient(app)

        response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["app_name"], "RepoMind")
        self.assertTrue(data["models_loaded"])


class TestReposAPI(unittest.TestCase):
    """Test repos API endpoints."""

    @patch("app.main.pipeline_registry")
    @patch("app.main.firebase_service")
    def test_list_repos_empty(self, mock_fb, mock_registry):
        mock_fb.list_repos.return_value = []
        mock_registry.models_loaded = True
        mock_registry.count = 0

        from app.main import app
        client = TestClient(app)

        response = client.get("/api/repos")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["count"], 0)

    @patch("app.main.pipeline_registry")
    @patch("app.main.firebase_service")
    def test_get_repo_not_found(self, mock_fb, mock_registry):
        mock_fb.get_repo.return_value = None
        mock_registry.models_loaded = True
        mock_registry.count = 0

        from app.main import app
        client = TestClient(app)

        response = client.get("/api/repos/rp_nonexistent")
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"]["code"], "REPO_NOT_FOUND")

    @patch("app.main.pipeline_registry")
    @patch("app.main.firebase_service")
    def test_delete_repo_not_found(self, mock_fb, mock_registry):
        mock_fb.delete_repo.return_value = False
        mock_registry.models_loaded = True
        mock_registry.count = 0

        from app.main import app
        client = TestClient(app)

        response = client.delete("/api/repos/rp_nonexistent")
        self.assertEqual(response.status_code, 404)

    @patch("app.main.pipeline_registry")
    @patch("app.main.firebase_service")
    def test_clone_validation_error(self, mock_fb, mock_registry):
        mock_registry.models_loaded = True
        mock_registry.count = 0

        from app.main import app
        client = TestClient(app)

        # Invalid URL (not GitHub)
        response = client.post("/api/repos/clone", json={
            "github_url": "https://gitlab.com/some/repo",
        })
        self.assertEqual(response.status_code, 422)

    @patch("app.main.pipeline_registry")
    @patch("app.main.firebase_service")
    def test_clone_repo_limit(self, mock_fb, mock_registry):
        mock_fb.count_repos.return_value = 10
        mock_registry.models_loaded = True
        mock_registry.count = 0

        from app.main import app
        client = TestClient(app)

        response = client.post("/api/repos/clone", json={
            "github_url": "https://github.com/test/repo",
        })
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"]["code"], "REPO_LIMIT_REACHED")

    @patch("app.main.pipeline_registry")
    @patch("app.main.firebase_service")
    def test_clone_duplicate(self, mock_fb, mock_registry):
        mock_fb.count_repos.return_value = 1
        mock_fb.find_repo_by_url.return_value = {"id": "rp_existing"}
        mock_registry.models_loaded = True
        mock_registry.count = 0

        from app.main import app
        client = TestClient(app)

        response = client.post("/api/repos/clone", json={
            "github_url": "https://github.com/test/repo",
        })
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "REPO_ALREADY_EXISTS")


class TestQueryAPI(unittest.TestCase):
    """Test query API endpoint."""

    @patch("app.main.pipeline_registry")
    @patch("app.main.firebase_service")
    def test_query_repo_not_found(self, mock_fb, mock_registry):
        mock_fb.get_repo.return_value = None
        mock_registry.models_loaded = True
        mock_registry.count = 0

        from app.main import app
        client = TestClient(app)

        response = client.post("/api/repos/rp_xxx/query", json={
            "query": "How does auth work?",
        })
        self.assertEqual(response.status_code, 404)

    @patch("app.main.pipeline_registry")
    @patch("app.main.firebase_service")
    def test_query_index_not_ready(self, mock_fb, mock_registry):
        mock_fb.get_repo.return_value = {
            "id": "rp_test",
            "status": "indexing",
            "user_id": "dev_user",
        }
        mock_registry.models_loaded = True
        mock_registry.count = 0

        from app.main import app
        client = TestClient(app)

        response = client.post("/api/repos/rp_test/query", json={
            "query": "How does auth work?",
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "INDEX_NOT_READY")


class TestErrorHandlers(unittest.TestCase):
    """Test global error handlers."""

    @patch("app.main.pipeline_registry")
    def test_validation_error_format(self, mock_registry):
        mock_registry.models_loaded = True
        mock_registry.count = 0

        from app.main import app
        client = TestClient(app)

        # Send invalid JSON (missing required field)
        response = client.post("/api/repos/clone", json={})
        self.assertEqual(response.status_code, 422)

        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"]["code"], "VALIDATION_ERROR")

    @patch("app.main.pipeline_registry")
    def test_swagger_docs_accessible(self, mock_registry):
        mock_registry.models_loaded = True
        mock_registry.count = 0

        from app.main import app
        client = TestClient(app)

        response = client.get("/docs")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
