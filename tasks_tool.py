import os.path
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from groq import Groq
from dotenv import load_dotenv

import google_calendar_tool
import gmail_tool
import web_search_tool

# Load environment variables
load_dotenv()

# Groq client for AI Daily Briefing generation
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Google Tasks API Scope
SCOPES = ['https://www.googleapis.com/auth/tasks']

CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'tasks_token.json'


def get_tasks_service():
    """
    Authenticates with Google Tasks API using OAuth 2.0.
    Generates tasks_token.json on first run.
    """
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                return None, f"Missing '{CREDENTIALS_FILE}'. Please download OAuth Desktop credentials from Google Cloud Console."
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    service = build('tasks', 'v1', credentials=creds)
    return service, None


def list_google_tasks(show_completed: bool = False) -> str:
    """
    List tasks/to-dos from the user's primary Google Tasks list.

    Args:
        show_completed: Whether to include completed tasks (default: False)
    """
    service, err = get_tasks_service()
    if err:
        return f"Google Tasks Setup Required: {err}"

    try:
        results = service.tasks().list(
            tasklist='@default',
            showCompleted=show_completed,
            showHidden=False
        ).execute()

        items = results.get('items', [])
        if not items:
            return "No pending Google Tasks found."

        output = [f"Pending Google Tasks ({len(items)} items):\n"]
        for idx, task in enumerate(items, 1):
            title = task.get('title', 'Untitled Task')
            status = task.get('status', 'needsAction')
            due = task.get('due', '')
            due_str = f" (Due: {due[:10]})" if due else ""
            notes = task.get('notes', '')
            notes_str = f"\n   Notes: {notes}" if notes else ""
            task_id = task.get('id', '')

            output.append(f"{idx}. [{status.upper()}] {title}{due_str} - ID: {task_id}{notes_str}")

        return "\n".join(output)

    except Exception as e:
        return f"Error fetching Google Tasks: {str(e)}"


def create_google_task(title: str, notes: str = "", due_date: str = "") -> str:
    """
    Create a new task item on the user's primary Google Tasks list.

    Args:
        title: Task title or description
        notes: Optional additional notes or details
        due_date: Optional due date in YYYY-MM-DD or RFC3339 format
    """
    service, err = get_tasks_service()
    if err:
        return f"Google Tasks Setup Required: {err}"

    try:
        task_body = {
            'title': title,
            'notes': notes
        }
        if due_date:
            if len(due_date) == 10:
                due_date += "T00:00:00.000Z"
            task_body['due'] = due_date

        created_task = service.tasks().insert(tasklist='@default', body=task_body).execute()
        return f"Task created successfully in Google Tasks!\n- Title: '{created_task.get('title')}'\n- Task ID: {created_task.get('id')}"

    except Exception as e:
        return f"Error creating Google Task: {str(e)}"


def complete_google_task(task_id: str) -> str:
    """
    Mark a task as completed on the user's primary Google Tasks list.

    Args:
        task_id: The ID of the Google Task to complete
    """
    service, err = get_tasks_service()
    if err:
        return f"Google Tasks Setup Required: {err}"

    try:
        service.tasks().patch(
            tasklist='@default',
            task=task_id,
            body={'status': 'completed'}
        ).execute()
        return f"Successfully marked Google Task ID '{task_id}' as COMPLETED!"

    except Exception as e:
        return f"Error marking Google Task as completed: {str(e)}"


def get_daily_briefing() -> str:
    """
    Synthesize an executive Morning Daily AI Briefing by aggregating:
    - Upcoming Google Calendar events
    - Unread Gmail inbox summaries
    - Pending Google Tasks
    - Top news headlines
    """
    now_str = datetime.now().strftime("%A, %d %B %Y, %I:%M %p")

    # 1. Fetch Calendar Events
    calendar_data = google_calendar_tool.list_upcoming_calendar_events(max_results=5)

    # 2. Fetch Unread Email Info
    email_data = gmail_tool.search_emails(query="is:unread", max_results=5)

    # 3. Fetch Google Tasks
    tasks_data = list_google_tasks(show_completed=False)

    # 4. Fetch Top Headlines
    news_data = web_search_tool.search_web(query="top news headlines today", max_results=3)

    prompt = f"""
Synthesize an executive, high-impact Daily Morning Briefing for the user.

CURRENT DATE & TIME: {now_str}

--- DATA STREAM 1: GOOGLE CALENDAR ---
{calendar_data}

--- DATA STREAM 2: UNREAD EMAILS ---
{email_data}

--- DATA STREAM 3: GOOGLE TASKS ---
{tasks_data}

--- DATA STREAM 4: LIVE NEWS HEADLINES ---
{news_data}

--- FORMATTING INSTRUCTIONS ---
Format your response as a polished executive briefing using clean Markdown:
# 🌅 Executive Daily Briefing — {now_str}

1. **📅 Today's Schedule & Meetings**: Highlight upcoming events and times.
2. **📩 Inbox & Priority Emails**: Key email updates needing attention.
3. **✅ Priority Tasks & Action Items**: Top to-do list items for today.
4. **📰 Morning Headlines**: Brief summary of top news.
5. **💡 Productivity Focus**: A 1-sentence recommended focus area for today.
"""

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are an elite executive AI chief of staff. Provide crisp, structured, elegant daily briefings."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error generating Daily AI Briefing with Groq: {str(e)}"
