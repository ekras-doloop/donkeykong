# 🦍 DonkeyKong

### Distributed Collection, Local Intelligence

**The moment your data pipeline needs *judgment*, the economics change.**

---

## The Problem We Actually Solved

We asked Claude to collect financial data on 1,000 companies. It started inventing earnings numbers.

Not maliciously - it saw tedious, repetitive work and took shortcuts. **This is a documented anti-pattern:**

> **"LLMs are 'lazy learners' that tend to exploit shortcuts in prompts for downstream tasks."**  
> — [arXiv:2305.17256](https://arxiv.org/abs/2305.17256)

> **"Larger models are MORE likely to utilize shortcuts during inference."**  
> — Same paper. Counterintuitive but documented.

> **"An LLM tends to behave like humans: it often goes for the easiest answer rather than the best one."**  
> — [Towards Data Science](https://towardsdatascience.com/boost-your-llm-outputdesign-smarter-prompts-real-tricks-from-an-ai-engineers-toolbox/)

Even with RAG and best practices, hallucination rates remain **5-20% on complex tasks** (2026 benchmarks). When LLMs face bulk tedious work, they fabricate to "complete" rather than admit "I can't fetch this."

**The solution: separate what LLMs are BAD at (tedious collection) from what they're GOOD at (pattern recognition).**

| Task Type | LLM Behavior | Who Should Do It |
|-----------|--------------|------------------|
| Tedious data gathering | Takes shortcuts, hallucinates | **Donkeys** (mechanical scripts) |
| Pattern recognition | Actually excellent | **Claude** (expensive AI) |
| Validation (yes/no questions) | Good and cheap | **Kong** (local LLM) |

This is **"Kong in the Loop"** architecture.

---

## Why DonkeyKong?

If your validation can be done with regex, use a for-loop with `time.sleep()`.

If your validation requires *reasoning*, you need an LLM.

If you need an LLM at 10,000+ entities, you can't afford cloud APIs.

**That's why DonkeyKong exists.**

## The Core Pattern

> "Expensive intelligence does the work once. Cheap intelligence challenges it many times. Only failures go back to expensive intelligence."

This is how humans review work:
- Senior analyst does the analysis
- Junior analyst checks it, asks questions
- Senior only re-reviews what junior flagged

DonkeyKong implements this with AI:
- **Claude/GPT-4** (expensive) does deep analysis
- **Kong** (local Ollama, free) validates and challenges
- Only low-confidence items get reanalyzed

```
┌─────────────────────────────────────────────────────────────────┐
│              "Kong in the Loop" Architecture                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PHASE 1: MECHANICAL COLLECTION (Donkeys - no LLM)              │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                         │
│  │Worker 1 │  │Worker 2 │  │Worker N │  → Raw Data             │
│  │(scripts)│  │(scripts)│  │(scripts)│    (real, not invented) │
│  └────┬────┘  └────┬────┘  └────┬────┘                         │
│       └────────────┼────────────┘                               │
│                    ▼                                             │
│  ┌─────────────────────────────────────────┐                    │
│  │ 🦍 Kong: DATA VALIDATION (free)         │ ← LLM HERE         │
│  │ • "Is this response complete?"          │                    │
│  │ • "Did we get all 12 quarters?"         │                    │
│  │ • Catches collection failures           │                    │
│  └────────────────┬────────────────────────┘                    │
│                   ▼ (verified REAL data)                         │
│                                                                  │
│  PHASE 2: INTELLIGENT ANALYSIS (Claude - expensive)             │
│  ┌─────────────────────────────────────────┐                    │
│  │ Pattern recognition on VERIFIED data    │                    │
│  │ • Cannot invent inputs (they're real)   │                    │
│  │ • Does what LLMs are good at            │                    │
│  │ → Scores, patterns, conclusions         │                    │
│  └────────────────┬────────────────────────┘                    │
│                   ▼                                              │
│  ┌─────────────────────────────────────────┐                    │
│  │ 🦍 Kong: ADVERSARIAL VALIDATION (free)  │ ← LLM HERE         │
│  │ • "Did you USE all the data I gave you?"│                    │
│  │ • "Your score doesn't match evidence"   │                    │
│  │ • "What would change your conclusion?"  │                    │
│  │ • Catches bullshit analysis             │                    │
│  └────────────────┬────────────────────────┘                    │
│                   ▼                                              │
│  PHASE 3: TARGETED RERUN (only ~15% failures)                   │
│  ┌─────────────────────────────────────────┐                    │
│  │ Only low-confidence items reanalyzed    │                    │
│  │ + Missing data added                    │                    │
│  │ + Adversarial questions addressed       │                    │
│  │                                         │                    │
│  │ Cost: 85% less than rerunning all      │                    │
│  └─────────────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

## Why This Prevents Hallucination

**The key insight: validation is easier than generation.**

| Task | Difficulty | Model Needed |
|------|------------|--------------|
| Generate 12 quarters of earnings data | HARD (will hallucinate) | None - use scripts |
| "Is this JSON complete?" | EASY | Cheap local LLM |
| Analyze patterns in verified data | MEDIUM | Expensive cloud LLM |
| "Did you cite all 6 sources?" | EASY | Cheap local LLM |

Kong can run **unlimited passes** at **$0 cost** because validation is:
- Answering yes/no questions about data that EXISTS
- Checking if conclusions match evidence
- Asking adversarial questions

Claude only does the middle part - the actual intelligence work.

## Two Modes of Operation

### Mode 1: Kong as Data Validator
Donkeys collect → Kong validates quality → Retry failures

```python
from donkeykong import Pipeline, OllamaValidator

pipeline = Pipeline(entities=urls, kong=OllamaValidator())
pipeline.run()  # Kong validates each collected item
```

### Mode 2: Kong as Adversarial Reviewer  
Claude analyzes → Kong challenges → Rerun low-confidence only

```python
from donkeykong.kong import AdversarialValidator

validator = AdversarialValidator()
for entity, analysis, raw_data in results:
    result = validator.validate(entity, analysis, raw_data)
    if result.should_rerun:
        reanalyze(entity, questions=result.adversarial_questions)
```

## The Name

- **Donkey** = Load-bearing Docker workers hauling data (pack animals doing the heavy lifting)
- **Kong** = Local LLM sitting on top, managing and QC'ing the output (the king overseeing the donkeys)

## The Economics

| Approach | Collection | Validation | Cost at 10K entities |
|----------|-----------|------------|---------------------|
| Python script + sleep | Sequential | Regex/schema only | $0 but dumb |
| Python script + cloud LLM | Sequential | Intelligent | $100-500 |
| **DonkeyKong** | **Parallel** | **Intelligent + local** | **~$0** |

## Features

- **🐴 Distributed Workers**: Docker containers with range-based task assignment
- **🦍 Local LLM QC**: Ollama integration for intelligent validation (Llama, Mistral, Phi)
- **📊 Real-time Monitoring**: Redis pub/sub for progress tracking
- **🔄 Fault Tolerance**: Automatic retry with configurable strategies
- **💾 Checkpointing**: Resume from failures without losing progress
- **🔌 Three Interfaces**: CLI, Python API, and MCP Server

## Quick Start

### Option 1: CLI

```bash
pip install donkeykong

# Collect URLs with quality validation
dk collect urls.txt --workers 10 --validator quality_check

# Monitor progress
dk status

# Retry failures with different strategy
dk retry --strategy aggressive
```

### Option 2: Python API

```python
from donkeykong import Pipeline, OllamaValidator

# Define your collector
class MyCollector(Pipeline):
    def collect(self, entity):
        # Your collection logic
        return {"data": fetch_data(entity)}
    
    def validate(self, entity, data):
        # Kong validates with local LLM
        return self.kong.validate(data, 
            prompt="Is this data complete and accurate?")

# Run distributed collection
pipeline = MyCollector(
    entities=my_entity_list,
    workers=10,
    kong=OllamaValidator(model="llama3.2")
)
pipeline.run()
```

### Option 3: MCP Server (Claude Integration)

Add to your Claude Desktop config:

```json
{
  "mcpServers": {
    "donkeykong": {
      "command": "dk",
      "args": ["mcp-server"]
    }
  }
}
```

Then talk to Claude:

> "Start collecting these 1000 URLs and validate each page has pricing information"
>
> "How's the collection going?"
>
> "These 12 failed - retry them with a different user agent"

## Installation

```bash
# Core package
pip install donkeykong

# With Ollama support (recommended)
pip install donkeykong[ollama]

# Full installation with MCP
pip install donkeykong[full]
```

### Prerequisites

- Docker & Docker Compose
- Redis (included in docker-compose)
- Ollama (optional, for Kong LLM validation)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3.2
```

## Example: Wikipedia Quality Collection

A complete working example that collects Wikipedia articles and uses a local LLM to assess content quality:

```bash
cd examples/wikipedia_quality
docker-compose up
```

See [examples/wikipedia_quality/README.md](examples/wikipedia_quality/README.md) for details.

## Architecture Deep Dive

### Why Docker?
- **Isolation**: Each worker runs in its own container
- **Scalability**: `docker-compose up --scale worker=100`
- **Reproducibility**: Same environment everywhere

### Why Redis?
- **Coordination**: Workers claim tasks atomically
- **Real-time**: Pub/sub for instant progress updates
- **Fault tolerance**: Workers can restart without losing progress

### Why Local LLM?
- **Cost**: $0 per validation vs $0.01+ per API call
- **Speed**: No rate limits, no network latency
- **Privacy**: Data never leaves your infrastructure
- **Unlimited retries**: Validate as many times as needed

### Degraded Mode (Without Ollama)

Kong works without Ollama installed, but with reduced capability:

| Feature | With Ollama | Without Ollama |
|---------|-------------|----------------|
| Rule-based validation | ✅ Full | ✅ Full |
| Completeness checking | ✅ Full | ✅ Full |
| Consistency checking | ✅ Full | ✅ Full |
| Logic checking | ✅ Full | ✅ Full |
| Adversarial questions | ✅ LLM-generated + rules | ⚠️ Rules only |
| Deep semantic analysis | ✅ Yes | ❌ No |

**Without Ollama**, Kong still catches:
- Missing data sources
- High confidence with low data quality
- Extreme scores without evidence
- Recommendations without findings

**With Ollama**, Kong additionally:
- Generates deeper adversarial questions
- Performs semantic analysis of findings
- Catches subtle logical inconsistencies

```python
# Check if Ollama enhances validation
from donkeykong.kong import AdversarialValidator, OllamaAdversarialValidator

# Rule-based only (always works)
validator = AdversarialValidator()

# LLM-enhanced (requires Ollama running)
try:
    validator = OllamaAdversarialValidator(model="llama3.2")
except ImportError:
    print("Ollama not installed, using rule-based validation")
    validator = AdversarialValidator()
```

## Configuration

```yaml
# donkeykong.yml
workers: 10
redis_url: redis://localhost:6379

kong:
  provider: ollama
  model: llama3.2
  validation_prompt: |
    Evaluate this data for completeness and accuracy.
    Return JSON: {"valid": bool, "issues": [...], "retry": bool}

collection:
  rate_limit: 2.0  # seconds between requests per worker
  retry_attempts: 3
  checkpoint_interval: 100  # save progress every N entities
```

## MCP Server Tools

When running as an MCP server, DonkeyKong exposes these tools to Claude:

| Tool | Description |
|------|-------------|
| `donkeykong_start` | Start a new collection job |
| `donkeykong_status` | Get current progress and stats |
| `donkeykong_failures` | List failed entities with reasons |
| `donkeykong_retry` | Retry failed entities with new strategy |
| `donkeykong_validate` | Manually validate a sample |
| `donkeykong_stop` | Gracefully stop collection |

## Use Cases

DonkeyKong is ideal for any data pipeline that needs intelligent validation:

- **Web scraping** with content quality checks
- **Document processing** pipelines
- **Training data** curation for ML
- **Knowledge graph** construction
- **Research data** gathering
- **API harvesting** with response validation
- **ETL pipelines** where "is this data good?" requires reasoning

## Contributing

Contributions welcome! See [CONTRIBUTING.md](docs/CONTRIBUTING.md).

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=donkeykong --cov-report=term-missing

# Run the reproducible benchmark
cd examples/wikipedia_quality
python benchmark.py --articles 50
```

### Benchmark Results

The Wikipedia benchmark provides verifiable metrics:

| Metric | Expected | Notes |
|--------|----------|-------|
| Collection success | 95%+ | Wikipedia API is reliable |
| Validation pass rate | 70-85% | Kong catches intentional flaws |
| Flagged for review | 15-30% | Adversarial questioning works |

## License

MIT License - see [LICENSE](LICENSE).

---

**DonkeyKong**: Because sometimes the best solution is to throw more barrels at the problem 🦍🛢️

*Built with Docker, Redis, Ollama, and a healthy respect for distributed systems*
