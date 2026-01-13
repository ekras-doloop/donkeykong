# The DonkeyKong Project: Origin Story

## How It Actually Happened

DonkeyKong wasn't designed top-down. It emerged from hitting walls.

### The Walls We Hit

**Wall 1: Rate Limits (429 errors)**
```
Single Python script → 50 companies → 429 Too Many Requests
```
We needed to analyze 1000 companies. Sequential processing would take days.

**Wall 2: Docker Containers Get Different IPs**
```python
# The breakthrough moment
# 10 Docker containers = 10 different IPs = 10x throughput
```
Redis for coordination, shared volumes for data. Suddenly 733 companies in 3 hours.

**Wall 3: SEC Blocks Datacenter IPs**
```
Docker workers → 403 Forbidden from SEC
```
Solution: Hybrid architecture. Docker for most APIs, local harvester for SEC.

**Wall 4: Claude Invents Data When Bored**
```
"Analyze these 1000 companies"
→ Claude starts hallucinating earnings numbers to please us
```
The separation emerged: mechanical collection (can't hallucinate) vs intelligent analysis (what LLMs are good at).

**Wall 5: Claude Bullshits Analysis Too**
```
"Your confidence is 90% but 3 data sources failed?"
```
Enter Kong: adversarial validation. Cheap local LLM that challenges expensive analysis.

### The Evolution

```
Rate limits (429)
    ↓
Docker containers (IP diversity)
    ↓
SEC blocks datacenter IPs (hybrid architecture)
    ↓
"Claude analyzes JSON in 30 seconds!" (separation works)
    ↓
"Claude invents data when bored" (hallucination problem)
    ↓
Kong as adversarial validator (current architecture)
```

### Why This Matters

The pattern didn't come from theory. It came from:
- Getting rate limited
- Getting blocked by SEC
- Getting hallucinated data
- Getting bullshit analysis

Each wall forced a better architecture.

### The Name

- **Donkey**: Pack animal doing grunt work (Docker workers)
- **Kong**: The king overseeing everything (local LLM validator)
- **Together**: Parallel processing "barrels" of data 🛢️

### Technical Reality

| Metric | Before | After |
|--------|--------|-------|
| Companies processed | 50 (then 429) | 733 |
| Time | 3 days (theoretical) | 3 hours |
| Success rate | ~5% (rate limits) | 85%+ |
| Hallucinated data | 30%+ | Caught by Kong |

### The Lesson

> "In the beginning, there was a rate limit. And the developer said, 'Let there be Docker.' And there were containers. And it was good."
> 
> — The Book of DonkeyKong, Chapter 1, Verse 429

---

*DonkeyKong exists because we kept hitting walls. Each wall made the architecture better.*
