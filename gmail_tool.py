import base64
import os.path
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from groq import Groq
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Groq client for AI email summarization
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Scope required for searching, reading, and drafting emails
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'gmail_token.json'


def get_gmail_service():
    """
    Authenticates with Google Gmail API using OAuth 2.0.
    Generates gmail_token.json on first run.
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

    service = build('gmail', 'v1', credentials=creds)
    return service, None


def search_emails(query: str = "is:unread", max_results: int = 5, limit: int = None, **kwargs) -> str:
    """
    Search messages in Gmail inbox matching a query string (e.g. 'is:unread', 'from:github', 'urgent').

    Args:
        query: Gmail search query string (default: 'is:unread')
        max_results: Max number of messages to fetch (default: 5)
    """
    if limit is not None:
        max_results = limit
    service, err = get_gmail_service()
    if err:
        return f"Gmail Setup Required: {err}"

    try:
        results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
        messages = results.get('messages', [])

        if not messages:
            return f"No emails found matching query '{query}'."

        output = [f"Found {len(messages)} Email(s) for Query '{query}':\n"]

        for idx, msg in enumerate(messages, 1):
            msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
            headers = msg_data.get('payload', {}).get('headers', [])
            
            subject = "No Subject"
            sender = "Unknown Sender"
            date = "Unknown Date"

            for h in headers:
                name = h.get('name', '').lower()
                if name == 'subject':
                    subject = h.get('value', 'No Subject')
                elif name == 'from':
                    sender = h.get('value', 'Unknown Sender')
                elif name == 'date':
                    date = h.get('value', 'Unknown Date')

            snippet = msg_data.get('snippet', '')

            output.append(
                f"{idx}. Subject: {subject}\n"
                f"   From: {sender}\n"
                f"   Date: {date}\n"
                f"   Snippet: {snippet}\n"
                f"   Message ID: {msg['id']}\n"
            )

        return "\n".join(output)

    except Exception as e:
        return f"Error searching Gmail: {str(e)}"


def summarize_unread_inbox(max_results: int = 5) -> str:
    """
    Fetch unread emails and use Groq AI (Llama 3.3) to generate an executive summary.

    Args:
        max_results: Max number of unread emails to analyze (default: 5)
    """
    emails_text = search_emails(query="is:unread", max_results=max_results)

    if "No emails found" in emails_text or "Setup Required" in emails_text or "Error" in emails_text:
        return emails_text

    prompt = (
        f"Here are the latest unread emails from the user's inbox:\n\n"
        f"{emails_text}\n\n"
        f"Instructions:\n"
        f"Provide a concise executive summary of these emails.\n"
        f"1. Highlight key updates and urgent messages requiring action.\n"
        f"2. List any action items or follow-ups needed.\n"
        f"3. Group by priority (High / Medium / Informational)."
    )

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional executive email assistant. Summarize emails clearly, accurately, and concisely."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        return f"📩 **Unread Inbox Executive Summary (AI Generated)**:\n\n" + completion.choices[0].message.content
    except Exception as e:
        return f"Error analyzing unread emails with Groq AI: {str(e)}"


def create_email_draft(to: str, subject: str, body: str) -> str:
    """
    Create a new draft email in Gmail.

    Args:
        to: Recipient email address
        subject: Email subject line
        body: Text content of the email
    """
    service, err = get_gmail_service()
    if err:
        return f"Gmail Setup Required: {err}"

    try:
        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject

        raw_msg = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        draft_body = {'message': {'raw': raw_msg}}

        draft = service.users().drafts().create(userId='me', body=draft_body).execute()
        draft_id = draft.get('id', 'Unknown')
        return f"Successfully created email draft in Gmail!\n- To: {to}\n- Subject: {subject}\n- Draft ID: {draft_id}"

    except Exception as e:
        return f"Error creating email draft: {str(e)}"
