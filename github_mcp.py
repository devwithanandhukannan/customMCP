import os
import requests
from dotenv import load_dotenv
from fastmcp import FastMCP
from groq import Groq

# Load environment variables
load_dotenv()

# Initialize Groq client
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ─────────────────────────────────────────────────────────────────────────────
# Unified MCP Server — All Tools in One Place
#   • GitHub        → profile, repos, search, README summary, AI repo analysis
#   • Google Cal    → list, create, delete events
#   • Gmail         → search emails, AI unread inbox summary, create email drafts
#   • Google Tasks  → list tasks, create task, complete task, get_daily_briefing
#   • SQL Database  → store text/notes, store files/images/PDFs, search DB, list, get doc
#   • Web           → DuckDuckGo search, URL scraper, AI content analysis
# ─────────────────────────────────────────────────────────────────────────────
mcp = FastMCP(
    "Custom AI Agent MCP Server — GitHub · Calendar · Gmail · Tasks · Briefing · SQL DB · Web"
)



def get_headers():
    """Helper: GitHub API authentication headers."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


# =============================================================================
# GITHUB TOOLS
# =============================================================================

@mcp.tool()
def get_user_profile(username: str) -> str:
    """
    Fetch public profile details of a GitHub user.

    Args:
        username: The GitHub username (e.g. 'torvalds')
    """
    url = f"https://api.github.com/users/{username}"
    response = requests.get(url, headers=get_headers())

    if response.status_code == 404:
        return f"User '{username}' not found."
    elif response.status_code != 200:
        return f"Error: Received status code {response.status_code}"

    data = response.json()
    return (
        f"GitHub User: {data.get('login')}\n"
        f"- Name: {data.get('name', 'N/A')}\n"
        f"- Bio: {data.get('bio', 'N/A')}\n"
        f"- Location: {data.get('location', 'N/A')}\n"
        f"- Public Repositories: {data.get('public_repos', 0)}\n"
        f"- Followers: {data.get('followers', 0)}\n"
        f"- Profile Link: {data.get('html_url')}"
    )


@mcp.tool()
def get_user_repositories(username: str, limit: int = 5) -> str:
    """
    Get recent public repositories for a GitHub user.

    Args:
        username: The GitHub username
        limit: Number of repositories to fetch (default: 5)
    """
    url = f"https://api.github.com/users/{username}/repos?sort=updated&per_page={limit}"
    response = requests.get(url, headers=get_headers())

    if response.status_code != 200:
        return f"Error: Received status code {response.status_code}"

    repos = response.json()
    if not repos:
        return f"No public repositories found for '{username}'."

    output = [f"Top Repositories for {username}:"]
    for repo in repos:
        output.append(
            f"\n- {repo['name']} (Stars: {repo['stargazers_count']})\n"
            f"  Description: {repo.get('description') or 'No description'}\n"
            f"  Language: {repo.get('language') or 'N/A'}\n"
            f"  URL: {repo['html_url']}"
        )
    return "\n".join(output)


@mcp.tool()
def search_repositories(query: str, limit: int = 5) -> str:
    """
    Search GitHub repositories by keyword or query string.

    Args:
        query: Search query (e.g. 'fastmcp' or 'python web framework')
        limit: Max results to return (default: 5)
    """
    url = f"https://api.github.com/search/repositories?q={query}&per_page={limit}"
    response = requests.get(url, headers=get_headers())

    if response.status_code != 200:
        return f"Error: Received status code {response.status_code}"

    items = response.json().get("items", [])
    if not items:
        return f"No repositories found matching '{query}'."

    output = [f"Search Results for '{query}':"]
    for repo in items:
        output.append(
            f"\n- {repo['full_name']} (Stars: {repo['stargazers_count']})\n"
            f"  Description: {repo.get('description') or 'No description'}\n"
            f"  URL: {repo['html_url']}"
        )
    return "\n".join(output)


@mcp.tool()
def summarize_repo_readme(owner: str, repo: str) -> str:
    """
    Fetch a repository's README and use Groq AI (Llama 3.3) to summarize it.

    Args:
        owner: GitHub repository owner (e.g. 'jlowin')
        repo: Repository name (e.g. 'fastmcp')
    """
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/README.md"
    res = requests.get(url)
    if res.status_code == 404:
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/master/README.md"
        res = requests.get(url)
    if res.status_code != 200:
        return f"Could not fetch README for {owner}/{repo} (Status {res.status_code})."

    readme_text = res.text[:8000]
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful software engineering assistant. "
                        "Summarize README files into 3 sections: "
                        "1. Overview & Purpose, 2. Key Features, 3. How to Get Started."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Summarize this README for '{owner}/{repo}':\n\n{readme_text}",
                },
            ],
            temperature=0.3,
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error calling Groq API: {str(e)}"


@mcp.tool()
def analyze_user_repositories(
    username: str,
    question: str = "Summarize all repositories and highlight key projects and tech stacks",
) -> str:
    """
    Fetch a GitHub user's repositories and use Groq AI to analyze them.

    Args:
        username: GitHub username (e.g. 'torvalds')
        question: Specific analysis question or instruction for Groq AI
    """
    repo_data = get_user_repositories(username, limit=20)
    profile_data = get_user_profile(username)

    if "not found" in repo_data.lower() or "error" in repo_data.lower():
        return repo_data

    prompt_content = (
        f"GitHub profile and repositories for user '{username}':\n\n"
        f"--- PROFILE ---\n{profile_data}\n\n"
        f"--- REPOSITORIES ---\n{repo_data}\n\n"
        f"--- INSTRUCTION ---\n{question}"
    )
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert AI code analyst. Analyze GitHub repositories and give clear, well-structured summaries.",
                },
                {"role": "user", "content": prompt_content},
            ],
            temperature=0.3,
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error from Groq AI analysis: {str(e)}"


@mcp.tool()
def ask_groq_ai(prompt: str) -> str:
    """
    Ask Groq AI (Llama 3.3) any general question or request code analysis.

    Args:
        prompt: Question or prompt for Groq AI
    """
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error from Groq AI: {str(e)}"


# =============================================================================
# GOOGLE CALENDAR TOOLS
# =============================================================================
import google_calendar_tool


@mcp.tool()
def list_upcoming_calendar_events(max_results: int = 5) -> str:
    """
    Fetch upcoming events from the user's primary Google Calendar.

    Args:
        max_results: Max number of events to fetch (default: 5)
    """
    return google_calendar_tool.list_upcoming_calendar_events(max_results=max_results)


@mcp.tool()
def create_calendar_event(
    summary: str, start_time: str, end_time: str, description: str = ""
) -> str:
    """
    Create a new event in the user's Google Calendar.

    Args:
        summary: Event title / summary
        start_time: ISO timestamp for start (e.g. '2026-08-02T10:00:00+05:30')
        end_time: ISO timestamp for end (e.g. '2026-08-02T11:00:00+05:30')
        description: Optional notes or description for the event
    """
    return google_calendar_tool.create_calendar_event(
        summary=summary,
        start_time=start_time,
        end_time=end_time,
        description=description,
    )


@mcp.tool()
def delete_calendar_event(event_summary: str) -> str:
    """
    Find and delete an event from Google Calendar by title/summary keyword.

    Args:
        event_summary: Event title keyword to find and delete (e.g. 'Team Standup')
    """
    return google_calendar_tool.delete_calendar_event(event_summary=event_summary)


# =============================================================================
# WEB SEARCH & SCRAPING TOOLS
# =============================================================================
import web_search_tool


@mcp.tool()
def search_web(query: str, max_results: int = 5) -> str:
    """
    Search the live web using DuckDuckGo for news, docs, and articles.

    Args:
        query: Search query string (e.g. 'latest Python 3.13 features')
        max_results: Max results to return (default: 5)
    """
    return web_search_tool.search_web(query=query, max_results=max_results)


@mcp.tool()
def scrape_url(url: str) -> str:
    """
    Scrape and extract readable text content from any clearnet webpage URL.

    Args:
        url: The webpage URL to scrape (must be http:// or https://)
    """
    return web_search_tool.scrape_url(url=url)


@mcp.tool()
def analyze_content(content: str, analysis_type: str = "summarize") -> str:
    """
    Analyze any text content using Groq AI (Llama 3.3).
    Use after scraping a webpage or from raw text.

    Args:
        content: The raw text content to analyze
        analysis_type: One of:
            'summarize'       → concise bullet-point summary
            'risk_assessment' → detect risks/threats (rated LOW/MEDIUM/HIGH)
            'extract_links'   → list all URLs, emails, and web references found
            'key_info'        → extract names, dates, facts, organizations
    """
    return web_search_tool.analyze_content(
        content=content, analysis_type=analysis_type
    )



# =============================================================================
# GMAIL TOOLS
# =============================================================================
import gmail_tool


@mcp.tool()
def search_emails(query: str = "is:unread", max_results: int = 5) -> str:
    """
    Search messages in Gmail inbox matching a query string (e.g. 'is:unread', 'from:github').

    Args:
        query: Gmail search query string (default: 'is:unread')
        max_results: Max number of messages to fetch (default: 5)
    """
    return gmail_tool.search_emails(query=query, max_results=max_results)


@mcp.tool()
def summarize_unread_inbox(max_results: int = 5) -> str:
    """
    Fetch unread emails and use Groq AI (Llama 3.3) to generate an executive summary.

    Args:
        max_results: Max number of unread emails to analyze (default: 5)
    """
    return gmail_tool.summarize_unread_inbox(max_results=max_results)


@mcp.tool()
def create_email_draft(to: str, subject: str, body: str) -> str:
    """
    Create a new draft email in Gmail.

    Args:
        to: Recipient email address
        subject: Email subject line
        body: Text content of the email
    """
    return gmail_tool.create_email_draft(to=to, subject=subject, body=body)



# =============================================================================
# SQL DATABASE STORAGE TOOLS
# =============================================================================
import db_tool


@mcp.tool()
def store_text_data(title: str, content: str, tags: str = "") -> str:
    """
    Store text notes, code snippets, or structured information in the SQL database.

    Args:
        title: Short title or header for the text entry
        content: The text body or content to store
        tags: Optional comma-separated tags (e.g. 'notes, meeting, python')
    """
    return db_tool.store_text_data(title=title, content=content, tags=tags)


@mcp.tool()
def store_file(file_path: str, title: str = "", tags: str = "") -> str:
    """
    Read any local file (Image, PDF, Document, Code, Data) and store it in the SQL database.

    Args:
        file_path: Path to the local file (e.g. '/path/to/image.png' or 'doc.pdf')
        title: Optional title (defaults to filename)
        tags: Optional comma-separated tags (e.g. 'pdf, invoice, research')
    """
    return db_tool.store_file(file_path=file_path, title=title, tags=tags)


@mcp.tool()
def search_database(query: str, file_type: str = "all") -> str:
    """
    Search stored documents, images, PDFs, and notes in the SQL database by title, content, or tags.

    Args:
        query: Search term or keyword
        file_type: Filter by type ('all', 'text', 'pdf', 'image', 'data')
    """
    return db_tool.search_database(query=query, file_type=file_type)


@mcp.tool()
def list_stored_documents(limit: int = 10) -> str:
    """
    List stored documents, images, PDFs, and text notes in the SQL database.

    Args:
        limit: Max number of items to list (default: 10)
    """
    return db_tool.list_stored_documents(limit=limit)


@mcp.tool()
def get_document(doc_id: int) -> str:
    """
    Fetch full text content and metadata for a document in the SQL database by ID.

    Args:
        doc_id: Integer ID of the document to retrieve
    """
    return db_tool.get_document(doc_id=doc_id)


@mcp.tool()
def update_document(
    doc_id: int, title: str = None, content: str = None, tags: str = None
) -> str:
    """
    Update an existing document's title, content, or tags in the SQL database by ID.

    Args:
        doc_id: Integer ID of the document to update
        title: Optional new title for the document
        content: Optional new text content for the document
        tags: Optional new comma-separated tags
    """
    return db_tool.update_document(
        doc_id=doc_id, title=title, content=content, tags=tags
    )


@mcp.tool()
def delete_document(doc_id: int) -> str:
    """
    Delete a document from the SQL database by its ID.

    Args:
        doc_id: Integer ID of the document to delete
    """
    return db_tool.delete_document(doc_id=doc_id)




# =============================================================================
# GOOGLE TASKS & DAILY AI BRIEFING TOOLS
# =============================================================================
import tasks_tool


@mcp.tool()
def list_google_tasks(show_completed: bool = False) -> str:
    """
    List tasks/to-dos from the user's primary Google Tasks list.

    Args:
        show_completed: Whether to include completed tasks (default: False)
    """
    return tasks_tool.list_google_tasks(show_completed=show_completed)


@mcp.tool()
def create_google_task(title: str, notes: str = "", due_date: str = "") -> str:
    """
    Create a new task item on the user's primary Google Tasks list.

    Args:
        title: Task title or description
        notes: Optional additional notes
        due_date: Optional due date (YYYY-MM-DD format)
    """
    return tasks_tool.create_google_task(title=title, notes=notes, due_date=due_date)


@mcp.tool()
def complete_google_task(task_id: str) -> str:
    """
    Mark a task as completed on the user's primary Google Tasks list.

    Args:
        task_id: The ID of the task to complete
    """
    return tasks_tool.complete_google_task(task_id=task_id)


@mcp.tool()
def get_daily_briefing() -> str:
    """
    Synthesize an executive Morning Daily AI Briefing by aggregating:
    - Upcoming Google Calendar events
    - Unread Gmail inbox summaries
    - Pending Google Tasks / to-dos
    - Live morning news headlines
    """
    return tasks_tool.get_daily_briefing()


# =============================================================================
# RUN MCP SERVER
# =============================================================================
if __name__ == "__main__":
    mcp.run()



