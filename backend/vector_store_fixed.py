from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings
from models import Course, CourseChunk
from sentence_transformers import SentenceTransformer


@dataclass
class SearchResults:
    """Container for search results with metadata"""

    documents: List[str]
    metadata: List[Dict[str, Any]]
    distances: List[float]
    error: Optional[str] = None

    @classmethod
    def from_chroma(cls, chroma_results: Dict) -> "SearchResults":
        """Create SearchResults from ChromaDB query results"""
        return cls(
            documents=(
                chroma_results["documents"][0] if chroma_results["documents"] else []
            ),
            metadata=(
                chroma_results["metadatas"][0] if chroma_results["metadatas"] else []
            ),
            distances=(
                chroma_results["distances"][0] if chroma_results["distances"] else []
            ),
        )

    @classmethod
    def empty(cls, error_msg: str) -> "SearchResults":
        """Create empty results with error message"""
        return cls(documents=[], metadata=[], distances=[], error=error_msg)

    def is_empty(self) -> bool:
        """Check if results are empty"""
        return len(self.documents) == 0


class VectorStore:
    """Vector storage using ChromaDB with manual embedding handling to avoid Windows segfaults"""

    def __init__(self, chroma_path: str, embedding_model: str, max_results: int = 5):
        self.max_results = max_results

        # Initialize sentence transformer model manually
        print(f"Loading embedding model: {embedding_model}")
        self.embedding_model = SentenceTransformer(embedding_model)

        # Initialize ChromaDB client without built-in embedding function
        self.client = chromadb.PersistentClient(
            path=chroma_path, settings=Settings(anonymized_telemetry=False)
        )

        # Create collections without embedding function (we'll handle manually)
        self.course_catalog = self._create_collection("course_catalog")
        self.course_content = self._create_collection("course_content")

    def _create_collection(self, name: str):
        """Create or get a ChromaDB collection without embedding function"""
        return self.client.get_or_create_collection(name=name)

    def _encode_texts(self, texts: List[str]) -> List[List[float]]:
        """Manually encode texts to embeddings"""
        embeddings = self.embedding_model.encode(texts)
        return embeddings.tolist()

    def search(
        self,
        query: str,
        course_name: Optional[str] = None,
        lesson_number: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> SearchResults:
        """Search course content with manual embedding"""
        try:
            # Encode query
            query_embedding = self._encode_texts([query])[0]

            # Build where clause for filtering
            where_clause = {}
            if course_name:
                where_clause["course_title"] = {"$contains": course_name}
            if lesson_number:
                where_clause["lesson_number"] = lesson_number

            # Search in content collection
            results = self.course_content.query(
                query_embeddings=[query_embedding],
                n_results=limit or self.max_results,
                where=where_clause if where_clause else None,
            )

            return SearchResults.from_chroma(results)

        except Exception as e:
            print(f"Search error: {e}")
            return SearchResults.empty(f"Search failed: {str(e)}")

    def add_course_metadata(self, course: Course):
        """Add course metadata to catalog"""
        try:
            # Prepare course text for embedding
            course_text = f"Course: {course.title}"
            if course.instructor:
                course_text += f" by {course.instructor}"

            # Add lessons info
            if course.lessons:
                lesson_titles = [
                    f"Lesson {lesson.lesson_number}: {lesson.title}"
                    for lesson in course.lessons
                ]
                course_text += f" Lessons: {', '.join(lesson_titles)}"

            # Encode and add to catalog
            embedding = self._encode_texts([course_text])[0]

            self.course_catalog.add(
                documents=[course_text],
                embeddings=[embedding],
                metadatas=[
                    {
                        "course_title": course.title,
                        "instructor": course.instructor or "Unknown",
                        "num_lessons": len(course.lessons),
                        "course_link": course.course_link,
                    }
                ],
                ids=[f"course_{course.title}"],
            )
            print(f"Added course metadata: {course.title}")

        except Exception as e:
            print(f"Error adding course metadata: {e}")

    def add_course_content(self, course_chunks: List[CourseChunk]):
        """Add course content chunks to vector store"""
        try:
            if not course_chunks:
                return

            # Prepare data for batch insertion
            documents = [chunk.content for chunk in course_chunks]
            embeddings = self._encode_texts(documents)

            metadatas = []
            ids = []

            for i, chunk in enumerate(course_chunks):
                metadata = {
                    "course_title": chunk.course_title,
                    "chunk_index": chunk.chunk_index,
                }
                if chunk.lesson_number is not None:
                    metadata["lesson_number"] = chunk.lesson_number

                metadatas.append(metadata)
                ids.append(f"chunk_{chunk.course_title}_{chunk.chunk_index}")

            # Add to collection in batches to avoid memory issues
            batch_size = 50
            for i in range(0, len(documents), batch_size):
                end_idx = min(i + batch_size, len(documents))

                self.course_content.add(
                    documents=documents[i:end_idx],
                    embeddings=embeddings[i:end_idx],
                    metadatas=metadatas[i:end_idx],
                    ids=ids[i:end_idx],
                )

            print(f"Added {len(course_chunks)} content chunks")

        except Exception as e:
            print(f"Error adding course content: {e}")

    def get_course_count(self) -> int:
        """Get total number of courses"""
        try:
            return self.course_catalog.count()
        except:
            return 0

    def get_existing_course_titles(self) -> List[str]:
        """Get list of existing course titles"""
        try:
            results = self.course_catalog.get()
            return [meta.get("course_title", "") for meta in results["metadatas"]]
        except:
            return []

    def clear_all_data(self):
        """Clear all data from collections"""
        try:
            # Delete and recreate collections
            self.client.delete_collection("course_catalog")
            self.client.delete_collection("course_content")

            self.course_catalog = self._create_collection("course_catalog")
            self.course_content = self._create_collection("course_content")

            print("Cleared all vector store data")
        except Exception as e:
            print(f"Error clearing data: {e}")
