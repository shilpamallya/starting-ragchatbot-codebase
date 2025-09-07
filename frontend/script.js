// API base URL - use relative path to work from any host
const API_URL = '/api';

// Global state
let currentSessionId = null;

// DOM elements
let chatMessages, chatInput, sendButton, totalCourses, courseTitles, themeToggle;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Get DOM elements after page loads
    chatMessages = document.getElementById('chatMessages');
    chatInput = document.getElementById('chatInput');
    sendButton = document.getElementById('sendButton');
    totalCourses = document.getElementById('totalCourses');
    courseTitles = document.getElementById('courseTitles');
    themeToggle = document.getElementById('themeToggle');
    
    setupEventListeners();
    initializeTheme();
    createNewSession();
    loadCourseStats();
});

// Event Listeners
function setupEventListeners() {
    // Chat functionality
    sendButton.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
    
    // New Chat button
    document.getElementById('newChatBtn').addEventListener('click', createNewSession);
    
    // Suggested questions
    document.querySelectorAll('.suggested-item').forEach(button => {
        button.addEventListener('click', (e) => {
            const question = e.target.getAttribute('data-question');
            chatInput.value = question;
            sendMessage();
        });
    });
    
    // Theme toggle
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
        themeToggle.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleTheme();
            }
        });
    }
}


