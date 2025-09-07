"""Test configuration and fixtures for the RAG system tests."""

import os
import sys
from unittest.mock import MagicMock, Mock

import pytest

# Add the parent directory to the Python path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_generator import AIGenerator
from config import Config
from rag_system import RAGSystem
from search_tools import CourseOutlineTool, CourseSearchTool, ToolManager
from simple_vector_store import SearchResults, SimpleVectorStore


@pytest.fixture
def test_config():
    """Create a test configuration with safe settings."""
    config = Config()
    # Override problematic settings
    config.MAX_RESULTS = 5  # Fix the 0 value that might be causing issues
    config.CHROMA_PATH = "./test_chroma_db"
    config.ANTHROPIC_API_KEY = "test-key"
    config.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
    return config


@pytest.fixture
def sample_search_results():
    """Create sample search results for testing."""
    return SearchResults(
        documents=[
            "MCP (Model Context Protocol) is a new standard for connecting AI applications to data sources.",
            "Creating an MCP server involves implementing the protocol handlers for tools, resources, and prompts.",
            "MCP clients connect to servers to access additional capabilities beyond the base LLM.",
        ],
        metadata=[
            {
                "course_title": "MCP: Build Rich-Context AI Apps with Anthropic",
                "lesson_number": 1,
            },
            {
                "course_title": "MCP: Build Rich-Context AI Apps with Anthropic",
                "lesson_number": 4,
            },
            {
                "course_title": "MCP: Build Rich-Context AI Apps with Anthropic",
                "lesson_number": 5,
            },
        ],
        distances=[0.1, 0.2, 0.3],
    )


@pytest.fixture
def sample_course_outline():
    """Create sample course outline data for testing."""
    return {
        "course_title": "MCP: Build Rich-Context AI Apps with Anthropic",
        "course_link": "https://www.deeplearning.ai/short-courses/mcp-build-rich-context-ai-apps-with-anthropic/",
        "instructor": "Elie Schoppik",
        "num_lessons": 3,
        "lessons": [
            {
                "lesson_number": 1,
                "title": "Why MCP",
                "lesson_link": "https://example.com/lesson1",
            },
            {
                "lesson_number": 4,
                "title": "Creating An MCP Server",
                "lesson_link": "https://example.com/lesson4",
            },
            {
                "lesson_number": 5,
                "title": "Creating An MCP Client",
                "lesson_link": "https://example.com/lesson5",
            },
        ],
    }


@pytest.fixture
def mock_vector_store(sample_search_results, sample_course_outline):
    """Create a mock vector store with predefined responses."""
    mock_store = Mock(spec=SimpleVectorStore)

    # Mock search method
    mock_store.search.return_value = sample_search_results

    # Mock course outline method
    mock_store.get_course_outline.return_value = sample_course_outline

    # Mock lesson link method
    mock_store.get_lesson_link.return_value = "https://example.com/lesson"

    return mock_store


@pytest.fixture
def mock_empty_vector_store():
    """Create a mock vector store that returns empty results."""
    mock_store = Mock(spec=SimpleVectorStore)

    # Mock search method to return empty results
    empty_results = SearchResults(documents=[], metadata=[], distances=[])
    mock_store.search.return_value = empty_results

    # Mock course outline method to return None
    mock_store.get_course_outline.return_value = None

    return mock_store


@pytest.fixture
def course_search_tool(mock_vector_store):
    """Create a CourseSearchTool with mocked vector store."""
    return CourseSearchTool(mock_vector_store)


@pytest.fixture
def course_outline_tool(mock_vector_store):
    """Create a CourseOutlineTool with mocked vector store."""
    return CourseOutlineTool(mock_vector_store)


@pytest.fixture
def tool_manager(course_search_tool, course_outline_tool):
    """Create a ToolManager with both tools registered."""
    manager = ToolManager()
    manager.register_tool(course_search_tool)
    manager.register_tool(course_outline_tool)
    return manager


@pytest.fixture
def mock_anthropic_client():
    """Create a mock Anthropic client for testing."""
    mock_client = MagicMock()

    # Mock a successful tool-free response
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].text = "This is a test response"
    mock_response.stop_reason = "end_turn"

    mock_client.messages.create.return_value = mock_response

    return mock_client


@pytest.fixture
def ai_generator_with_mock_client(test_config, mock_anthropic_client):
    """Create an AIGenerator with a mocked Anthropic client."""
    generator = AIGenerator(test_config.ANTHROPIC_API_KEY, test_config.ANTHROPIC_MODEL)
    generator.client = mock_anthropic_client
    return generator
