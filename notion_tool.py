import os
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY") or os.getenv("NOTION_TOKEN")


def get_notion_client():
    """Helper: Retrieve authenticated Notion Client instance or None."""
    api_key = os.getenv("NOTION_API_KEY") or os.getenv("NOTION_TOKEN")
    if not api_key:
        return None
    return Client(auth=api_key)


def search_notion(query: str = "") -> str:
    """
    Search for pages and databases in the user's Notion workspace matching a query string.

    Args:
        query: Keyword or search query (e.g. 'Meeting Notes', 'Project Plan', 'Tasks')
    """
    client = get_notion_client()
    if not client:
        return (
            "Notion API Key missing. Please add 'NOTION_API_KEY=secret_xxxxxxxxxxxx' "
            "to your .env file and share your Notion pages with your integration."
        )

    try:
        clean_query = query.strip() if query else ""
        if clean_query.lower() in ["*", "all", "everything", "show all", "list all"]:
            clean_query = ""

        kwargs = {"page_size": 100}
        if clean_query:
            kwargs["query"] = clean_query

        response = client.search(**kwargs)
        results = response.get("results", [])

        if not results:
            return f"No Notion pages or databases found." if not clean_query else f"No Notion pages or databases found matching query '{query}'."

        header_str = "all items in Notion workspace" if not clean_query else f"query '{query}'"
        output = [f"Found {len(results)} Notion item(s) for {header_str}:\n"]
        for idx, item in enumerate(results, 1):
            obj_type = item.get("object", "page")
            item_id = item.get("id")

            # Extract title
            title = "Untitled"
            if obj_type == "page":
                props = item.get("properties", {})
                for prop in props.values():
                    if prop.get("type") == "title":
                        title_objs = prop.get("title", [])
                        if title_objs:
                            title = "".join([t.get("plain_text", "") for t in title_objs])
                        break
            elif obj_type == "database":
                title_objs = item.get("title", [])
                if title_objs:
                    title = "".join([t.get("plain_text", "") for t in title_objs])

            url = item.get("url", "#")
            output.append(f"{idx}. [{title}] ({obj_type.upper()})\n   ID: {item_id}\n   URL: {url}\n")

        return "\n".join(output)
    except Exception as e:
        return f"Error searching Notion workspace: {str(e)}"


def create_notion_page(title: str, content: str = "", parent_page_id: str = "") -> str:
    """
    Create a new page in the Notion workspace with a title and optional body text.

    Args:
        title: Title of the new page
        content: Optional paragraph text content for the page
        parent_page_id: Optional ID of a parent page or database to place this page under
    """
    client = get_notion_client()
    if not client:
        return (
            "Notion API Key missing. Please add 'NOTION_API_KEY=secret_xxxxxxxxxxxx' "
            "to your .env file."
        )

    try:
        children_blocks = []
        if content and content.strip():
            paragraphs = content.strip().split("\n")
            for p in paragraphs:
                if p.strip():
                    children_blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": p.strip()}}]
                        }
                    })

        def _do_create(parent_dict):
            kwargs = {
                "parent": parent_dict,
                "properties": {
                    "title": {"title": [{"type": "text", "text": {"content": title}}]}
                }
            }
            if children_blocks:
                kwargs["children"] = children_blocks
            return client.pages.create(**kwargs)

        if parent_page_id and parent_page_id.strip():
            pid = parent_page_id.strip().replace("-", "")
            try:
                new_page = _do_create({"page_id": pid})
            except Exception:
                new_page = _do_create({"database_id": pid})
            page_id = new_page.get("id")
            page_url = new_page.get("url", "#")
            return f"Successfully created Notion page!\n- Title: '{title}'\n- Page ID: {page_id}\n- URL: {page_url}"

        # Default: Try creating as root workspace page
        try:
            new_page = _do_create({"workspace": True})
            page_id = new_page.get("id")
            page_url = new_page.get("url", "#")
            return f"Successfully created Notion page!\n- Title: '{title}'\n- Page ID: {page_id}\n- URL: {page_url}"
        except Exception as ws_err:
            last_error = ws_err

        # Fallback: Search workspace for valid parent pages or databases
        search_res = client.search(page_size=50)
        results = search_res.get("results", [])

        for candidate in results:
            obj_type = candidate.get("object", "page")
            if obj_type in ["data_source", "user", "person"]:
                continue

            candidate_id = candidate.get("id")
            try:
                parent_dict = {"database_id": candidate_id} if obj_type == "database" else {"page_id": candidate_id}
                new_page = _do_create(parent_dict)
                page_id = new_page.get("id")
                page_url = new_page.get("url", "#")
                return f"Successfully created Notion page!\n- Title: '{title}'\n- Page ID: {page_id}\n- URL: {page_url}"
            except Exception as err:
                last_error = err
                continue

        return f"Error creating Notion page: {str(last_error or 'No valid parent page found')}"
    except Exception as e:
        return f"Error creating Notion page '{title}': {str(e)}"


