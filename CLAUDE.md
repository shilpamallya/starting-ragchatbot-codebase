# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development
```bash
# Install dependencies
uv sync

# Run the application
./run.sh
# OR manually:
cd backend && uv run uvicorn app:app --reload --port 8000

# Access points
# Web Interface: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Environment Setup
```bash
# Copy environment template and add Anthropic API key
cp .env.example .env
# Edit .env to add: ANTHROPIC_API_KEY=your-key-here
```

### Code Quality
```bash
# Format code automatically
uv run python scripts/format_code.py
# OR use shell script: ./scripts/format.sh

# Run quality checks
uv run python scripts/quality_check.py
# OR use shell script: ./scripts/check.sh

# Manual formatting commands
uv run black .          # Format with black
uv run isort .          # Sort imports
uv run flake8 .         # Linting
uv run mypy .           # Type checking
```

## Architecture Overview

This is a **Retrieval-Augmented Generation (RAG) system** for querying course materials using semantic search and AI-powered responses.

### Core Components

**RAGSystem (`rag_system.py`)** - Main orchestrator that coordinates all components:
- Processes documents → chunks → vector embeddings → ChromaDB storage
- Handles user queries through tool-based AI search workflow
- Manages sessions and conversation history

**Tool-Based Search Architecture**: The AI (Claude) receives user queries and autonomously decides whether to:
- Answer using general knowledge
- Search course materials using the `CourseSearchTool`
- The search tool performs semantic similarity search through ChromaDB embeddings

**Document Processing Pipeline** (`document_processor.py`):
1. Parses structured course documents with format:
   ```
   Course Title: [title]
   Course Link: [url] 
   Course Instructor: [instructor]
   
   Lesson X: [lesson title]
   [lesson content...]
   ```
2. Extracts course/lesson metadata
3. Chunks text using sentence-based splitting with configurable overlap
4. Adds contextual prefixes: `"Course {title} Lesson {num} content: {chunk}"`

**Vector Storage** (`vector_store.py`):
- Uses ChromaDB with sentence-transformers embeddings (`all-MiniLM-L6-v2`)
- Two collections: course metadata + content chunks
- Semantic search with metadata filtering (course name, lesson number)

### Key Architectural Patterns

**Tool-Enabled AI Workflow**: Instead of traditional RAG retrieval-then-generate, Claude autonomously chooses when to search using the registered `CourseSearchTool`. This allows mixing factual course content with general knowledge responses.

**Session Management**: Each conversation maintains context through `SessionManager` which stores conversation history and passes it to AI for context-aware responses.

**Structured Data Models** (`models.py`):
- `Course` → `Lesson[]` → `CourseChunk[]` hierarchy
- Pydantic models for type safety and API serialization
- Metadata preservation through the entire pipeline

**Configuration System** (`config.py`):
- Centralized settings via environment variables and dataclass
- Key settings: `CHUNK_SIZE=800`, `CHUNK_OVERLAP=100`, `MAX_RESULTS=5`, `MAX_HISTORY=2`

### Frontend-Backend Flow

1. **Frontend** (vanilla JS) sends POST to `/api/query` with `{query, session_id}`
2. **FastAPI** (`app.py`) validates request via Pydantic models 
3. **RAGSystem** creates AI prompt with conversation history
4. **AIGenerator** calls Anthropic API with tools enabled
5. **Claude** decides to use `CourseSearchTool` if needed
6. **Tool execution** performs vector search → ChromaDB → relevant chunks
7. **Response** flows back with generated answer + source attributions

### Data Flow

```
docs/*.txt → DocumentProcessor → Course+CourseChunk objects → 
VectorStore (ChromaDB) → CourseSearchTool → AIGenerator → 
FastAPI → Frontend
```

Course documents are processed once at startup, creating persistent ChromaDB embeddings. User queries trigger real-time semantic search and AI generation.

### Important Implementation Details

- **AI System Prompt**: Configured in `ai_generator.py` with specific instructions for tool usage and response formatting
- **Chunking Strategy**: Sentence-boundary based chunking preserves context while fitting embedding model limits
- **Error Handling**: FastAPI returns 500 errors, frontend shows error messages to user
- **CORS**: Enabled for all origins during development
- **Static File Serving**: FastAPI serves frontend files directly from `/frontend` directory
- always use uv to run the server and do not use pip