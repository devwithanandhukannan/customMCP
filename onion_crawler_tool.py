import os
import requests
from bs4 import BeautifulSoup
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Tor Docker container proxy settings
TOR_HOST = "127.0.0.1"
TOR_PORT = 9050


def crawl_onion(url: str) -> str:
    """
    Crawl a .onion (dark web) URL via the Tor SOCKS5 proxy running in Docker.
    Extracts and returns readable text content from the page.

    Args:
        url: Full .onion URL (e.g. 'http://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion')

    Returns:
        Extracted page text or an error message.
    """
    # Build a requests session that routes ALL traffic through Tor
    session = requests.Session()
    session.proxies = {
        "http":  f"socks5h://{TOR_HOST}:{TOR_PORT}",   # socks5h = resolve DNS via Tor
        "https": f"socks5h://{TOR_HOST}:{TOR_PORT}",
    }
    # Use a realistic browser User-Agent
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; rv:102.0) Gecko/20100101 Firefox/102.0"
        )
    }

    try:
        response = session.get(url, headers=headers, timeout=30)

        if response.status_code != 200:
            return f"Failed to reach onion site. HTTP Status: {response.status_code}"

        # Parse and clean the HTML
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.extract()

        text = soup.get_text(separator=" ", strip=True)
        truncated = text[:4000]  # Keep within token limits

        if not truncated:
            return f"No readable text content found at: {url}"

        return f"Onion Site Content from [{url}]:\n\n{truncated}"

    except requests.exceptions.ConnectionError:
        return (
            "Connection failed. Make sure the Tor Docker container is running:\n"
            "  docker compose up -d"
        )
    except requests.exceptions.Timeout:
        return (
            "Request timed out. .onion sites can be slow — try again or check "
            "that Tor is fully bootstrapped (docker logs tor_proxy)."
        )
    except Exception as e:
        return f"Error crawling onion URL '{url}': {str(e)}"


def analyze_content(content: str, analysis_type: str = "summarize") -> str:
    """
    Analyze any text content using Groq AI (Llama 3.3).
    Useful after crawling a webpage, onion site, or any scraped text.

    Args:
        content:       The raw text to analyze.
        analysis_type: One of:
                         - 'summarize'        → clear, concise summary
                         - 'risk_assessment'  → detect risks, threats, illegal content
                         - 'extract_links'    → list all URLs and .onion links found
                         - 'key_info'         → extract names, dates, facts, entities

    Returns:
        AI-generated analysis as a formatted string.
    """
    analysis_prompts = {
        "summarize": (
            "Summarize the following content clearly and concisely in bullet points. "
            "Focus on the main topics and purpose of the content."
        ),
        "risk_assessment": (
            "Carefully analyze this content for potential risks, threats, suspicious activity, "
            "or dangerous/illegal information. Be objective and factual. "
            "Rate overall risk as LOW / MEDIUM / HIGH and explain your reasoning."
        ),
        "extract_links": (
            "Extract ALL URLs, .onion addresses, email addresses, and web references "
            "mentioned in this content. List each one on a separate line. "
            "If none are found, say so clearly."
        ),
        "key_info": (
            "Extract the most important facts from this content: "
            "names, organizations, dates, locations, numbers, and any key claims. "
            "Present them as a structured list."
        ),
    }

    prompt_prefix = analysis_prompts.get(analysis_type, analysis_prompts["summarize"])

    if not content or not content.strip():
        return "Error: No content provided for analysis."

    # Limit content to avoid exceeding token limits
    content_truncated = content[:6000]

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert content analyst. You are thorough, accurate, "
                        "and objective. Format your responses clearly."
                    ),
                },
                {
                    "role": "user",
                    "content": f"{prompt_prefix}\n\n---\n\n{content_truncated}",
                },
            ],
            temperature=0.3,
            max_tokens=1024,
        )

        result = response.choices[0].message.content
        return f"[AI Analysis — {analysis_type.upper()}]\n\n{result}"

    except Exception as e:
        return f"Error analyzing content: {str(e)}"


