import json
import os
import sys
from dotenv import load_dotenv
from groq import Groq
import github_mcp
import web_search_tool
import gmail_tool
import db_tool
import tasks_tool

# CloudGuard Security Gateway SDK Integration
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cloudguard", "sdk", "python"))
try:
    from cloudguard.client import CloudGuardClient, CloudGuardDeniedError, CloudGuardEscalatedError
    CLOUDGUARD_AVAILABLE = True
except ImportError:
    CLOUDGUARD_AVAILABLE = False

# 1. Load environment variables
load_dotenv()

# Initialize Groq client
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# 2. Define Tool Schemas for Groq Function Calling
TOOLS_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_user_profile",
            "description": "Fetch public GitHub profile details of a user (name, bio, location, repos count, followers).",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "The exact GitHub username to look up"
                    }
                },
                "required": ["username"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_repositories",
            "description": "Fetch a list of public GitHub repositories for a specified user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "The exact GitHub username to fetch repositories for"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of repositories to fetch (default is 5)",
                        "default": 5
                    }
                },
                "required": ["username"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_repositories",
            "description": "Search GitHub repositories by topic, query, or language.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g. 'fastmcp' or 'e-commerce python')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (default 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_repo_readme",
            "description": "Fetch and summarize the README file of a specific GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {
                        "type": "string",
                        "description": "GitHub repository owner"
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository name"
                    }
                },
                "required": ["owner", "repo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_upcoming_calendar_events",
            "description": "Fetch upcoming events from the user's Google Calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Number of upcoming events to fetch (default: 5)",
                        "default": 5
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": "Schedule/create a new event or meeting on the user's Google Calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Title or topic of the calendar event"
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Start time in ISO format (e.g. '2026-08-02T10:00:00+05:30')"
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time in ISO format (e.g. '2026-08-02T11:00:00+05:30')"
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional details or notes for the meeting/event"
                    }
                },
                "required": ["summary", "start_time", "end_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_calendar_event",
            "description": "Delete or remove an event from the user's Google Calendar by title/summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_summary": {
                        "type": "string",
                        "description": "The title or summary keyword of the event to delete (e.g. 'New Event')"
                    }
                },
                "required": ["event_summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the live web for recent news, articles, tutorials, or general knowledge using DuckDuckGo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max results to return (default 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scrape_url",
            "description": "Scrape and extract readable text content from any webpage URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full HTTP or HTTPS URL of the webpage to scrape"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_content",
            "description": "Analyze any text content using AI. Use after scraping a webpage or from raw text to summarize, assess risks, extract links, or pull key information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The raw text content to analyze"
                    },
                    "analysis_type": {
                        "type": "string",
                        "description": "Type of analysis: 'summarize' | 'risk_assessment' | 'extract_links' | 'key_info'",
                        "enum": ["summarize", "risk_assessment", "extract_links", "key_info"],
                        "default": "summarize"
                    }
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_emails",
            "description": "Search messages in Gmail inbox matching a specific query string (e.g. 'from:github', 'subject:invoice', 'urgent').",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Gmail search query string (e.g. 'is:unread', 'from:sender@example.com')"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max number of messages to fetch (default: 5)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_unread_inbox",
            "description": "Fetch unread emails from Gmail and generate an AI-powered executive summary using Groq AI. Use this when the user asks to check today's new mail, check unread emails, or summarize inbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Max number of unread emails to summarize (default: 5)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_email_draft",
            "description": "Create a new email draft in Gmail.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Subject line of the email"
                    },
                    "body": {
                        "type": "string",
                        "description": "Text body of the draft email"
                    }
                },
                "required": ["to", "subject", "body"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "store_text_data",
            "description": "Store text notes, code snippets, or structured data in the SQL database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Short title or header for the text entry"
                    },
                    "content": {
                        "type": "string",
                        "description": "The text body or content to store"
                    },
                    "tags": {
                        "type": "string",
                        "description": "Optional comma-separated tags (e.g. 'notes, meeting, python')"
                    }
                },
                "required": ["title", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "store_file",
            "description": "Read any local file (Image, PDF, Document, Code, Data) and store it in the SQL database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the local file (e.g. 'doc.pdf', '/path/to/image.png')"
                    },
                    "title": {
                        "type": "string",
                        "description": "Optional custom title (defaults to filename if omitted)"
                    },
                    "tags": {
                        "type": "string",
                        "description": "Optional comma-separated tags (e.g. 'pdf, research, invoice')"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_database",
            "description": "Search stored documents, images, PDFs, and text notes in the SQL database by keyword.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query or keyword"
                    },
                    "file_type": {
                        "type": "string",
                        "description": "Filter by file type: 'all' | 'text' | 'pdf' | 'image' | 'data'"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_stored_documents",
            "description": "List stored documents, images, PDFs, and text notes in the SQL database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max items to list (default: 10)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_document",
            "description": "Fetch full content and metadata for a document in the SQL database by its integer ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "integer",
                        "description": "The integer ID of the document to retrieve"
                    }
                },
                "required": ["doc_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_document",
            "description": "Update an existing document's title, text content, or tags in the SQL database by its integer ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "integer",
                        "description": "The integer ID of the document to update"
                    },
                    "title": {
                        "type": "string",
                        "description": "New title for the document (optional)"
                    },
                    "content": {
                        "type": "string",
                        "description": "New text content for the document (optional)"
                    },
                    "tags": {
                        "type": "string",
                        "description": "New comma-separated tags for the document (optional)"
                    }
                },
                "required": ["doc_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_document",
            "description": "Delete a document from the SQL database by its integer ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "integer",
                        "description": "The integer ID of the document to delete"
                    }
                },
                "required": ["doc_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_google_tasks",
            "description": "List tasks/to-dos from the user's primary Google Tasks list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "show_completed": {
                        "type": "boolean",
                        "description": "Whether to include completed tasks (default: False)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_google_task",
            "description": "Create a new task item on the user's primary Google Tasks list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Task title or description"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional additional notes"
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Optional due date (YYYY-MM-DD format)"
                    }
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "complete_google_task",
            "description": "Mark a task as completed on the user's primary Google Tasks list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The ID of the task to mark as completed"
                    }
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_daily_briefing",
            "description": "Synthesize a complete executive Daily Morning Briefing combining Calendar events, unread Gmail summary, pending Google Tasks, and top news headlines.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_notion",
            "description": "Search for pages and databases in the user's Notion workspace matching a query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query or keyword (e.g. 'Project', 'Notes')"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_notion_page",
            "description": "Create a new page in the user's Notion workspace with a title and optional body text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Title of the new Notion page"
                    },
                    "content": {
                        "type": "string",
                        "description": "Optional body text content for the page"
                    },
                    "parent_page_id": {
                        "type": "string",
                        "description": "Optional parent page or database ID"
                    }
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_notion_page_content",
            "description": "Fetch and read text content and blocks from a specific Notion page ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "string",
                        "description": "The ID of the Notion page"
                    }
                },
                "required": ["page_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "append_notion_block",
            "description": "Append text blocks or notes to an existing Notion page by ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_id": {
                        "type": "string",
                        "description": "The ID of the Notion page"
                    },
                    "content": {
                        "type": "string",
                        "description": "Text content to append to the page"
                    }
                },
                "required": ["page_id", "content"]
            }
        }
    }
]

