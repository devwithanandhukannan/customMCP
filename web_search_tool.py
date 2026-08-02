import os
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def search_web(query: str, max_results: int = 5) -> str:
    """
    Search the live web using DuckDuckGo to find latest news, articles, code docs, and information.
    
    Args:
        query: Search query (e.g. 'latest AI news 2026' or 'fastmcp documentation')
        max_results: Maximum search results to return (default: 5)
    """
    try:
        results = list(DDGS().text(query, max_results=max_results))
        if not results:
            return f"No search results found for query '{query}'."

        output = [f"Web Search Results for '{query}':"]
        for idx, item in enumerate(results, 1):
            title = item.get('title', 'No Title')
            href = item.get('href', '#')
            snippet = item.get('body', '')
            output.append(f"\n{idx}. [{title}]({href})\n   Snippet: {snippet}")

        return "\n".join(output)
    except Exception as e:
        return f"Error performing web search: {str(e)}"

def scrape_url(url: str) -> str:
    """
    Scrape and extract readable text content from a given webpage URL.
    
    Args:
        url: The webpage URL to scrape (e.g. 'https://en.wikipedia.org/wiki/Artificial_intelligence')
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return f"Failed to fetch webpage. HTTP Status Code: {response.status_code}"

        # Parse HTML content with BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
            script.extract()

        # Get readable text content
        text = soup.get_text(separator=" ", strip=True)
        
        # Truncate text content (~3000 chars to conserve tokens)
        truncated_text = text[:3000]

        if not truncated_text:
            return f"No readable text content found at URL: {url}"

        return f"Extracted Text Content from [{url}]({url}):\n\n{truncated_text}"


    except Exception as e:
        return f"Error scraping URL '{url}': {str(e)}"


def analyze_content(content: str, analysis_type: str = "summarize") -> str:
    """
    Analyze any text content using Groq AI (Llama 3.3).
    Useful after scraping a webpage or any text.

    Args:
        content:       The raw text to analyze.
        analysis_type: One of:
                         - 'summarize'        → clear, concise summary
                         - 'risk_assessment'  → detect risks, threats, suspicious content
                         - 'extract_links'    → list all URLs, email addresses, and web references found
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
            "or dangerous information. Be objective and factual. "
            "Rate overall risk as LOW / MEDIUM / HIGH and explain your reasoning."
        ),
        "extract_links": (
            "Extract ALL URLs, email addresses, and web references "
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