// Chat Functions
async function sendMessage() {
    const query = chatInput.value.trim();
    if (!query) return;

    // Disable input
    chatInput.value = '';
    chatInput.disabled = true;
    sendButton.disabled = true;

    // Add user message
    addMessage(query, 'user');

    // Add loading message - create a unique container for it
    const loadingMessage = createLoadingMessage();
    chatMessages.appendChild(loadingMessage);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        const response = await fetch(`${API_URL}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: query,
                session_id: currentSessionId
            })
        });

        if (!response.ok) throw new Error('Query failed');

        const data = await response.json();
        
        // Update session ID if new
        if (!currentSessionId) {
            currentSessionId = data.session_id;
        }

        // Replace loading message with response
        loadingMessage.remove();
        addMessage(data.answer, 'assistant', data.sources);

    } catch (error) {
        // Replace loading message with error
        loadingMessage.remove();
        addMessage(`Error: ${error.message}`, 'assistant');
    } finally {
        chatInput.disabled = false;
        sendButton.disabled = false;
        chatInput.focus();
    }
}

function createLoadingMessage() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="loading">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    return messageDiv;
}

function addMessage(content, type, sources = null, isWelcome = false) {
    const messageId = Date.now();
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}${isWelcome ? ' welcome-message' : ''}`;
    messageDiv.id = `message-${messageId}`;
    
    // Convert markdown to HTML for assistant messages
    const displayContent = type === 'assistant' ? marked.parse(content) : escapeHtml(content);
    
    let html = `<div class="message-content">${displayContent}</div>`;
    
    if (sources && sources.length > 0) {
        // Format sources as clickable links when available
        const sourceElements = sources.map(source => {
            if (typeof source === 'object' && source.title) {
                // Handle structured source objects
                let displayText = source.title;
                if (source.lesson_number !== null && source.lesson_number !== undefined) {
                    displayText += ` - Lesson ${source.lesson_number}`;
                }
                
                if (source.link) {
                    return `<a href="${escapeHtml(source.link)}" target="_blank" rel="noopener noreferrer" class="source-link">${escapeHtml(displayText)}</a>`;
                } else {
                    return escapeHtml(displayText);
                }
            } else if (typeof source === 'string') {
                // Parse string sources to extract lesson information and create links
                const sourceStr = source;
                const lessonMatch = sourceStr.match(/^(.+?) - Lesson (\d+)$/);
                
                if (lessonMatch) {
                    const [, courseTitle, lessonNumber] = lessonMatch;
                    const lessonLink = getLessonLink(courseTitle, parseInt(lessonNumber));
                    
                    if (lessonLink) {
                        return `<a href="${escapeHtml(lessonLink)}" target="_blank" rel="noopener noreferrer" class="source-link">${escapeHtml(sourceStr)}</a>`;
                    } else {
                        return escapeHtml(sourceStr);
                    }
                } else {
                    return escapeHtml(sourceStr);
                }
            } else {
                // Fallback for other formats
                return escapeHtml(String(source));
            }
        });
        
        html += `
            <details class="sources-collapsible">
                <summary class="sources-header">Sources</summary>
                <div class="sources-content">${sourceElements.join('')}</div>
            </details>
        `;
    }
    
    messageDiv.innerHTML = html;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return messageId;
}

// Helper function to escape HTML for user messages
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Function to get lesson link based on course title and lesson number
function getLessonLink(courseTitle, lessonNumber) {
    // Mapping of course titles to their base URLs and lesson patterns
    const coursePatterns = {
        'Building Towards Computer Use with Anthropic': {
            baseUrl: 'https://learn.deeplearning.ai/courses/building-toward-computer-use-with-anthropic/lesson',
            lessons: {
                0: 'a6k0z/introduction',
                1: 'x97e6/anthropic-and-claude',
                2: 'y5k7f/first-api-call',
                3: 'x5k7f/multimodal-capabilities',
                4: 'n6k7f/tool-use',
                5: 'd7k7f/tools-execution-part-2',
                6: 'm8k7f/function-calling-best-practices',
                7: 'ljun5/computer-use',
                8: 'p9k7f/agents'
            }
        },
        'MCP: Build Rich-Context AI Apps with Anthropic': {
            baseUrl: 'https://learn.deeplearning.ai/courses/mcp-build-rich-context-ai-apps-with-anthropic/lesson',
            lessons: {
                0: 'fkbhh/introduction',
                1: 'ccsd0/why-mcp',
                2: 'gdms0/mcp-primitives',
                3: 'sge50/creating-an-mcp-server',
                4: 'y8g9n/creating-mcp-resources',
                5: 'pnd5n/creating-an-mcp-client',
                6: 'frhw0/mcp-tools',
                7: 'mjei0/mcp-prompts',
                8: 'l8ms0/configuring-servers-for-claude-desktop',
                9: 'kd5n0/conclusion'
            }
        },
        'Advanced Retrieval for AI with Chroma': {
            baseUrl: 'https://learn.deeplearning.ai/courses/advanced-retrieval-for-ai-with-chroma/lesson',
            lessons: {
                0: 'a6k0z/introduction',
                1: 'b7k1z/query-expansion',
                2: 'c8k2z/cross-encoder-reranking',
                3: 'd9k3z/embedding-adaptors'
            }
        },
        'Prompt Compression and Query Optimization': {
            baseUrl: 'https://learn.deeplearning.ai/courses/prompt-compression-and-query-optimization/lesson',
            lessons: {
                0: 'a6k0z/introduction',
                1: 'y8g9n/vanilla-vector-search',
                2: 'x7k8z/query-expansion',
                3: 'sge50/projections'
            }
        }
    };
    
    const coursePattern = coursePatterns[courseTitle];
    if (coursePattern && coursePattern.lessons[lessonNumber]) {
        return `${coursePattern.baseUrl}/${coursePattern.lessons[lessonNumber]}`;
    }
    
    return null; // No link found
}

// Removed removeMessage function - no longer needed since we handle loading differently

async function createNewSession() {
    currentSessionId = null;
    chatMessages.innerHTML = '';
    addMessage('Welcome to the Course Materials Assistant! I can help you with questions about courses, lessons and specific content. What would you like to know?', 'assistant', null, true);
}

// Load course statistics
async function loadCourseStats() {
    try {
        console.log('Loading course stats...');
        const response = await fetch(`${API_URL}/courses`);
        if (!response.ok) throw new Error('Failed to load course stats');
        
        const data = await response.json();
        console.log('Course data received:', data);
        
        // Update stats in UI
        if (totalCourses) {
            totalCourses.textContent = data.total_courses;
        }
        
        // Update course titles
        if (courseTitles) {
            if (data.course_titles && data.course_titles.length > 0) {
                courseTitles.innerHTML = data.course_titles
                    .map(title => `<div class="course-title-item">${title}</div>`)
                    .join('');
            } else {
                courseTitles.innerHTML = '<span class="no-courses">No courses available</span>';
            }
        }
        
    } catch (error) {
        console.error('Error loading course stats:', error);
        // Set default values on error
        if (totalCourses) {
            totalCourses.textContent = '0';
        }
        if (courseTitles) {
            courseTitles.innerHTML = '<span class="error">Failed to load courses</span>';
        }
    }
}

// Theme Functions
function initializeTheme() {
    // Check for saved theme preference or default to 'dark'
    const savedTheme = localStorage.getItem('theme') || 'dark';
    setTheme(savedTheme);
}

function toggleTheme() {
    const currentTheme = getCurrentTheme();
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
}

function getCurrentTheme() {
    return document.documentElement.getAttribute('data-theme') || 'dark';
}

function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    
    // Update ARIA label for accessibility
    if (themeToggle) {
        const label = theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme';
        themeToggle.setAttribute('aria-label', label);
    }
}