# 3. Map tool names to Python implementations
import google_calendar_tool
import web_search_tool
import notion_tool

AVAILABLE_FUNCTIONS = {
    "get_user_profile": github_mcp.get_user_profile,
    "get_user_repositories": github_mcp.get_user_repositories,
    "search_repositories": github_mcp.search_repositories,
    "summarize_repo_readme": github_mcp.summarize_repo_readme,
    "list_upcoming_calendar_events": google_calendar_tool.list_upcoming_calendar_events,
    "create_calendar_event": google_calendar_tool.create_calendar_event,
    "delete_calendar_event": google_calendar_tool.delete_calendar_event,
    "search_emails": gmail_tool.search_emails,
    "summarize_unread_inbox": gmail_tool.summarize_unread_inbox,
    "create_email_draft": gmail_tool.create_email_draft,
    "store_text_data": db_tool.store_text_data,
    "store_file": db_tool.store_file,
    "search_database": db_tool.search_database,
    "list_stored_documents": db_tool.list_stored_documents,
    "get_document": db_tool.get_document,
    "update_document": db_tool.update_document,
    "delete_document": db_tool.delete_document,
    "list_google_tasks": tasks_tool.list_google_tasks,
    "create_google_task": tasks_tool.create_google_task,
    "complete_google_task": tasks_tool.complete_google_task,
    "get_daily_briefing": tasks_tool.get_daily_briefing,
    "search_web": web_search_tool.search_web,
    "scrape_url": web_search_tool.scrape_url,
    "analyze_content": web_search_tool.analyze_content,
    "search_notion": notion_tool.search_notion,
    "create_notion_page": notion_tool.create_notion_page,
    "get_notion_page_content": notion_tool.get_notion_page_content,
    "append_notion_block": notion_tool.append_notion_block,
}



