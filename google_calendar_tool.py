import os.path
from datetime import datetime, timezone
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar']

CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'

def get_calendar_service():
    """
    Authenticates with Google Calendar API using OAuth 2.0.
    Generates token.json on first run.
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

    service = build('calendar', 'v3', credentials=creds)
    return service, None

def list_upcoming_calendar_events(max_results: int = 25, date: str = None, **kwargs) -> str:
    """
    List upcoming events from the user's primary Google Calendar.
    
    Args:
        max_results: Max number of events to fetch (default: 25)
        date: Optional date string in YYYY-MM-DD format (e.g. '2026-08-03') to filter events for a specific day
    """
    service, err = get_calendar_service()
    if err:
        return f"Google Calendar Setup Required: {err}"
        
    try:
        if date and str(date).strip():
            date_clean = str(date).strip().split("T")[0]
            time_min = f"{date_clean}T00:00:00+05:30"
            time_max = f"{date_clean}T23:59:59+05:30"
        else:
            time_min = datetime.now(timezone.utc).isoformat()
            time_max = None

        params = {
            'calendarId': 'primary',
            'timeMin': time_min,
            'maxResults': max_results,
            'singleEvents': True,
            'orderBy': 'startTime'
        }
        if time_max:
            params['timeMax'] = time_max

        events_result = service.events().list(**params).execute()
        events = events_result.get('items', [])

        if not events:
            return f"No calendar events found" + (f" for {date}." if date else ".")

        output = [f"Google Calendar Events" + (f" for {date}:" if date else ":")]
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            summary = event.get('summary', 'No Title')
            description = event.get('description', '')
            output.append(f"- [{start}] {summary}" + (f" - {description}" if description else ""))

        return "\n".join(output)
    except Exception as e:
        return f"Error accessing Google Calendar API: {str(e)}"

def create_calendar_event(summary: str, start_time: str, end_time: str, description: str = "") -> str:
    """
    Create a new event on the user's primary Google Calendar.
    
    Args:
        summary: Event title / topic
        start_time: Start time in ISO format (e.g. '2026-08-02T10:00:00+05:30')
        end_time: End time in ISO format (e.g. '2026-08-02T11:00:00+05:30')
        description: Optional event notes or description
    """
    service, err = get_calendar_service()
    if err:
        return f"Google Calendar Setup Required: {err}"
        
    try:
        event_body = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': start_time},
            'end': {'dateTime': end_time},
        }

        created_event = service.events().insert(calendarId='primary', body=event_body).execute()
        return f"Event created successfully! Title: '{created_event.get('summary')}', Link: {created_event.get('htmlLink')}"
    except Exception as e:
        return f"Error creating event on Google Calendar: {str(e)}"

def delete_calendar_event(event_summary: str = "", date: str = None, delete_all: bool = False, **kwargs) -> str:
    """
    Find and delete event(s) from the user's primary Google Calendar by title/summary keyword or date.
    
    Args:
        event_summary: Summary or title keyword of the event to delete (e.g. 'Interview' or 'all')
        date: Optional date string in YYYY-MM-DD format to delete all events on that day
        delete_all: If True, deletes all matching events instead of just the first match
    """
    service, err = get_calendar_service()
    if err:
        return f"Google Calendar Setup Required: {err}"
        
    try:
        if date and str(date).strip():
            date_clean = str(date).strip().split("T")[0]
            time_min = f"{date_clean}T00:00:00+05:30"
            time_max = f"{date_clean}T23:59:59+05:30"
        else:
            time_min = datetime.now(timezone.utc).isoformat()
            time_max = None

        params = {
            'calendarId': 'primary',
            'timeMin': time_min,
            'maxResults': 100,
            'singleEvents': True,
            'orderBy': 'startTime'
        }
        if time_max:
            params['timeMax'] = time_max

        events_result = service.events().list(**params).execute()
        events = events_result.get('items', [])

        deleted_count = 0
        deleted_summaries = []

        query = (event_summary or "").strip().lower()

        for event in events:
            summary = event.get('summary', '').lower()
            description = event.get('description', '').lower()
            
            is_match = False
            if (date or delete_all) and (not query or query in ["all", "*", "everything", "all events"]):
                is_match = True
            elif query:
                if query in summary or query in description:
                    is_match = True
                else:
                    tokens = [t for t in query.split() if len(t) > 3]
                    if tokens and any(t in summary or t in description for t in tokens):
                        is_match = True

            if is_match:
                event_id = event['id']
                m_summary = event.get('summary', 'Untitled Event')
                try:
                    service.events().delete(calendarId='primary', eventId=event_id).execute()
                    deleted_count += 1
                    deleted_summaries.append(m_summary)
                    if not delete_all and not date and query not in ["all", "*", "everything"]:
                        break
                except Exception:
                    pass

        if deleted_count == 0:
            return f"No upcoming event matching '{event_summary or date}' was found on your calendar."

        return f"Successfully deleted {deleted_count} event(s) from Google Calendar: {', '.join(deleted_summaries)}"
    except Exception as e:
        return f"Error deleting event from Google Calendar: {str(e)}"


