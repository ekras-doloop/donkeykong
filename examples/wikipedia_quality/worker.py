#!/usr/bin/env python3
"""
Wikipedia Quality Worker
Example DonkeyKong worker that collects Wikipedia articles
and uses Kong (local LLM) to assess quality.
"""

import os
import json
import requests
from typing import Dict, Any

# Add parent to path for imports
import sys
sys.path.insert(0, '/app')

from donkeykong.core.worker import DonkeyWorker, WorkerConfig, run_worker
from donkeykong.kong.validator import OllamaValidator


class WikipediaWorker(DonkeyWorker):
    """
    Collects Wikipedia articles and validates quality with Kong.
    
    This demonstrates the DonkeyKong pattern:
    - collect() fetches the raw data
    - Kong validates with local LLM intelligence
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        
        # Setup HTTP session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'DonkeyKong/1.0 (Wikipedia Quality Example)'
        })
        
        # Setup Kong validator with custom prompt
        ollama_url = os.environ.get('OLLAMA_URL', 'http://host.docker.internal:11434')
        
        self.kong = OllamaValidator(
            model=os.environ.get('OLLAMA_MODEL', 'llama3.2'),
            base_url=ollama_url,
            validation_prompt="""You are a Wikipedia article quality assessor.

Evaluate this article data:
Title: {entity}
Data: {data}

Assess:
1. Content completeness (does it cover the topic well?)
2. Structure (does it have proper sections?)
3. Citations (are there references?)
4. Neutrality (is it objectively written?)

Respond with ONLY valid JSON:
{{
    "valid": true if quality >= 70 else false,
    "quality_score": 0-100,
    "issues": ["list of problems found"],
    "should_retry": false,
    "reasoning": "brief assessment"
}}
"""
        )
    
    def collect(self, entity: str) -> Dict[str, Any]:
        """
        Fetch Wikipedia article data via the API.
        
        Args:
            entity: Wikipedia article title (e.g., "Python_programming_language")
            
        Returns:
            Dictionary with article data
        """
        self.log(f"Fetching Wikipedia article: {entity}")
        
        try:
            # Use Wikipedia API
            url = "https://en.wikipedia.org/w/api.php"
            params = {
                'action': 'query',
                'titles': entity.replace('_', ' '),
                'prop': 'extracts|info|categories|links',
                'exintro': False,
                'explaintext': True,
                'inprop': 'url|displaytitle',
                'cllimit': 20,
                'pllimit': 50,
                'format': 'json'
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            pages = data.get('query', {}).get('pages', {})
            
            # Get the first (and usually only) page
            page = list(pages.values())[0]
            
            if 'missing' in page:
                return {
                    'error': f'Article not found: {entity}',
                    'title': entity
                }
            
            # Extract relevant data
            extract = page.get('extract', '')
            categories = [c['title'] for c in page.get('categories', [])]
            links = [l['title'] for l in page.get('links', [])]
            
            # Count approximate citations (links to reference sections)
            citation_indicators = extract.lower().count('[citation') + \
                                  extract.lower().count('references')
            
            # Identify sections by looking for headers in extract
            sections = []
            for line in extract.split('\n'):
                if line.strip() and len(line) < 100 and line == line.strip():
                    # Likely a section header
                    if not any(c in line for c in ['==', '{{', '|']):
                        sections.append(line)
            
            return {
                'title': page.get('title', entity),
                'page_id': page.get('pageid'),
                'url': page.get('fullurl', f'https://en.wikipedia.org/wiki/{entity}'),
                'content_length': len(extract),
                'extract_preview': extract[:500] + '...' if len(extract) > 500 else extract,
                'sections_detected': len(sections),
                'sections': sections[:10],  # First 10 sections
                'categories': categories,
                'internal_links': len(links),
                'citation_indicators': citation_indicators,
                'last_touched': page.get('touched')
            }
            
        except requests.RequestException as e:
            return {
                'error': f'Failed to fetch article: {str(e)}',
                'title': entity
            }
        except Exception as e:
            return {
                'error': f'Unexpected error: {str(e)}',
                'title': entity
            }


def main():
    """Run the Wikipedia worker"""
    # Load articles list
    articles_file = os.environ.get('ARTICLES_FILE', '/app/articles.txt')
    
    if os.path.exists(articles_file):
        with open(articles_file, 'r') as f:
            all_articles = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    else:
        # Default test articles
        all_articles = [
            'Python_programming_language',
            'Machine_learning',
            'Artificial_intelligence',
            'Deep_learning',
            'Natural_language_processing'
        ]
    
    # Create worker and run
    config = WorkerConfig()
    worker = WikipediaWorker(config)
    
    # Get assigned range
    assigned = all_articles[config.start_index:config.end_index]
    
    if assigned:
        worker.run(assigned)
    else:
        worker.log("No articles assigned to this worker")


if __name__ == "__main__":
    main()
