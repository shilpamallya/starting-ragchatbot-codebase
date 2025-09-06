import json
import os
import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
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
    def empty(cls, error_msg: str) -> 'SearchResults':
        """Create empty results with error message"""
        return cls(documents=[], metadata=[], distances=[], error=error_msg)
    
    def is_empty(self) -> bool:
        """Check if results are empty"""
        return len(self.documents) == 0

@dataclass
class StoredChunk:
    """Stored chunk with embedding"""
    content: str
    metadata: Dict[str, Any]
    embedding: List[float]
    chunk_id: str

class SimpleVectorStore:
    """Simple in-memory vector store using sentence-transformers and cosine similarity"""
    
    def __init__(self, storage_path: str, embedding_model: str, max_results: int = 5):
        self.storage_path = storage_path
        self.max_results = max_results
        
        print(f"Loading embedding model: {embedding_model}")
        self.embedding_model = SentenceTransformer(embedding_model)
        
        # In-memory storage
        self.course_chunks: List[StoredChunk] = []
        self.course_metadata: Dict[str, Dict] = {}
        
        # Create storage directory
        os.makedirs(storage_path, exist_ok=True)
        
        # Try to load existing data
        self._load_data()
    
    def _save_data(self):
        """Save data to disk"""
        try:
            # Save chunks
            chunks_data = []
            for chunk in self.course_chunks:
                chunks_data.append({
                    'content': chunk.content,
                    'metadata': chunk.metadata,
                    'embedding': chunk.embedding,
                    'chunk_id': chunk.chunk_id
                })
            
            chunks_file = os.path.join(self.storage_path, 'chunks.json')
            with open(chunks_file, 'w', encoding='utf-8') as f:
                json.dump(chunks_data, f, ensure_ascii=False, indent=2)
            
            # Save course metadata
            metadata_file = os.path.join(self.storage_path, 'courses.json')
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.course_metadata, f, ensure_ascii=False, indent=2)
            
        except Exception as e:
            print(f"Error saving data: {e}")
    
    def _load_data(self):
        """Load data from disk"""
        try:
            # Load chunks
            chunks_file = os.path.join(self.storage_path, 'chunks.json')
            if os.path.exists(chunks_file):
                with open(chunks_file, 'r', encoding='utf-8') as f:
                    chunks_data = json.load(f)
                
                for chunk_data in chunks_data:
                    chunk = StoredChunk(
                        content=chunk_data['content'],
                        metadata=chunk_data['metadata'],
                        embedding=chunk_data['embedding'],
                        chunk_id=chunk_data['chunk_id']
                    )
                    self.course_chunks.append(chunk)
            
            # Load course metadata
            metadata_file = os.path.join(self.storage_path, 'courses.json')
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    self.course_metadata = json.load(f)
            
            print(f"Loaded {len(self.course_chunks)} chunks and {len(self.course_metadata)} courses")
            
        except Exception as e:
            print(f"Error loading data: {e}")
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            vec1_np = np.array(vec1)
            vec2_np = np.array(vec2)
            
            dot_product = np.dot(vec1_np, vec2_np)
            norm_vec1 = np.linalg.norm(vec1_np)
            norm_vec2 = np.linalg.norm(vec2_np)
            
            if norm_vec1 == 0 or norm_vec2 == 0:
                return 0.0
            
            similarity = dot_product / (norm_vec1 * norm_vec2)
            return float(similarity)
        except:
            return 0.0
    
    def search(self, 
               query: str,
               course_name: Optional[str] = None,
               lesson_number: Optional[int] = None,
               limit: Optional[int] = None) -> SearchResults:
        """Search course content"""
        try:
            if not self.course_chunks:
                return SearchResults.empty("No content available")
            
            # Encode query
            query_embedding = self.embedding_model.encode([query])[0].tolist()
            
            # Calculate similarities and filter
            candidates = []
            for chunk in self.course_chunks:
                # Apply filters
                if course_name and course_name.lower() not in chunk.metadata.get('course_title', '').lower():
                    continue
                if lesson_number and chunk.metadata.get('lesson_number') != lesson_number:
                    continue
                
                # Calculate similarity
                similarity = self._cosine_similarity(query_embedding, chunk.embedding)
                candidates.append((chunk, similarity))
            
            # Sort by similarity (descending) and take top results
            candidates.sort(key=lambda x: x[1], reverse=True)
            top_candidates = candidates[:limit or self.max_results]
            
            # Prepare results
            documents = [chunk.content for chunk, _ in top_candidates]
            metadata = [chunk.metadata for chunk, _ in top_candidates]
            distances = [1.0 - similarity for _, similarity in top_candidates]  # Convert to distance
            
            return SearchResults(
                documents=documents,
                metadata=metadata,
                distances=distances
            )
            
        except Exception as e:
            print(f"Search error: {e}")
            return SearchResults.empty(f"Search failed: {str(e)}")
    
    def add_course_metadata(self, course: Course):
        """Add course metadata"""
        try:
            self.course_metadata[course.title] = {
                "course_title": course.title,
                "instructor": course.instructor or "Unknown",
                "num_lessons": len(course.lessons),
                "course_link": course.course_link,
                "lessons": [
                    {
                        "lesson_number": lesson.lesson_number,
                        "title": lesson.title,
                        "lesson_link": lesson.lesson_link
                    } for lesson in course.lessons
                ]
            }
            self._save_data()
            print(f"Added course metadata: {course.title}")
            
        except Exception as e:
            print(f"Error adding course metadata: {e}")
    
    def add_course_content(self, course_chunks: List[CourseChunk]):
        """Add course content chunks"""
        try:
            if not course_chunks:
                return
            
            print(f"Encoding {len(course_chunks)} chunks...")
            
            # Encode all documents
            documents = [chunk.content for chunk in course_chunks]
            embeddings = self.embedding_model.encode(documents)
            
            # Add to storage
            for i, chunk in enumerate(course_chunks):
                stored_chunk = StoredChunk(
                    content=chunk.content,
                    metadata={
                        "course_title": chunk.course_title,
                        "chunk_index": chunk.chunk_index,
                        "lesson_number": chunk.lesson_number
                    },
                    embedding=embeddings[i].tolist(),
                    chunk_id=f"chunk_{chunk.course_title}_{chunk.chunk_index}"
                )
                self.course_chunks.append(stored_chunk)
            
            self._save_data()
            print(f"Added {len(course_chunks)} content chunks")
            
        except Exception as e:
            print(f"Error adding course content: {e}")
    
    def get_course_count(self) -> int:
        """Get total number of courses"""
        return len(self.course_metadata)
    
    def get_existing_course_titles(self) -> List[str]:
        """Get list of existing course titles"""
        return list(self.course_metadata.keys())
    
    def get_lesson_link(self, course_title: str, lesson_number: int) -> Optional[str]:
        """Get lesson link for a specific course and lesson number"""
        try:
            course_meta = self.course_metadata.get(course_title)
            if not course_meta or 'lessons' not in course_meta:
                return None
            
            for lesson in course_meta['lessons']:
                if lesson.get('lesson_number') == lesson_number:
                    return lesson.get('lesson_link')
            
            return None
        except Exception as e:
            print(f"Error getting lesson link: {e}")
            return None
    
    def get_course_outline(self, course_name: str) -> Optional[Dict[str, Any]]:
        """Get course outline including title, link, and lessons"""
        try:
            # Find course with fuzzy matching (case-insensitive partial match)
            matching_courses = []
            search_term = course_name.lower()
            
            for title, metadata in self.course_metadata.items():
                if search_term in title.lower():
                    matching_courses.append((title, metadata))
            
            if not matching_courses:
                return None
            
            # Return the first match (could be made more sophisticated)
            course_title, course_data = matching_courses[0]
            
            return {
                "course_title": course_data.get("course_title", course_title),
                "course_link": course_data.get("course_link"),
                "instructor": course_data.get("instructor"),
                "num_lessons": course_data.get("num_lessons", 0),
                "lessons": course_data.get("lessons", [])
            }
            
        except Exception as e:
            print(f"Error getting course outline: {e}")
            return None

    def clear_all_data(self):
        """Clear all data"""
        try:
            self.course_chunks = []
            self.course_metadata = {}
            
            # Remove storage files
            for filename in ['chunks.json', 'courses.json']:
                filepath = os.path.join(self.storage_path, filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
            
            print("Cleared all vector store data")
        except Exception as e:
            print(f"Error clearing data: {e}")