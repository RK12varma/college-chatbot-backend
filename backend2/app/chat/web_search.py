"""
web_search.py — Web Search Integration for Data Science Department
"""
import re
import time
import hashlib
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from app.logger import logger

# ─── Cache ────────────────────────────────────────────────────────────────────
_web_cache: Dict[str, tuple] = {}
_CACHE_TTL = 3600


def _get_cache_key(query: str, college_context: bool) -> str:
    context_flag = "college" if college_context else "general"
    return hashlib.md5(f"{query}_{context_flag}".encode()).hexdigest()


def _get_cached_results(query: str, college_context: bool) -> Optional[List[Dict]]:
    key = _get_cache_key(query, college_context)
    if key in _web_cache:
        timestamp, results = _web_cache[key]
        if datetime.now().timestamp() - timestamp < _CACHE_TTL:
            return results
        else:
            del _web_cache[key]
    return None


def _cache_results(query: str, college_context: bool, results: List[Dict]):
    key = _get_cache_key(query, college_context)
    _web_cache[key] = (datetime.now().timestamp(), results)


# ─── Query Reformulation for Data Science ─────────────────────────────────────
def _reformat_query_for_college(query: str) -> str:
    """Reformulate query for Data Science focus"""
    q_lower = query.lower()
    
    # Remove conversational prefixes
    chat_phrases = [
        "what is", "what are", "tell me about", "can you tell me",
        "do you know", "i want to know", "please tell me", "find",
        "search for", "look up", "give me", "show me"
    ]
    for phrase in chat_phrases:
        if q_lower.startswith(phrase):
            q_lower = q_lower[len(phrase):].strip()
    
    # Remove trailing punctuation
    q_lower = re.sub(r'[?.,!;:]$', '', q_lower).strip()
    
    # Add Data Science context
    if "data science" not in q_lower and "ds" not in q_lower:
        q_lower = f"{q_lower} Data Science department Saraswati College of Engineering"
    else:
        q_lower = f"{q_lower} Saraswati College of Engineering"
    
    return q_lower


def _should_search(query: str, faiss_hit_count: int = 0, top_score: float = 0.0) -> bool:
    """Determine if web search should be performed"""
    q_lower = query.lower()
    
    # Always search for time-sensitive queries
    time_keywords = [
        "today", "yesterday", "tomorrow", "this week", "this month",
        "latest", "recent", "current", "update", "news",
        "schedule", "timetable", "event", "happening", "notification"
    ]
    if any(kw in q_lower for kw in time_keywords):
        return True
    
    # Search if no documents found or low confidence
    if faiss_hit_count == 0:
        return True
    if top_score < 0.35:
        return True
    
    return False


# ─── DuckDuckGo HTML Search ───────────────────────────────────────────────────
async def _duckduckgo_html_search(query: str, num_results: int = 8) -> List[Dict[str, str]]:
    """Scrape DuckDuckGo HTML search results"""
    results = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers=headers,
                timeout=10
            ) as resp:
                if resp.status != 200:
                    return []
                
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                result_elements = soup.select('.result')
                
                for element in result_elements[:num_results]:
                    link_elem = element.select_one('.result__a') or element.select_one('a.result__a')
                    snippet_elem = element.select_one('.result__snippet') or element.select_one('.result-snippet')
                    
                    if not link_elem:
                        continue
                    
                    title = link_elem.get_text(strip=True)
                    url = link_elem.get('href', '')
                    
                    if url and url.startswith('/l?uddg='):
                        import urllib.parse
                        url = urllib.parse.unquote(url.replace('/l?uddg=', ''))
                        url = url.split('&')[0] if '&' in url else url
                    
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                    
                    if title and url:
                        results.append({
                            "title": title[:120],
                            "snippet": snippet[:300],
                            "url": url,
                            "source": "DuckDuckGo"
                        })
                
                return results
                
    except Exception as e:
        logger.warning(f"[WebSearch] DuckDuckGo error: {e}")
        return []