class Colors:
    CYAN = "\033[1;36m"
    GREEN = "\033[1;32m"
    YELLOW = "\033[1;33m"
    MAGENTA = "\033[1;35m"
    BLUE = "\033[1;34m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


class AutonomousAgent:
    """
    An Autonomous ReAct (Reason + Act) Agent powered by Groq Llama 3.3.
    It maintains conversation history across chat turns, remembers user details,
    and dynamically calls tools (GitHub, Google Calendar & Web Search/Scraping) when needed.
    """
    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        self.model = model
        self._build_system_prompt()
        self.messages = [{"role": "system", "content": self.system_prompt}]
        
        # CloudGuard Client Setup
        self.cloudguard_client = None
        if CLOUDGUARD_AVAILABLE:
            gateway_url = os.getenv("CLOUDGUARD_URL", "http://localhost:8000")
            api_key = os.getenv("CLOUDGUARD_API_KEY", "cg_live_custommcp_key")
            agent_id = os.getenv("CLOUDGUARD_AGENT_ID", "00000000-0000-0000-0000-000000000002")
            try:
                self.cloudguard_client = CloudGuardClient(
                    gateway_url=gateway_url,
                    api_key=api_key,
                    agent_id=agent_id,
                )
            except Exception as e:
                print(f"{Colors.YELLOW}[CloudGuard Warning]: Failed to init client: {e}{Colors.RESET}")

    def _build_system_prompt(self):
        """Build system prompt with the current date/time injected."""
        from datetime import datetime
        now = datetime.now()
        current_dt = now.strftime("%A, %d %B %Y, %I:%M %p IST")
        current_iso = now.strftime("%Y-%m-%dT%H:%M:%S+05:30")
        tomorrow = (now.replace(hour=0, minute=0, second=0) 
                    .__class__(now.year, now.month, now.day) 
                    .__add__(__import__('datetime').timedelta(days=1)))
        tomorrow_iso_start = tomorrow.strftime("%Y-%m-%dT09:00:00+05:30")
        tomorrow_iso_end   = tomorrow.strftime("%Y-%m-%dT10:00:00+05:30")

        # Load stored user entries from SQLite database for persistent memory
        user_memory_context = ""
        try:
            import sqlite3
            conn = sqlite3.connect(db_tool.DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT title, content_text, tags FROM documents ORDER BY id DESC LIMIT 15"
            )
            rows = cursor.fetchall()
            conn.close()
            if rows:
                memory_entries = []
                for title, content, tags in rows:
                    content_str = (content or "").replace('\n', ' ')[:150]
                    tag_str = f" [tags: {tags}]" if tags else ""
                    memory_entries.append(f"- [{title}]{tag_str}: {content_str}")
                user_memory_context = "\nSTORED USER DATA & PERSISTENT MEMORY (from SQL Database):\n" + "\n".join(memory_entries) + "\n"
        except Exception:
            pass

        self.system_prompt = f"""
You are an Autonomous AI Assistant with tools for GitHub, Google Calendar, Gmail, Google Tasks, SQL Storage, and Web Search.

TODAY'S DATE & TIME: {current_dt}
CURRENT ISO TIMESTAMP: {current_iso}
TOMORROW DATE (for reference): {tomorrow_iso_start} to {tomorrow_iso_end}
{user_memory_context}
ALWAYS use the correct current year ({now.year}) when creating calendar events. Never use past years.

CRITICAL RULES — follow these strictly:
1. For greetings (hi, hello, hey) or casual chat — respond conversationally. DO NOT call any tools.
2. NEVER call a tool with placeholder values like 'null', 'example', 'test', 'N/A', or made-up usernames.
3. ONLY call a tool when the user has given you real required information.
4. If the user asks to "list", "show", or "what are your tools" — describe them in plain text. Do NOT call any tool.
5. If required information is missing, ask the user for it before calling any tool.
6. After a tool returns a result, give the user a FINAL TEXT ANSWER. Do NOT call the same tool again.
7. Each tool should only be called ONCE per user request unless the user explicitly asks for more.
8. RETRIEVING STORED USER INFORMATION: If the user asks about their name, identity, owner details, saved notes, or past stored information (e.g. 'what is my name?', 'who am I?', 'what did I store?'), check the STORED USER DATA section above or call search_database(query=...) / list_stored_documents() BEFORE answering. NEVER say you don't know without checking stored database entries first!

Available tools:

GITHUB TOOLS:
- get_user_profile(username)          → GitHub profile info
- get_user_repositories(username)     → List user repos
- search_repositories(query)          → Search GitHub repos
- summarize_repo_readme(owner, repo)  → Summarize a repo README with AI
- analyze_user_repositories(username) → AI analysis of all user repos
- ask_groq_ai(prompt)                 → Ask Groq AI a general question

CALENDAR TOOLS:
- list_upcoming_calendar_events()     → Show upcoming Google Calendar events
- create_calendar_event(...)          → Create a new calendar event
- delete_calendar_event(summary)      → Delete a calendar event by title

GMAIL TOOLS:
- search_emails(query)                → Search emails in Gmail
- summarize_unread_inbox()            → Executive AI summary of unread emails
- create_email_draft(to, sub, body)   → Create an email draft in Gmail

SQL DATABASE STORAGE TOOLS:
- store_text_data(title, content)     → Store text notes or code snippets in SQL
- store_file(file_path, title)        → Store local images, PDFs, or files in SQL
- search_database(query)              → Search stored items in SQL by keyword
- list_stored_documents()             → List stored documents in SQL
- get_document(doc_id)                → Retrieve full content of a stored item by ID
- update_document(doc_id, ...)        → Update document title, content, or tags by ID
- delete_document(doc_id)             → Delete a document from SQL database by ID

GOOGLE TASKS & DAILY BRIEFING TOOLS:
- list_google_tasks()                 → List to-dos/tasks from Google Tasks
- create_google_task(title, notes)    → Create a new to-do task item
- complete_google_task(task_id)       → Mark a Google Task as completed
- get_daily_briefing()                → Executive Daily Morning AI Briefing (Calendar + Gmail + Tasks + News)

WEB & ANALYSIS TOOLS:
- search_web(query)                   → DuckDuckGo web search
- scrape_url(url)                     → Scrape text from any webpage URL
- analyze_content(content, type)      → AI analysis: summarize/risk/links/key_info

NOTION WORKSPACE TOOLS:
- search_notion(query)                → Search pages & databases in Notion
- create_notion_page(title, content)  → Create a new Notion page
- get_notion_page_content(page_id)    → Read text content & blocks of a Notion page
- append_notion_block(page_id, text)  → Append text notes to a Notion page
"""


    def reset_memory(self):
        """Reset conversation memory and refresh the date in system prompt."""
        self._build_system_prompt()
        self.messages = [{"role": "system", "content": self.system_prompt}]
        print(f"{Colors.YELLOW}[Memory] Conversation memory cleared.{Colors.RESET}")

    def run(self, user_prompt: str, max_turns: int = 5) -> str:
        # Refresh date in system prompt on every new user message
        self._build_system_prompt()
        self.messages[0] = {"role": "system", "content": self.system_prompt}

        # Append user prompt to ongoing conversation memory
        self.messages.append({"role": "user", "content": user_prompt})

        # Trim memory if it gets too long (keep system prompt + last 12 messages)
        if len(self.messages) > 14:
            self.messages = [self.messages[0]] + self.messages[-12:]

        turn = 0
        last_tool_signature = None   # tracks last tool call for loop detection
        last_tool_output = ""        # tracks last tool result
        fallback_models = [self.model, "llama-3.1-8b-instant", "mixtral-8x7b-32768"]
        
        while turn < max_turns:
            turn += 1
            
            response = None
            for model_candidate in fallback_models:
                try:
                    response = groq_client.chat.completions.create(
                        model=model_candidate,
                        messages=self.messages,
                        tools=TOOLS_SCHEMAS,
                        tool_choice="auto",
                        temperature=0.2
                    )
                    break
                except Exception as e:
                    err_str = str(e).lower()
                    if "rate_limit" in err_str or "429" in err_str or "rate limit" in err_str:
                        print(f"{Colors.YELLOW}[Warning] Model '{model_candidate}' rate limited. Trying fallback model...{Colors.RESET}")
                        continue
                    else:
                        print(f"[Error] Groq API Error ({model_candidate}): {str(e)}")
                        return f"API Error: {str(e)}"

            if not response:
                print("[Error] All Groq models rate limited. Please wait a few minutes before trying again.")
                return "All models are currently rate limited. Please try again in a few minutes."

            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls

            # Append the assistant's response/thought message to conversation memory
            self.messages.append(response_message)

            # If the LLM did not request any tool calls, it has reached its final answer!
            if not tool_calls:
                print(f"\n{Colors.GREEN}{response_message.content}{Colors.RESET}")
                return response_message.content


            # If the LLM requested tool calls, execute each tool function
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                raw_args = tool_call.function.arguments
                function_args = json.loads(raw_args) if raw_args else {}
                if function_args is None:
                    function_args = {}

                # ── Loop detection ────────────────────────────────────────
                current_signature = (function_name, str(function_args))
                if current_signature == last_tool_signature:
                    msg = (
                        f"I already checked {function_name.replace('_', ' ')} "
                        f"and the result was: {str(last_tool_output)}"
                    )
                    print(f"{Colors.YELLOW}[Loop Detected] Stopping repeated tool call.{Colors.RESET}")
                    print(f"\n{Colors.GREEN}{msg}{Colors.RESET}")
                    return msg
                last_tool_signature = current_signature
                # ─────────────────────────────────────────────────────────

                print(f"{Colors.YELLOW}[Executing Tool]: Calling [{function_name}] with args: {function_args}{Colors.RESET}")

                # 🛡️ CloudGuard Security Evaluation
                if self.cloudguard_client:
                    try:
                        eval_res = self.cloudguard_client.execute(
                            tool_name=function_name,
                            parameters=function_args,
                            raise_on_deny=False,
                        )
                        decision = eval_res.get("decision", "ALLOW")
                        reason = eval_res.get("reason", "Allowed by policy")
                        risk_score = eval_res.get("risk_score", 0)

                        if decision == "DENY":
                            print(f"{Colors.YELLOW}🛡️ [CloudGuard Security Gateway]: DENIED [{function_name}] (risk: {risk_score}/100) — Reason: {reason}{Colors.RESET}")
                            last_tool_output = f"Security Policy Blocked Execution of '{function_name}': {reason}"
                            self.messages.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": str(last_tool_output)
                            })
                            continue
                        elif decision == "ESCALATE":
                            print(f"{Colors.YELLOW}🛡️ [CloudGuard Security Gateway]: ESCALATED [{function_name}] (risk: {risk_score}/100) — Reason: {reason}{Colors.RESET}")
                            last_tool_output = f"Security Escalation Required for '{function_name}': {reason}"
                            self.messages.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": str(last_tool_output)
                            })
                            continue
                        else:
                            print(f"{Colors.GREEN}🛡️ [CloudGuard Security Gateway]: ALLOWED [{function_name}] (risk: {risk_score}/100){Colors.RESET}")
                    except Exception as cg_err:
                        print(f"{Colors.YELLOW}🛡️ [CloudGuard Warning]: Gateway evaluation skipped: {cg_err}{Colors.RESET}")

                # Execute Python function
                function_to_call = AVAILABLE_FUNCTIONS.get(function_name)
                if function_to_call:
                    last_tool_output = function_to_call(**function_args)
                else:
                    last_tool_output = f"Error: Tool '{function_name}' not found."

                print(f"{Colors.DIM}[Tool Output Received] ({len(str(last_tool_output))} chars){Colors.RESET}\n")

                # Send tool execution result back to conversation memory
                self.messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": str(last_tool_output)
                })

        return "Agent reached maximum execution steps without concluding."


