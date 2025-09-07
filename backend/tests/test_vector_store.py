"""Tests for vector store functionality, particularly the MAX_RESULTS configuration issue."""

import pytest
from config import Config
from simple_vector_store import SimpleVectorStore


class TestVectorStore:
    """Test vector store functionality and configuration issues."""

    def test_max_results_configuration_issue(self):
        """Test if MAX_RESULTS = 0 is causing the search failure."""
        # Test with the current problematic config
        config = Config()
        assert (
            config.MAX_RESULTS == 0
        ), "Expected MAX_RESULTS to be 0 based on the current config"

        # Create vector store with problematic config
        store = SimpleVectorStore(
            config.CHROMA_PATH, config.EMBEDDING_MODEL, config.MAX_RESULTS
        )

        # Test that max_results = 0 would return empty results
        # This should be the root cause of the content search failure
        assert store.max_results == 0, "Vector store should have max_results = 0"

    def test_max_results_with_valid_configuration(self):
        """Test that search works with valid MAX_RESULTS."""
        # Test with a proper config
        config = Config()
        config.MAX_RESULTS = 5  # Fix the problematic setting

        # Create vector store with fixed config
        store = SimpleVectorStore(
            config.CHROMA_PATH, config.EMBEDDING_MODEL, config.MAX_RESULTS
        )

        assert store.max_results == 5, "Vector store should have max_results = 5"

    def test_search_with_zero_max_results(self):
        """Test search behavior when max_results is 0."""
        config = Config()
        store = SimpleVectorStore(
            config.CHROMA_PATH, config.EMBEDDING_MODEL, 0
        )  # Explicitly set to 0

        # Perform a search
        results = store.search("MCP server creation", course_name="MCP", limit=None)

        # With max_results = 0, the search should return no results
        # This is likely why content queries are failing
        print(f"Search results with MAX_RESULTS=0: {len(results.documents)} documents")

        # Check if this is the issue
        if len(results.documents) == 0:
            print("ISSUE IDENTIFIED: MAX_RESULTS = 0 causes empty search results!")

    def test_search_with_valid_max_results(self):
        """Test search behavior with valid max_results."""
        config = Config()
        store = SimpleVectorStore(
            config.CHROMA_PATH, config.EMBEDDING_MODEL, 5
        )  # Use valid setting

        # Perform the same search
        results = store.search("MCP server creation", course_name="MCP", limit=None)

        print(f"Search results with MAX_RESULTS=5: {len(results.documents)} documents")

        # This should return actual results if the issue is MAX_RESULTS = 0

    def test_search_with_explicit_limit_override(self):
        """Test if providing explicit limit can override the max_results = 0."""
        config = Config()
        store = SimpleVectorStore(
            config.CHROMA_PATH, config.EMBEDDING_MODEL, 0
        )  # Problematic setting

        # Try to override with explicit limit
        results = store.search("MCP server creation", course_name="MCP", limit=5)

        print(
            f"Search results with MAX_RESULTS=0 but limit=5: {len(results.documents)} documents"
        )

    def test_course_count_and_data_availability(self):
        """Test if course data is actually loaded in the vector store."""
        config = Config()
        store = SimpleVectorStore(config.CHROMA_PATH, config.EMBEDDING_MODEL, 5)

        course_count = store.get_course_count()
        print(f"Course count in vector store: {course_count}")

        course_titles = store.get_existing_course_titles()
        print(f"Available courses: {course_titles}")

        # Check if MCP course exists
        mcp_courses = [title for title in course_titles if "MCP" in title]
        print(f"MCP-related courses: {mcp_courses}")

        assert course_count > 0, "Vector store should contain course data"
        assert len(mcp_courses) > 0, "Should have MCP course available"


class TestVectorStoreSearch:
    """Test actual search functionality."""

    def test_direct_search_functionality(self):
        """Test the vector store search with various parameters."""
        config = Config()
        # Use a working configuration
        store = SimpleVectorStore(config.CHROMA_PATH, config.EMBEDDING_MODEL, 5)

        # Test searches that should work
        test_queries = [
            ("MCP server", "MCP"),
            ("creating client", "MCP"),
            ("architecture", "MCP"),
            ("tools and resources", "MCP"),
        ]

        for query, course_name in test_queries:
            results = store.search(query, course_name=course_name)
            print(f"Query: '{query}' in course '{course_name}'")
            print(f"Results: {len(results.documents)} documents")

            if results.error:
                print(f"Error: {results.error}")
            elif len(results.documents) > 0:
                print(f"Sample result: {results.documents[0][:100]}...")
            else:
                print("No results found")
            print("-" * 50)

    def test_lesson_specific_search(self):
        """Test searching within specific lessons."""
        config = Config()
        store = SimpleVectorStore(config.CHROMA_PATH, config.EMBEDDING_MODEL, 5)

        # Test lesson-specific searches
        results = store.search("server", course_name="MCP", lesson_number=4)
        print(f"Lesson 4 search results: {len(results.documents)} documents")

        results = store.search("client", course_name="MCP", lesson_number=5)
        print(f"Lesson 5 search results: {len(results.documents)} documents")
