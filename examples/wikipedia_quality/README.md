# 🦍 DonkeyKong Example: Wikipedia Quality Collection

This example demonstrates DonkeyKong by collecting Wikipedia articles and using a local LLM (Kong) to assess content quality.

## What This Does

1. **Donkeys** (Docker workers) fetch Wikipedia articles in parallel
2. **Kong** (local Ollama LLM) evaluates each article for:
   - Content completeness
   - Citation quality
   - Neutral point of view
   - Overall quality score

## Prerequisites

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3.2

# Make sure Docker is running
docker --version
```

## Quick Start

```bash
# 1. Start the collection
docker-compose up

# 2. Monitor progress (in another terminal)
docker-compose logs -f monitor

# 3. Check results
ls data/
cat data/Python_programming_language_data.json
```

## Files

- `articles.txt` - List of Wikipedia articles to collect
- `worker.py` - Custom DonkeyKong worker for Wikipedia
- `docker-compose.yml` - Docker configuration
- `Dockerfile` - Worker container definition

## Customization

Edit `articles.txt` to change which articles to collect.

Edit the validation prompt in `worker.py` to change quality criteria:

```python
self.kong = OllamaValidator(
    model="llama3.2",
    validation_prompt="""
    Evaluate this Wikipedia article:
    - Is it comprehensive?
    - Does it have citations?
    - Is it neutrally written?
    
    Return JSON: {"valid": bool, "quality_score": 0-100, "issues": [...]}
    """
)
```

## Expected Output

Each article produces a JSON file like:

```json
{
  "entity": "Python_programming_language",
  "data": {
    "title": "Python (programming language)",
    "content_length": 45230,
    "sections": ["History", "Design philosophy", "Syntax", ...],
    "citations": 127,
    "last_modified": "2024-01-15"
  },
  "validation": {
    "valid": true,
    "quality_score": 92.5,
    "issues": [],
    "reasoning": "Well-structured article with extensive citations..."
  }
}
```

## Performance

With 3 workers and rate limiting:
- ~20 articles/minute
- ~100 articles in 5 minutes
- $0 API costs (local LLM)

## Reproducible Benchmark

Run the benchmark to verify Kong's validation on your infrastructure:

```bash
# Basic benchmark (20 articles, rule-based validation)
python benchmark.py

# Extended benchmark with Ollama
python benchmark.py --articles 100 --with-ollama

# Save results for comparison
python benchmark.py --articles 50 --output results.json
```

### Expected Benchmark Results

| Metric | Expected Range | Notes |
|--------|---------------|-------|
| Collection success | 95%+ | Wikipedia API is reliable |
| Validation pass rate | 70-85% | Depends on article quality |
| Flagged for review | 15-30% | Kong catches issues |
| Avg confidence score | 0.65-0.80 | Higher with Ollama |

### What the Benchmark Tests

The benchmark intentionally creates imperfect analyses (~33% have flaws) to verify Kong catches them:

1. **High confidence on short articles** - Kong should flag
2. **Missing data source references** - Kong should flag  
3. **Extreme scores without evidence** - Kong should flag

Sample output:
```
BENCHMARK RESULTS
================
  Collection: 20/20 (100.0%)
  Validation:
    Passed: 14 (70.0%)
    Flagged: 6 (30.0%)
    Avg confidence: 0.723
  Issues by type:
    confidence_mismatch: 4
    missing_data: 2
```

This provides reproducible evidence for the claimed validation rates.