def find_onion_urls(query: str, max_results: int = 10) -> str:
    """
    Search for real .onion (dark web) URLs related to a topic.
    Uses Ahmia.fi (leading onion search index) as primary source,
    with a curated seed list of well-known onion directories as fallback.

    Args:
        query:       Topic to search for (e.g. 'privacy', 'news', 'forums', 'search')
        max_results: Max number of onion URLs to return (default: 10)

    Returns:
        Numbered list of discovered .onion URLs with titles and descriptions.
    """
    import re
    from urllib.parse import urlencode, urlparse, parse_qs

    found = {}   # url -> {title, description}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; rv:102.0) Gecko/20100101 Firefox/102.0"
        )
    }

    # Real .onion addresses are base32 (a-z, 2-7): 16 chars (v2) or 56 chars (v3)
    # Pattern strictly matches only actual onion hostnames — NOT clearnet URLs
    onion_host_re = re.compile(r'\b([a-z2-7]{16}|[a-z2-7]{56})\.onion\b')

    def normalize(raw: str) -> str:
        """Ensure URL has http:// prefix."""
        raw = raw.strip()
        if not raw.startswith("http"):
            raw = "http://" + raw
        return raw

    # ── Source 1: Ahmia.fi ──────────────────────────────────────────────────
    # Ahmia indexes thousands of .onion services and is safe to query on clearnet.
    try:
        ahmia_search = f"https://ahmia.fi/search/?q={requests.utils.quote(query)}"
        resp = requests.get(ahmia_search, headers=headers, timeout=15)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")

            for result in soup.select("li.result")[:max_results * 2]:
                title_tag = result.select_one("h4")
                title = title_tag.get_text(strip=True) if title_tag else "Unknown"

                desc_tag = result.select_one("p.description") or result.select_one("p")
                description = desc_tag.get_text(strip=True) if desc_tag else ""

                # Ahmia redirect links look like:
                # /redirect/?site=xxxxx.onion  OR  href="http://xxxxx.onion/..."
                for a in result.find_all("a", href=True):
                    href = a["href"]

                    # Case A: Ahmia redirect URL → extract the `site=` param
                    if "redirect" in href and "site=" in href:
                        try:
                            qs = parse_qs(urlparse(href).query)
                            site = qs.get("site", [None])[0]
                            if site and onion_host_re.search(site):
                                url = normalize(site)
                                found[url] = {"title": title, "description": description[:200]}
                        except Exception:
                            pass

                    # Case B: Direct .onion href
                    elif onion_host_re.search(href):
                        url = normalize(href)
                        found[url] = {"title": title, "description": description[:200]}

                # Case C: onion address in plain text (e.g. <cite> or <p>)
                full_text = result.get_text()
                for m in onion_host_re.finditer(full_text):
                    url = normalize(m.group(0))
                    if url not in found:
                        found[url] = {"title": title, "description": description[:200]}

    except Exception:
        pass  # Fall through to seed list

    # ── Source 2: Curated onion directories (always-available fallback) ─────
    # These are well-known, publicly documented onion directories.
    KNOWN_DIRECTORIES = {
        "search":  [
            ("DuckDuckGo Onion",   "http://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion", "Private search engine"),
            ("Ahmia Onion",        "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion", "Tor hidden service search index"),
        ],
        "news":    [
            ("BBC News Onion",     "http://bbcnewsd73hkzno2ini43t4gblxvycyac5aw4gnv7t2rccijh7745uqd.onion", "BBC News dark web mirror"),
            ("The New York Times", "http://ej3kv4ebuugcmuwxctx5ic7zxh73rnxt42soi3tdneu2c2em55thufqd.onion", "NYT Tor mirror"),
        ],
        "privacy": [
            ("ProtonMail Onion",   "http://protonmailrmez3lotccipshtkleegetolb73fuirgj7r4o4vfu7ozyd.onion", "Encrypted email"),
            ("Tor Project",        "http://2gzyxa5ihm7nsggfxnu52rck2vv4rvmdlkiu3zzui5du4xyclen53wid.onion", "Official Tor Project site"),
        ],
        "social":  [
            ("Facebook Onion",     "http://facebookwkhpilnemxj7asber7cyoia7hl3uqnb54kb47ki5e4suvhad.onion", "Facebook Tor mirror"),
        ],
        "email":   [
            ("ProtonMail Onion",   "http://protonmailrmez3lotccipshtkleegetolb73fuirgj7r4o4vfu7ozyd.onion", "Encrypted email"),
        ],
        "forum":   [
            ("Dread",              "http://dreadytofatroptsdj6io7l3xptbet6onoyno2yv7jicoxknyazubrad.onion", "Reddit-like dark web forum"),
        ],
    }

    # Match query keywords to seed categories
    q_lower = query.lower()
    matched_seeds = []
    for category, seeds in KNOWN_DIRECTORIES.items():
        if category in q_lower or any(word in q_lower for word in category.split()):
            matched_seeds.extend(seeds)

    # If no specific match, include all seeds
    if not matched_seeds:
        for seeds in KNOWN_DIRECTORIES.values():
            matched_seeds.extend(seeds)

    for title, url, desc in matched_seeds:
        if url not in found:
            found[url] = {"title": title, "description": desc}

    # ── Build Output ────────────────────────────────────────────────────────
    if not found:
        return f"No .onion URLs found for query '{query}'. Try: 'search', 'news', 'privacy', 'email', 'forum'."

    lines = [f"Found {min(len(found), max_results)} .onion URL(s) for: '{query}'\n"]
    for idx, (url, meta) in enumerate(list(found.items())[:max_results], 1):
        lines.append(f"{idx}. {meta['title']}")
        lines.append(f"   URL: {url}")
        if meta["description"]:
            lines.append(f"   About: {meta['description']}")
        lines.append("")

    lines.append("─" * 50)
    lines.append("TIP: Use crawl_onion(url) to visit any of these links via Tor.")
    return "\n".join(lines)
