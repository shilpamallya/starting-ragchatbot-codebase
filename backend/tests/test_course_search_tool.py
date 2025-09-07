"""Tests for CourseSearchTool functionality."""

from unittest.mock import Mock

import pytest
from search_tools import CourseSearchTool
from simple_vector_store import SearchResults


class TestCourseSearchTool:
    """Test CourseSearchTool execute method and result formatting."""

    def test_execute_with_results(self, course_search_tool, sample_search_results):
        """Test execute method when search returns results."""
        result = course_search_tool.execute("MCP server", course_name="MCP")

        # Should return formatted results
        assert isinstance(result, str)
        assert "MCP: Build Rich-Context AI Apps with Anthropic" in result
        assert "MCP (Model Context Protocol)" in result

        # Check that sources are tracked
        assert len(course_search_tool.last_sources) > 0
        assert (
            course_search_tool.last_sources[0]["title"]
            == "MCP: Build Rich-Context AI Apps with Anthropic"
        )

    def test_execute_with_empty_results(self, mock_empty_vector_store):
        """Test execute method when search returns no results."""
        tool = CourseSearchTool(mock_empty_vector_store)
        result = tool.execute("nonexistent content", course_name="MCP")

        # Should return "no content found" message
        assert "No relevant content found" in result
        assert "MCP" in result

    def test_execute_with_search_error(self):
        """Test execute method when search returns an error."""
        mock_store = Mock()
        error_results = SearchResults(
            documents=[], metadata=[], distances=[], error="Search failed"
        )
        mock_store.search.return_value = error_results

        tool = CourseSearchTool(mock_store)
        result = tool.execute("test query")

        assert result == "Search failed"

    def test_execute_with_lesson_number(self, course_search_tool):
        """Test execute method with lesson number filter."""
        result = course_search_tool.execute(
            "server", course_name="MCP", lesson_number=4
        )

        # Should call vector store search with lesson_number parameter
        course_search_tool.store.search.assert_called_with(
            query="server", course_name="MCP", lesson_number=4
        )

    def test_format_results_with_lesson_links(
        self, mock_vector_store, sample_search_results
    ):
        """Test that lesson links are properly retrieved and formatted."""
        mock_vector_store.get_lesson_link.return_value = "https://example.com/lesson1"

        tool = CourseSearchTool(mock_vector_store)
        tool.store.search.return_value = sample_search_results

        result = tool.execute("test query")

        # Check that lesson links were requested
        mock_vector_store.get_lesson_link.assert_called()

        # Check that sources contain links
        assert len(tool.last_sources) > 0
        assert tool.last_sources[0]["link"] == "https://example.com/lesson1"


class TestCourseSearchToolIntegration:
    """Integration tests with real vector store to identify issues."""

    def test_real_vector_store_search(self):
        """Test CourseSearchTool with real vector store configuration."""
        from config import Config
        from simple_vector_store import SimpleVectorStore

        # Use current configuration (which has MAX_RESULTS = 0)
        config = Config()
        store = SimpleVectorStore(
            config.CHROMA_PATH, config.EMBEDDING_MODEL, config.MAX_RESULTS
        )

        tool = CourseSearchTool(store)

        # Test a query that should return results
        result = tool.execute("MCP server creation", course_name="MCP")

        print(f"Real vector store result with MAX_RESULTS={config.MAX_RESULTS}:")
        print(result)
        print(f"Sources tracked: {len(tool.last_sources)}")

        # This should demonstrate the MAX_RESULTS = 0 issue
        if "No relevant content found" in result:
            print("ISSUE CONFIRMED: Real vector store returns no results!")
            print("This is likely due to MAX_RESULTS = 0 configuration")

    def test_real_vector_store_search_with_fixed_config(self):
        """Test CourseSearchTool with corrected configuration."""
        from config import Config
        from simple_vector_store import SimpleVectorStore

        # Use corrected configuration
        config = Config()
        store = SimpleVectorStore(
            config.CHROMA_PATH, config.EMBEDDING_MODEL, 5
        )  # Fixed MAX_RESULTS

        tool = CourseSearchTool(store)

        # Test the same query
        result = tool.execute("MCP server creation", course_name="MCP")

        print(f"Real vector store result with MAX_RESULTS=5:")
        print(result)
        print(f"Sources tracked: {len(tool.last_sources)}")

        # This should work if MAX_RESULTS was the issue
        if "No relevant content found" not in result:
            print("ISSUE RESOLVED: Fixed configuration returns results!")

    def test_lesson_specific_search_real(self):
        """Test lesson-specific search with real vector store."""
        from config import Config
        from simple_vector_store import SimpleVectorStore

        config = Config()
        store = SimpleVectorStore(
            config.CHROMA_PATH, config.EMBEDDING_MODEL, 5
        )  # Use working config

        tool = CourseSearchTool(store)

        # Test lesson 5 specifically (Creating An MCP Client)
        result = tool.execute("client", course_name="MCP", lesson_number=5)

        print("Lesson 5 specific search result:")
        print(result)

        # This should help identify why lesson 5 queries are failing
        if "No relevant content found" in result:
            print("Issue: Even lesson-specific search returns no results")
        else:
            print("Success: Lesson-specific search works with corrected config")

    def test_various_content_queries_real(self):
        """Test various content queries that users might ask."""
        from config import Config
        from simple_vector_store import SimpleVectorStore

        config = Config()
        store = SimpleVectorStore(
            config.CHROMA_PATH, config.EMBEDDING_MODEL, 5
        )  # Use working config

        tool = CourseSearchTool(store)

        test_queries = [
            ("What does lesson 5 cover?", "MCP", 5),
            ("MCP client creation", "MCP", None),
            ("server implementation", "MCP", None),
            ("MCP architecture", "MCP", None),
            ("tools and resources", "MCP", None),
        ]

        for query, course, lesson in test_queries:
            print(f"\nTesting: '{query}' (course: {course}, lesson: {lesson})")
            result = tool.execute(query, course_name=course, lesson_number=lesson)

            if "No relevant content found" in result:
                print("❌ No results found")
            else:
                print("✅ Results found")
                print(f"Sample: {result[:200]}...")

            print(f"Sources: {len(tool.last_sources)}")
            tool.last_sources = []  # Reset for next test
