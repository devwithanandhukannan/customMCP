import os
import sqlite3
import mimetypes

DB_PATH = "agent_storage.db"


def init_db():
    """Initialize the SQLite database and create the documents table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            file_type TEXT NOT NULL,
            content_text TEXT,
            file_path TEXT,
            file_size INTEGER,
            blob_data BLOB,
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


# Ensure DB is initialized on module load
init_db()


def store_text_data(title: str, content: str, tags: str = "") -> str:
    """
    Store text notes, code snippets, or structured information in the SQL database.

    Args:
        title: Short title or header for the text entry
        content: The text body or content to store
        tags: Optional comma-separated tags (e.g. 'notes, meeting, python')
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        file_size = len(content.encode('utf-8'))
        cursor.execute(
            """
            INSERT INTO documents (title, file_type, content_text, file_size, tags)
            VALUES (?, ?, ?, ?, ?)
            """,
            (title, "text", content, file_size, tags)
        )
        doc_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return f"Successfully stored text data in SQL database!\n- Document ID: {doc_id}\n- Title: '{title}'\n- Tags: {tags or 'None'}\n- Size: {file_size} bytes"
    except Exception as e:
        return f"Error storing text data in SQL database: {str(e)}"


def store_file(file_path: str, title: str = "", tags: str = "") -> str:
    """
    Read any local file (Image, PDF, Document, Code, Data) and store it in the SQL database
    along with raw binary BLOBs and extracted text for AI search.

    Args:
        file_path: Absolute or relative path to the local file
        title: Optional title (defaults to filename if omitted)
        tags: Optional comma-separated tags (e.g. 'pdf, research, invoice')
    """
    if not os.path.exists(file_path):
        return f"File not found: '{file_path}'"

    file_name = os.path.basename(file_path)
    doc_title = title if title.strip() else file_name
    file_size = os.path.getsize(file_path)
    ext = os.path.splitext(file_name)[1].lower()

    # Determine file_type and extract text if applicable
    file_type = "data"
    extracted_text = ""

    if ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg', '.bmp', '.tiff']:
        file_type = "image"
        extracted_text = f"Image file: {file_name} ({file_size} bytes)"
    elif ext == '.pdf':
        file_type = "pdf"
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            pages_text = []
            for i, page in enumerate(reader.pages):
                txt = page.extract_text()
                if txt:
                    pages_text.append(txt)
            extracted_text = "\n".join(pages_text) if pages_text else "PDF text extraction empty."
        except Exception as pdf_err:
            extracted_text = f"PDF text extraction unavailable: {str(pdf_err)}"
    elif ext in ['.txt', '.md', '.json', '.py', '.js', '.html', '.css', '.csv', '.xml', '.yaml', '.yml', '.sh']:
        file_type = "text"
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                extracted_text = f.read()
        except Exception as txt_err:
            extracted_text = f"Error reading text file: {str(txt_err)}"

    # Read binary BLOB
    try:
        with open(file_path, 'rb') as f:
            blob_bytes = f.read()

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO documents (title, file_type, content_text, file_path, file_size, blob_data, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (doc_title, file_type, extracted_text, os.path.abspath(file_path), file_size, blob_bytes, tags)
        )
        doc_id = cursor.lastrowid
        conn.commit()
        conn.close()

        text_preview = f"\n- Extracted Text Snippet: {extracted_text[:150]}..." if extracted_text else ""
        return (
            f"Successfully stored file in SQL database!\n"
            f"- Document ID: {doc_id}\n"
            f"- Title: '{doc_title}'\n"
            f"- File Type: {file_type.upper()}\n"
            f"- Size: {file_size} bytes\n"
            f"- Tags: {tags or 'None'}"
            f"{text_preview}"
        )
    except Exception as e:
        return f"Error storing file in SQL database: {str(e)}"


def search_database(query: str, file_type: str = "all") -> str:
    """
    Search stored documents, images, PDFs, and notes in the SQL database by title, content, or tags.

    Args:
        query: Search term or keyword
        file_type: Filter by file type ('all', 'text', 'pdf', 'image', 'data')
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        sql_query = """
            SELECT id, title, file_type, file_path, file_size, tags, created_at, content_text
            FROM documents
            WHERE (title LIKE ? OR content_text LIKE ? OR tags LIKE ?)
        """
        params = [f"%{query}%", f"%{query}%", f"%{query}%"]

        if file_type.lower() != "all":
            sql_query += " AND file_type = ?"
            params.append(file_type.lower())

        sql_query += " ORDER BY created_at DESC LIMIT 10"

        cursor.execute(sql_query, params)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return f"No documents found matching query '{query}' (file_type: {file_type})."

        output = [f"Found {len(rows)} Document(s) in SQL Database for Query '{query}':\n"]
        for row in rows:
            doc_id, title, f_type, f_path, f_size, tags, created_at, content = row
            snippet = content[:200].replace("\n", " ") if content else "No text content"
            path_str = f" ({f_path})" if f_path else ""
            output.append(
                f"- [ID: {doc_id}] {title} | Type: {f_type.upper()} | Size: {f_size or 0} bytes | Date: {created_at}\n"
                f"  Tags: {tags or 'None'}{path_str}\n"
                f"  Snippet: {snippet}\n"
            )

        return "\n".join(output)
    except Exception as e:
        return f"Error searching SQL database: {str(e)}"


def list_stored_documents(limit: int = 10) -> str:
    """
    List stored documents, images, PDFs, and text notes in the SQL database.

    Args:
        limit: Max number of items to list (default: 10)
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, file_type, file_path, file_size, tags, created_at
            FROM documents
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return "The SQL database is currently empty. Use 'store_text_data' or 'store_file' to add items."

        output = [f"Stored Items in SQL Database (Showing top {len(rows)}):\n"]
        for row in rows:
            doc_id, title, f_type, f_path, f_size, tags, created_at = row
            path_str = f" ({f_path})" if f_path else ""
            output.append(
                f"- [ID: {doc_id}] {title} | Type: {f_type.upper()} | Size: {f_size or 0} bytes | Tags: {tags or 'None'} | Date: {created_at}{path_str}"
            )

        return "\n".join(output)
    except Exception as e:
        return f"Error listing database documents: {str(e)}"


def get_document(doc_id: int) -> str:
    """
    Fetch full text content and metadata for a document by its SQL ID.

    Args:
        doc_id: The integer ID of the document to retrieve
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, file_type, file_path, file_size, tags, created_at, content_text
            FROM documents
            WHERE id = ?
            """,
            (doc_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return f"No document found with ID {doc_id} in the database."

        _, title, f_type, f_path, f_size, tags, created_at, content = row
        return (
            f"📄 **Document Details (ID: {doc_id})**:\n"
            f"- **Title**: {title}\n"
            f"- **Type**: {f_type.upper()}\n"
            f"- **File Path**: {f_path or 'N/A'}\n"
            f"- **Size**: {f_size or 0} bytes\n"
            f"- **Tags**: {tags or 'None'}\n"
            f"- **Created At**: {created_at}\n\n"
            f"**Content / Extracted Text**:\n"
            f"----------------------------------------\n"
            f"{content or 'No text content available.'}"
        )
    except Exception as e:
        return f"Error retrieving document ID {doc_id}: {str(e)}"
