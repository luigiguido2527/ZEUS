from duckduckgo_search import DDGS

def search_web(query):
    """Searches the live internet using the DDGS library."""
    try:
        # Using the context manager as recommended by the new 'ddgs' update
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=3)]
            if not results:
                return "No web results found."
            
            output = "--- WEB RESEARCH DATA ---\n"
            for r in results:
                output += f"SOURCE: {r['title']}\nSUMMARY: {r['body']}\n\n"
            return output
    except Exception as e:
        return f"Research Tool Failed: {e}"