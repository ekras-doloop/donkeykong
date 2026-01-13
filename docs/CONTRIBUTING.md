# Contributing to DonkeyKong

Thanks for considering contributing! Here's how to get started.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/ekras-doloop/donkeykong.git
cd donkeykong

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks (optional)
pip install pre-commit
pre-commit install
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=donkeykong --cov-report=term-missing

# Run specific test file
pytest tests/test_adversarial.py -v

# Run specific test
pytest tests/test_adversarial.py::TestAdversarialValidator::test_validate_good_analysis -v
```

### Test Coverage Goals

| Module | Target Coverage |
|--------|-----------------|
| kong/adversarial.py | 90%+ |
| kong/validator.py | 80%+ |
| core/worker.py | 70%+ |
| interfaces/* | 60%+ |

## Running the Benchmark

The Wikipedia benchmark provides reproducible validation metrics:

```bash
cd examples/wikipedia_quality

# Basic benchmark (no Ollama required)
python benchmark.py --articles 20

# With Ollama for enhanced validation
python benchmark.py --articles 50 --with-ollama --output results.json
```

Expected results:
- Collection success: 95%+
- Validation pass rate: 70-85%
- Flagged for review: 15-30%

## Code Style

We use `black` for formatting and `ruff` for linting:

```bash
# Format code
black donkeykong/ tests/

# Lint code
ruff check donkeykong/ tests/

# Fix auto-fixable issues
ruff check --fix donkeykong/ tests/
```

## Pull Request Process

1. **Fork and branch**: Create a feature branch from `main`
2. **Write tests**: Add tests for new functionality
3. **Run tests**: Ensure all tests pass (`pytest`)
4. **Format code**: Run `black` and `ruff`
5. **Update docs**: Update README if adding features
6. **Submit PR**: Describe what you changed and why

### PR Checklist

- [ ] Tests added/updated
- [ ] Tests pass locally (`pytest`)
- [ ] Code formatted (`black`)
- [ ] Linting passes (`ruff check`)
- [ ] Documentation updated if needed
- [ ] Benchmark still passes (if touching validation logic)

## Architecture Overview

```
donkeykong/
├── core/           # Base worker and monitoring
│   ├── worker.py   # DonkeyWorker base class
│   └── monitor.py  # Progress tracking
├── kong/           # Validation logic
│   ├── validator.py      # OllamaValidator, SchemaValidator
│   └── adversarial.py    # AdversarialValidator (key file)
├── interfaces/     # User-facing APIs
│   ├── cli/        # `dk` command
│   ├── python/     # Pipeline API
│   └── mcp/        # Claude integration
└── examples/       # Working examples
    └── wikipedia_quality/  # Benchmark example
```

### Key Design Principles

1. **Separation of concerns**: Collection (can't hallucinate) vs Analysis (needs LLM) vs Validation (cheap LLM)
2. **Graceful degradation**: Works without Ollama, just with reduced capability
3. **Fail fast**: Flag issues early rather than propagating bad data
4. **Reproducibility**: Benchmarks should give consistent results

## Reporting Issues

When reporting bugs, include:
- Python version
- OS
- Docker/Redis/Ollama versions (if relevant)
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs

## Questions?

Open an issue with the "question" label or reach out to the maintainers.

---

*Thank you for helping make DonkeyKong better!* 🦍🛢️
