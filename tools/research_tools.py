try:
    from ddgs import DDGS
except ImportError:  # older package name
    from duckduckgo_search import DDGS


def search_web(query):
    """Search the public web and return short source summaries."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
        if not results:
            return "No web results found."

        lines = ["--- WEB RESEARCH DATA ---"]
        for item in results:
            title = item.get("title") or "Untitled"
            body = item.get("body") or ""
            href = item.get("href") or ""
            lines.append(f"SOURCE: {title}")
            if href:
                lines.append(f"URL: {href}")
            lines.append(f"SUMMARY: {body}\n")
        return "\n".join(lines)
    except Exception as e:
        return f"Research Tool Failed: {e}"