HELP_TEXT = f"""
{Colors.CYAN}{'='*60}
  Custom AI Agent — Available Commands & Tools
{'='*60}{Colors.RESET}

{Colors.BOLD}Built-in Commands:{Colors.RESET}
  help          → Show this help menu
  reset         → Clear conversation memory
  exit / quit   → Exit the agent

{Colors.BOLD}🐙 GitHub Tools:{Colors.RESET}
  "Get GitHub profile of torvalds"
  "Show repositories of <username>"
  "Search GitHub repos for fastmcp"
  "Summarize README of owner/repo"
  "Analyze all repos of <username>"

{Colors.BOLD}💾 SQL Database Tools (Full CRUD):{Colors.RESET}
  "Store note title: X, content: Y"
  "Search database for <keyword>"
  "List stored documents"
  "Get document <ID>"
  "Update document <ID> title/content/tags"
  "Delete document <ID>"

{Colors.BOLD}📅 Calendar Tools:{Colors.RESET}
  "Show my upcoming calendar events"
  "Create a meeting called X on <date> at <time>"
  "Delete calendar event called X"

{Colors.BOLD}🌐 Web Tools:{Colors.RESET}
  "Search the web for <topic>"
  "Scrape and summarize <URL>"

{Colors.BOLD}📝 Notion Workspace Tools:{Colors.RESET}
  "Search Notion for <query>"
  "Create a Notion page titled X with content Y"
  "Read Notion page <ID>"
  "Append note Z to Notion page <ID>"

{Colors.BOLD}🤖 AI Tools:{Colors.RESET}
  "Ask AI: <any question>"
  "Analyze this content: <text>"
{Colors.CYAN}{'='*60}{Colors.RESET}
"""

if __name__ == "__main__":
    agent = AutonomousAgent()

    print(f"{Colors.CYAN}")
    print("  ╔═════════════════════════════════════════════════════╗")
    print("  ║      Custom AI Agent — MCP Powered  🚀             ║")
    print("  ║  GitHub · Calendar · Gmail · Tasks · SQL · Notion   ║")
    print("  ╚═════════════════════════════════════════════════════╝")
    print(f"{Colors.RESET}")
    print(f"  {Colors.DIM}Type 'help' to see all tools, 'exit' to quit{Colors.RESET}\n")

    while True:
        try:
            prompt = input(f"{Colors.BLUE}Enter prompt > {Colors.RESET}").strip()

            if not prompt:
                continue
            if prompt.lower() in ["exit", "quit"]:
                print(f"{Colors.YELLOW}Goodbye!{Colors.RESET}")
                break
            if prompt.lower() == "reset":
                agent.reset_memory()
                continue
            if prompt.lower() in ["help", "?", "tools", "functions"]:
                print(HELP_TEXT)
                continue

            agent.run(prompt)

        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Interrupted. Type 'exit' to quit.{Colors.RESET}")
            continue
