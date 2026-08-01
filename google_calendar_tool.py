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

def list_upcoming_calendar_events(max_results: int = 5) -> str:
    """
    List upcoming events from the user's primary Google Calendar.
    
    Args:
        max_results: Max number of events to fetch (default: 5)
    """
    service, err = get_calendar_service()
    if err:
        return f"Google Calendar Setup Required: {err}"
        
    try:
        now = datetime.now(timezone.utc).isoformat()
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        if not events:
            return "No upcoming calendar events found."

        output = ["Upcoming Google Calendar Events:"]
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

def delete_calendar_event(event_summary: str) -> str:
    """
    Find and delete an event from the user's primary Google Calendar by title/summary keyword.
    
    Args:
        event_summary: Summary or title keyword of the event to delete (e.g. 'New Event')
    """
    service, err = get_calendar_service()
    if err:
        return f"Google Calendar Setup Required: {err}"
        
    try:
        now = datetime.now(timezone.utc).isoformat()
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            maxResults=20,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        target_event = None
        for event in events:
            summary = event.get('summary', '')
            if event_summary.lower() in summary.lower():
                target_event = event
                break

        if not target_event:
            return f"No upcoming event matching '{event_summary}' was found on your calendar."

        event_id = target_event['id']
        matched_summary = target_event.get('summary', 'Untitled Event')
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        return f"Successfully deleted event '{matched_summary}' (ID: {event_id}) from your Google Calendar."
    except Exception as e:
        return f"Error deleting event from Google Calendar: {str(e)}"