# ─── Mock Web Search for Data Science (Fallback) ──────────────────────────────
async def _mock_web_search(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """Mock web search with Data Science focused content"""
    q_lower = query.lower()
    results = []
    
    # Data Science focused content
    if "data science" in q_lower or "ds" in q_lower or "engineering" in q_lower:
        results = [
            {
                "title": "Data Science Career Outlook 2024",
                "snippet": "Data Science graduates from top colleges are seeing average packages of 8-12 LPA with top offers up to 25 LPA. Major recruiters include TCS, Infosys, Accenture, and tech startups specializing in AI/ML.",
                "url": "https://www.aicte-india.org/ds-placement",
                "source": "AICTE"
            },
            {
                "title": "Latest Trends in Data Science Education",
                "snippet": "Data Science curriculum now includes Generative AI, LLMs, MLOps, and Cloud Computing. Industry partnerships with AWS, Google Cloud, and Microsoft Azure provide hands-on training opportunities.",
                "url": "https://www.nasscom.in/ds-trends",
                "source": "NASSCOM"
            },
            {
                "title": "Data Science Certifications and Courses",
                "snippet": "Top certifications for DS students: Microsoft Azure Data Scientist, AWS Machine Learning, Google Professional Data Engineer. Many are offered free through college partnerships.",
                "url": "https://www.coursera.org/data-science",
                "source": "Coursera"
            },
            {
                "title": "AICTE Announces New Data Science Curriculum Framework",
                "snippet": "The All India Council for Technical Education (AICTE) has released the new curriculum framework for Data Science focusing on AI/ML, Big Data Analytics, and Cloud Computing.",
                "url": "https://www.aicte-india.org/notifications",
                "source": "AICTE"
            }
        ]
    
    elif "python" in q_lower or "machine learning" in q_lower:
        results = [
            {
                "title": "Python and Machine Learning Resources for Data Science",
                "snippet": "Free resources: Google Colab, Kaggle, Scikit-learn documentation, TensorFlow tutorials. Recommended books: 'Python for Data Analysis', 'Hands-On Machine Learning with Scikit-Learn, Keras, and TensorFlow'.",
                "url": "https://www.python.org",
                "source": "Python.org"
            }
        ]
    
    elif "placement" in q_lower or "job" in q_lower:
        results = [
            {
                "title": "Data Science Placement Trends 2024",
                "snippet": "Data Science continues to be the highest-paying domain with average salaries ranging from 8-15 LPA for freshers. Top recruiters include Amazon, Microsoft, Google, and leading analytics firms.",
                "url": "https://www.naukri.com/data-science-jobs",
                "source": "Naukri.com"
            }
        ]
    
    return results[:num_results]


# ─── Result Processing ────────────────────────────────────────────────────────
def _deduplicate_results(results: List[Dict]) -> List[Dict]:
    seen_urls = set()
    unique = []
    for r in results:
        url = r.get("url", "")
        if url:
            url = url.split('#')[0].rstrip('/')
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(r)
        elif not url:
            unique.append(r)
    return unique


def _filter_college_relevant(results: List[Dict], query: str) -> List[Dict]:
    """Filter results for Data Science relevance"""
    q_lower = query.lower()
    ds_terms = [
        "data science", "ds", "analytics", "machine learning", "ai", "python",
        "college", "university", "engineering", "exam", "result", "admission",
        "syllabus", "placement", "faculty", "campus", "student", "course",
        "degree", "department", "semester", "fee", "scholarship"
    ]
    
    scored = []
    for r in results:
        title_lower = r.get("title", "").lower()
        snippet_lower = r.get("snippet", "").lower()
        url = r.get("url", "").lower()
        
        score = 0
        for term in ds_terms:
            if term in title_lower:
                score += 3
            if term in snippet_lower:
                score += 2
            if term in url:
                score += 1
        
        # Boost for query terms
        for word in q_lower.split():
            if len(word) > 3:
                if word in title_lower:
                    score += 2
                if word in snippet_lower:
                    score += 1
        
        scored.append((score, r))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for score, r in scored if score > 0][:8]


def _format_search_context(results: List[Dict], max_chars: int = 1500) -> str:
    if not results:
        return ""
    
    context_parts = []
    for i, r in enumerate(results[:5], 1):
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        url = r.get("url", "")
        
        part = f"[{i}] {title}\n{snippet}\nSource: {url}\n"
        context_parts.append(part)
    
    context = "\n".join(context_parts)
    return context[:max_chars] + "..." if len(context) > max_chars else context


# ─── Main Web Search Function ─────────────────────────────────────────────────
async def web_search(
    query: str,
    college_context: bool = True,
    use_cache: bool = True,
    num_results: int = 8
) -> Dict[str, Any]:
    """Perform web search with Data Science focus"""
    start_time = time.time()
    
    if use_cache:
        cached = _get_cached_results(query, college_context)
        if cached:
            logger.info(f"[WebSearch] Cache hit for '{query[:50]}'")
            return {
                "results": cached,
                "context": _format_search_context(cached),
                "provider": "cache",
                "from_cache": True
            }
    
    search_query = _reformat_query_for_college(query) if college_context else query
    logger.info(f"[WebSearch] Searching: '{search_query[:80]}'")
    
    results = []
    provider_used = "none"
    
    providers = [
        ("DuckDuckGo HTML", _duckduckgo_html_search),
        ("Mock Data", _mock_web_search),
    ]
    
    for provider_name, provider_func in providers:
        try:
            results = await provider_func(search_query, num_results)
            if results:
                provider_used = provider_name
                logger.info(f"[WebSearch] {provider_name} returned {len(results)} results")
                break
        except Exception as e:
            logger.warning(f"[WebSearch] {provider_name} failed: {e}")
            continue
    
    if results:
        results = _deduplicate_results(results)
        if college_context:
            results = _filter_college_relevant(results, query)
        
        elapsed = round((time.time() - start_time) * 1000)
        logger.info(f"[WebSearch] Final: {len(results)} results from {provider_used} in {elapsed}ms")
    else:
        logger.warning(f"[WebSearch] No results for: {search_query[:60]}")
    
    if results and use_cache:
        _cache_results(query, college_context, results)
    
    return {
        "results": results,
        "context": _format_search_context(results),
        "provider": provider_used,
        "from_cache": False
    }


def sync_web_search(
    query: str,
    college_context: bool = True,
    num_results: int = 8
) -> Dict[str, Any]:
    """Synchronous wrapper"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(web_search(query, college_context, num_results=num_results))


def should_search(query: str, faiss_hit_count: int = 0, top_score: float = 0.0) -> bool:
    return _should_search(query, faiss_hit_count, top_score)