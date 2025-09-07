from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Protocol

from simple_vector_store import SearchResults
from simple_vector_store import SimpleVectorStore as VectorStore


class Tool(ABC):
    """Abstract base class for all tools"""

    @abstractmethod
    def get_tool_definition(self) -> Dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """Execute the tool with given parameters"""
        pass


class CourseSearchTool(Tool):
    """Tool for searching course content with semantic course name matching"""

    def __init__(self, vector_store: VectorStore):
        self.store = vector_store
        self.last_sources = []  # Track sources from last search

    def get_tool_definition(self) -> Dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        return {
            "name": "search_course_content",
            "description": "Search for SPECIFIC CONTENT within course lessons. Use ONLY when user asks about detailed content inside lessons, not for course structure or lesson lists.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for in the course content",
                    },
                    "course_name": {
                        "type": "string",
                        "description": "Course title (partial matches work, e.g. 'MCP', 'Introduction')",
                    },
                    "lesson_number": {
                        "type": "integer",
                        "description": "Specific lesson number to search within (e.g. 1, 2, 3)",
                    },
                },
                "required": ["query"],
            },
        }

    def execute(
        self,
        query: str,
        course_name: Optional[str] = None,
        lesson_number: Optional[int] = None,
    ) -> str:
        """
        Execute the search tool with given parameters.

        Args:
            query: What to search for
            course_name: Optional course filter
            lesson_number: Optional lesson filter

        Returns:
            Formatted search results or error message
        """

        # Use the vector store's unified search interface
        results = self.store.search(
            query=query, course_name=course_name, lesson_number=lesson_number
        )

        # Handle errors
        if results.error:
            return results.error

        # Handle empty results
        if results.is_empty():
            filter_info = ""
            if course_name:
                filter_info += f" in course '{course_name}'"
            if lesson_number:
                filter_info += f" in lesson {lesson_number}"
            return f"No relevant content found{filter_info}."

        # Format and return results
        return self._format_results(results)

    def _format_results(self, results: SearchResults) -> str:
        """Format search results with course and lesson context"""
        formatted = []
        sources = []  # Track structured sources for the UI

        for doc, meta in zip(results.documents, results.metadata):
            course_title = meta.get("course_title", "unknown")
            lesson_num = meta.get("lesson_number")

            # Build context header
            header = f"[{course_title}"
            if lesson_num is not None:
                header += f" - Lesson {lesson_num}"
            header += "]"

            # Create structured source with lesson link if available
            source = {"title": course_title, "lesson_number": lesson_num, "link": None}

            # Try to get lesson link from vector store
            if lesson_num is not None:
                link = self.store.get_lesson_link(course_title, lesson_num)
                if link:
                    source["link"] = link

            sources.append(source)
            formatted.append(f"{header}\n{doc}")

        # Store structured sources for retrieval
        self.last_sources = sources

        return "\n\n".join(formatted)


class CourseOutlineTool(Tool):
    """Tool for getting course outline with lesson structure"""

    def __init__(self, vector_store: VectorStore):
        self.store = vector_store

    def get_tool_definition(self) -> Dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        return {
            "name": "get_course_outline",
            "description": "Get complete course OUTLINE/STRUCTURE showing course title, link, and ALL lesson numbers with titles. Use for ANY question about course structure, syllabus, lesson lists, or 'what lessons are in' queries.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "course_name": {
                        "type": "string",
                        "description": "Course title (partial matches work, e.g. 'MCP', 'Introduction')",
                    }
                },
                "required": ["course_name"],
            },
        }

    def execute(self, course_name: str) -> str:
        """
        Execute the outline tool with given course name.

        Args:
            course_name: Course title to get outline for

        Returns:
            Formatted course outline or error message
        """
        outline = self.store.get_course_outline(course_name)

        if not outline:
            return f"No course found matching '{course_name}'. Please check the course name and try again."

        return self._format_outline(outline)

    def _format_outline(self, outline: Dict[str, Any]) -> str:
        """Format course outline for display"""
        result = []

        # Course header
        result.append(f"**{outline['course_title']}**")

        # Add course link if available
        if outline.get("course_link"):
            result.append(f"Course Link: {outline['course_link']}")

        # Add instructor if available
        if outline.get("instructor"):
            result.append(f"Instructor: {outline['instructor']}")

        # Add lesson count
        result.append(f"Total Lessons: {outline.get('num_lessons', 0)}")

        # Add lessons list
        lessons = outline.get("lessons", [])
        if lessons:
            result.append("\n**Lessons:**")
            for lesson in lessons:
                lesson_num = lesson.get("lesson_number", "N/A")
                lesson_title = lesson.get("title", "Untitled")
                result.append(f"{lesson_num}. {lesson_title}")
        else:
            result.append("\nNo lessons found.")

        return "\n".join(result)


class ToolManager:
    """Manages available tools for the AI"""

    def __init__(self):
        self.tools = {}

    def register_tool(self, tool: Tool):
        """Register any tool that implements the Tool interface"""
        tool_def = tool.get_tool_definition()
        tool_name = tool_def.get("name")
        if not tool_name:
            raise ValueError("Tool must have a 'name' in its definition")
        self.tools[tool_name] = tool

    def get_tool_definitions(self) -> list:
        """Get all tool definitions for Anthropic tool calling"""
        return [tool.get_tool_definition() for tool in self.tools.values()]

    def execute_tool(self, tool_name: str, **kwargs) -> str:
        """Execute a tool by name with given parameters"""
        if tool_name not in self.tools:
            return f"Tool '{tool_name}' not found"

        return self.tools[tool_name].execute(**kwargs)

    def get_last_sources(self) -> list:
        """Get sources from the last search operation"""
        # Check all tools for last_sources attribute
        for tool in self.tools.values():
            if hasattr(tool, "last_sources") and tool.last_sources:
                return tool.last_sources
        return []

    def reset_sources(self):
        """Reset sources from all tools that track sources"""
        for tool in self.tools.values():
            if hasattr(tool, "last_sources"):
                tool.last_sources = []