def get_notion_page_content(page_id: str) -> str:
    """
    Fetch and read the text content and blocks of a Notion page by its page ID.

    Args:
        page_id: The ID of the Notion page
    """
    client = get_notion_client()
    if not client:
        return "Notion API Key missing. Please add 'NOTION_API_KEY=secret_xxxxxxxxxxxx' to your .env file."

    try:
        clean_id = page_id.strip().replace("-", "")
        # Fetch page metadata
        page_meta = client.pages.retrieve(page_id=clean_id)
        title = "Untitled Page"
        props = page_meta.get("properties", {})
        for prop in props.values():
            if prop.get("type") == "title":
                title_objs = prop.get("title", [])
                if title_objs:
                    title = "".join([t.get("plain_text", "") for t in title_objs])
                break

        # Fetch block children
        blocks_res = client.blocks.children.list(block_id=clean_id)
        blocks = blocks_res.get("results", [])

        extracted_lines = []
        for b in blocks:
            b_type = b.get("type")
            b_data = b.get(b_type, {})
            rich_texts = b_data.get("rich_text", [])
            text_str = "".join([rt.get("plain_text", "") for rt in rich_texts])
            if text_str:
                if b_type == "heading_1":
                    extracted_lines.append(f"# {text_str}")
                elif b_type == "heading_2":
                    extracted_lines.append(f"## {text_str}")
                elif b_type == "heading_3":
                    extracted_lines.append(f"### {text_str}")
                elif b_type in ["bulleted_list_item", "numbered_list_item"]:
                    extracted_lines.append(f"- {text_str}")
                else:
                    extracted_lines.append(text_str)

        body = "\n".join(extracted_lines) if extracted_lines else "No text blocks found on this page."
        return (
            f"📖 **Notion Page: {title}** (ID: {clean_id})\n"
            f"----------------------------------------\n"
            f"{body}"
        )
    except Exception as e:
        return f"Error retrieving Notion page content for ID '{page_id}': {str(e)}"


def append_notion_block(page_id: str, content: str) -> str:
    """
    Append new paragraph or bullet point text blocks to an existing Notion page.

    Args:
        page_id: The ID of the Notion page to update
        content: Text content or bullet points to append to the page
    """
    client = get_notion_client()
    if not client:
        return "Notion API Key missing. Please add 'NOTION_API_KEY=secret_xxxxxxxxxxxx' to your .env file."

    if not content or not content.strip():
        return "Error: No text content provided to append."

    try:
        clean_id = page_id.strip().replace("-", "")
        paragraphs = content.strip().split("\n")
        children_blocks = []
        for p in paragraphs:
            if p.strip():
                children_blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": p.strip()}}]
                    }
                })

        client.blocks.children.append(block_id=clean_id, children=children_blocks)
        return f"Successfully appended {len(children_blocks)} text block(s) to Notion page ID '{clean_id}'!"
    except Exception as e:
        return f"Error appending blocks to Notion page ID '{page_id}': {str(e)}"
