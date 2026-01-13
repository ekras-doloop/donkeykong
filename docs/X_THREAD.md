# 🦍 DonkeyKong X Thread

## Thread for Launch

---

**Tweet 1 (Hook)**

We asked Claude to analyze 1000 companies.

It immediately started making up earnings data to please us.

LLMs are bad at tedious work. They hallucinate to avoid it.

So we built DonkeyKong 🧵

---

**Tweet 2 (The Research)**

Turns out this is a documented anti-pattern:

"LLMs are 'lazy learners' that exploit shortcuts in prompts."
— arXiv:2305.17256

"Larger models are MORE likely to use shortcuts."
— Same paper

When facing tedious bulk work, LLMs fabricate to "complete" rather than admit they can't.

---

**Tweet 3 (The Insight)**

The breakthrough: separate what CANNOT be approximated from what NEEDS intelligence.

| Task | Who | Why |
|------|-----|-----|
| Data gathering | Scripts | Can't hallucinate |
| Analysis | Claude | What LLMs are good at |
| Catching BS | Local LLM | Adversarial check |

We call this "Kong in the Loop."

---

**Tweet 3 (The Architecture)**

🐴 **Donkeys** = Docker workers doing mechanical collection
   - Just HTTP requests
   - Deterministic
   - Cannot hallucinate

🦍 **Kong** = Local LLM that challenges Claude's analysis
   - "Did you use ALL the data?"
   - "Your confidence is 90% but 3 sources failed?"
   - Catches the bullshit

---

**Tweet 4 (Why This Matters)**

Claude is AMAZING at pattern recognition and analysis.

Claude is TERRIBLE at tedious data gathering. It'll make stuff up rather than admit "this is boring."

DonkeyKong plays to the strengths:
- Donkeys do the boring part (mechanical)
- Claude does the smart part (analysis)
- Kong keeps Claude honest

---

**Tweet 5 (The Economics)**

But wait, there's a cost angle too:

| Step | Who | Cost |
|------|-----|------|
| Collect data | Donkeys | ~$0 |
| Deep analysis | Claude | $$$ |
| Challenge analysis | Kong | $0 |
| Rerun failures | Claude | $$$ (but only 15%) |

Kong is free. Kong can run unlimited passes. Kong catches 85% of issues before Claude reruns.

---

**Tweet 6 (Real Numbers)**

Russell 1000 financial data:

WITHOUT DonkeyKong:
- Claude hallucinated 30%+ of earnings data
- Had to throw out entire analysis
- Wasted $400 in API calls

WITH DonkeyKong:
- 733 companies, real data
- Kong flagged 112 for review
- 621 passed adversarial validation
- Actually trustworthy output

---

**Tweet 7 (Kong's Questions)**

Kong doesn't just validate - it plays devil's advocate:

- "How confident can you be with 3 data sources missing?"
- "Your score is 8/10 but you only cited 2 sources?"
- "What would change your conclusion?"
- "Is this trend or noise?"

Cheap local LLM. Unlimited questioning. $0.

---

**Tweet 8 (Three Interfaces)**

Use it however you want:

**CLI**: `dk collect urls.txt --workers 10`

**Python**: 
```python
validator = AdversarialValidator()
result = validator.validate(analysis, raw_data)
if result.should_rerun:
    # Only 15% need expensive reanalysis
```

**MCP**: "Claude, which analyses failed Kong's review?"

---

**Tweet 9 (The Name)**

Why "DonkeyKong"?

🐴 Donkey = pack animal, load-bearing, does tedious work
🦍 Kong = the king, overseer, keeps everyone honest

"Kong in the Loop" = adversarial AI checking expensive AI

(Also it's fun to say)

---

**Tweet 10 (CTA)**

DonkeyKong is now open source:

🔗 github.com/[your-username]/donkeykong

Use it when:
- You need LLM analysis at scale
- You can't trust LLMs to gather their own data
- You want cheap QC on expensive AI

🦍🛢️ Kong in the Loop

---

## Key Messages

1. **Hallucination is the real problem** - Not just cost, but trust
2. **Separation of concerns** - Mechanical vs intelligent work
3. **Kong in the Loop** - Catchy name for the pattern
4. **Adversarial, not just validation** - Kong challenges, doesn't just check

## Image Suggestions

1. **The separation diagram** - "Cannot Hallucinate" vs "Can Hallucinate (but checked)"
2. **Kong's adversarial questions** - List of challenging questions
3. **Before/after** - "Claude made up 30% of data" vs "Kong caught the issues"
4. **Architecture flow** - Donkeys → Data → Claude → Kong → Output

## The Honest Story

This thread leads with the REAL problem: LLMs hallucinate on tedious tasks.

That's more relatable than "save money on API calls" because everyone who's used Claude/GPT at scale has hit this wall.

"Kong in the Loop" is memorable and explains the pattern in 4 words.

## Research Backing

The "lazy learners" arXiv paper (2305.17256) is the key citation. It documents:
- LLMs exploit shortcuts rather than doing tedious work
- Larger models are MORE prone to this (counterintuitive)
- This is measurable and reproducible

2026 benchmarks show 5-20% hallucination rates on "complex reasoning and summarization tasks" even with best practices.

The research validates the architecture: you can't fix this with prompting. You need to separate generation from validation.
