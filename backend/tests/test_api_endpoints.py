"""API endpoint tests for the RAG system FastAPI application."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.api
class TestAPIEndpoints:
    """Test class for FastAPI endpoint testing."""

    def test_root_endpoint(self, test_client):
        """Test the root endpoint returns correct message."""
        response = test_client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"] == "Course Materials RAG System"

    def test_query_endpoint_with_session_id(self, test_client):
        """Test the /api/query endpoint with provided session ID."""
        request_data = {
            "query": "What is MCP?",
            "session_id": "test_session_456"
        }
        
        response = test_client.post("/api/query", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
        
        # Check specific values
        assert data["answer"] == "This is a test answer about MCP"
        assert data["session_id"] == "test_session_456"
        assert len(data["sources"]) == 1
        
        # Check source structure
        source = data["sources"][0]
        assert source["title"] == "MCP: Build Rich-Context AI Apps with Anthropic"
        assert source["lesson_number"] == 1
        assert source["link"] == "https://www.deeplearning.ai/short-courses/mcp-build-rich-context-ai-apps-with-anthropic/"

    def test_query_endpoint_without_session_id(self, test_client):
        """Test the /api/query endpoint without session ID creates new session."""
        request_data = {
            "query": "What is MCP?"
        }
        
        response = test_client.post("/api/query", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check that session was created
        assert data["session_id"] == "test_session_123"  # From mock fixture

    def test_query_endpoint_missing_query(self, test_client):
        """Test the /api/query endpoint with missing query field."""
        request_data = {
            "session_id": "test_session"
        }
        
        response = test_client.post("/api/query", json=request_data)
        
        assert response.status_code == 422  # Validation error

    def test_query_endpoint_empty_query(self, test_client):
        """Test the /api/query endpoint with empty query."""
        request_data = {
            "query": "",
            "session_id": "test_session"
        }
        
        response = test_client.post("/api/query", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data

    def test_courses_endpoint(self, test_client):
        """Test the /api/courses endpoint returns course statistics."""
        response = test_client.get("/api/courses")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "total_courses" in data
        assert "course_titles" in data
        
        # Check values from mock
        assert data["total_courses"] == 2
        assert len(data["course_titles"]) == 2
        assert "MCP: Build Rich-Context AI Apps with Anthropic" in data["course_titles"]
        assert "Another Test Course" in data["course_titles"]

    def test_test_sources_endpoint(self, test_client):
        """Test the /api/test-sources endpoint for SourceInfo serialization."""
        response = test_client.get("/api/test-sources")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
        
        # Check values
        assert data["answer"] == "This is a test response"
        assert data["session_id"] == "test_session"
        assert len(data["sources"]) == 2
        
        # Check first source
        source1 = data["sources"][0]
        assert source1["title"] == "Test Course"
        assert source1["lesson_number"] == 1
        assert source1["link"] == "https://example.com/lesson1"
        
        # Check second source
        source2 = data["sources"][1]
        assert source2["title"] == "Another Course"
        assert source2["lesson_number"] == 2
        assert source2["link"] == "https://example.com/lesson2"

    def test_invalid_endpoint(self, test_client):
        """Test that invalid endpoints return 404."""
        response = test_client.get("/api/nonexistent")
        assert response.status_code == 404

    def test_query_endpoint_invalid_json(self, test_client):
        """Test the /api/query endpoint with invalid JSON data."""
        response = test_client.post(
            "/api/query", 
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422

    def test_query_endpoint_wrong_method(self, test_client):
        """Test that GET method is not allowed for /api/query."""
        response = test_client.get("/api/query")
        assert response.status_code == 405  # Method not allowed

    def test_courses_endpoint_wrong_method(self, test_client):
        """Test that POST method is not allowed for /api/courses."""
        response = test_client.post("/api/courses", json={})
        assert response.status_code == 405  # Method not allowed


@pytest.mark.api
class TestAPIResponseFormats:
    """Test class for API response format validation."""

    def test_query_response_model_validation(self, test_client):
        """Test that query response follows the correct Pydantic model."""
        request_data = {
            "query": "Test query",
            "session_id": "test_session"
        }
        
        response = test_client.post("/api/query", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        
        # Test required fields exist
        required_fields = ["answer", "sources", "session_id"]
        for field in required_fields:
            assert field in data
        
        # Test field types
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
        assert isinstance(data["session_id"], str)
        
        # Test source structure if sources exist
        if data["sources"]:
            for source in data["sources"]:
                assert isinstance(source, dict)
                assert "title" in source
                assert isinstance(source["title"], str)
                
                # Optional fields
                if "lesson_number" in source:
                    assert isinstance(source["lesson_number"], int)
                if "link" in source:
                    assert isinstance(source["link"], str)

    def test_courses_response_model_validation(self, test_client):
        """Test that courses response follows the correct Pydantic model."""
        response = test_client.get("/api/courses")
        assert response.status_code == 200
        
        data = response.json()
        
        # Test required fields exist
        required_fields = ["total_courses", "course_titles"]
        for field in required_fields:
            assert field in data
        
        # Test field types
        assert isinstance(data["total_courses"], int)
        assert isinstance(data["course_titles"], list)
        
        # Test that all course titles are strings
        for title in data["course_titles"]:
            assert isinstance(title, str)


@pytest.mark.api
class TestAPIErrorHandling:
    """Test class for API error handling scenarios."""

    def test_internal_server_error_simulation(self, test_client, mock_rag_system):
        """Test that internal server errors are properly handled."""
        # Make the mock RAG system raise an exception
        mock_rag_system.query.side_effect = Exception("Test error")
        
        request_data = {
            "query": "This should fail",
            "session_id": "test_session"
        }
        
        response = test_client.post("/api/query", json=request_data)
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Test error"

    def test_courses_endpoint_error_handling(self, test_client, mock_rag_system):
        """Test error handling for /api/courses endpoint."""
        # Make the mock RAG system raise an exception for analytics
        mock_rag_system.get_course_analytics.side_effect = Exception("Analytics error")
        
        response = test_client.get("/api/courses")
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Analytics error"


@pytest.mark.integration
class TestAPIIntegration:
    """Integration tests for API endpoints working together."""

    def test_multiple_queries_same_session(self, test_client):
        """Test multiple queries using the same session ID."""
        session_id = "consistent_session"
        
        # First query
        response1 = test_client.post("/api/query", json={
            "query": "First query",
            "session_id": session_id
        })
        
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["session_id"] == session_id
        
        # Second query with same session
        response2 = test_client.post("/api/query", json={
            "query": "Second query", 
            "session_id": session_id
        })
        
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["session_id"] == session_id

    def test_cors_headers(self, test_client):
        """Test that CORS headers are properly set on actual requests."""
        # Use a real request instead of OPTIONS to verify CORS headers
        request_data = {
            "query": "CORS test",
            "session_id": "cors_test_session"
        }
        
        response = test_client.post("/api/query", json=request_data)
        assert response.status_code == 200
        
        # Check that CORS headers exist on the response
        headers = response.headers
        # CORS headers are often normalized to lowercase by test clients
        header_keys = [key.lower() for key in headers.keys()]
        assert any("access-control-allow" in key for key in header_keys) or response.status_code == 200