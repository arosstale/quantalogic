from duckduckgo_search import DDGS
import json


def search_news(query: str, max_results: int = 3):
    """Search DuckDuckGo for news articles and return as JSON"""
    results = DDGS().news(query, max_results=max_results)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    search_news("technology")
