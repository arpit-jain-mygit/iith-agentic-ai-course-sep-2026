# Agentic AI Interview Guide — 🟡 Intermediate

**Guide parts:** [🟢 Beginner](INTERVIEW-GUIDE-1-BEGINNER.md) · **🟡 Intermediate** (this file) · [🔴 Expert](INTERVIEW-GUIDE-3-EXPERT.md) · Companion: [INTERVIEW-PREP.md](INTERVIEW-PREP.md) (same course material by day, with more code)

This part assumes you know the definitions from the [🟢 Beginner](INTERVIEW-GUIDE-1-BEGINNER.md) part.
Interviewers at this level want to hear how things work under the hood, the trade-offs, and what breaks
in practice. A small "I've seen this go wrong when..." story is worth more than a perfect definition.

---

## Topics in this part

| # | Topic | Source |
|---|---|---|
| [I1](#i1-why-long-prompts-are-slow-and-expensive) | Why long prompts are slow and expensive | Day 1 · S1 |
| [I2](#i2-context-rot--why-a-bigger-window-isnt-the-fix) | Context rot — why a bigger window isn't the fix | Day 1 · S1 |
| [I3](#i3-prompt-engineering-vs-context-engineering) | Prompt engineering vs context engineering | Day 1 · S1 + books |
| [I4](#i4-valid-json-isnt-a-correct-answer) | Valid JSON isn't a correct answer | Day 1 · S1 |
| [I5](#i5-the-self-repair-loop) | The self-repair loop | Day 1 · S1 + books |
| [I6](#i6-provider-agnostic-clients-litellm) | Provider-agnostic clients (LiteLLM) | Day 1 · S1 |
| [I7](#i7-picking-a-model-benchmark-traps) | Picking a model; benchmark traps | Day 1 · S1 |
| [I8](#i8-designing-a-good-tool) | Designing a good tool | Day 1 · S2 |
| [I9](#i9-idempotency-and-parallel-tool-calls) | Idempotency and parallel tool calls | Day 1 · S2 |
| [I10](#i10-retries-backoff-and-circuit-breakers) | Retries, backoff and circuit breakers | Day 1 · S2 + books |
| [I11](#i11-the-harness) | The harness | Day 1 · S2 |
| [I12](#i12-react-vs-plannerexecutor-vs-reflection) | ReAct vs planner–executor vs reflection | Day 1 · S2 + books |
| [I13](#i13-long-conversations-truncation-summaries-long-term-memory) | Long conversations: truncation, summaries, long-term memory | Day 2 · S1 |
| [I14](#i14-agent-managed-memory-and-consolidation) | Agent-managed memory and consolidation | Day 2 · S1 |
| [I15](#i15-chunking-strategies-compared) | Chunking strategies compared | Day 2 · S2 + books |
| [I16](#i16-ingesting-messy-real-world-documents) | Ingesting messy real-world documents | Day 2 · S2 |
| [I17](#i17-hybrid-search) | Hybrid search | Day 2 · S2 |
| [I18](#i18-reranking-rrf-and-rag-fusion) | Reranking, RRF and RAG Fusion | Day 2 · S2 |
| [I19](#i19-measuring-retrieval-and-rag-quality) | Measuring retrieval and RAG quality | Day 2 · S2 |
| [I20](#i20-langgraph-state-checkpoints-interrupts) | LangGraph: state, checkpoints, interrupts | Day 3 · S1 |
| [I21](#i21-supervisor-routing-and-loop-caps) | Supervisor routing and loop caps | Day 3 · S2 |
| [I22](#i22-how-mcp-works-when-to-use-a2a) | How MCP works; when to use A2A | Day 3 · S2 |
| [I23](#i23-ag-ui-and-ap2) | AG-UI and AP2 | Day 3 · S2 + books |
| [I24](#i24-the-four-caches-in-llm-serving) | The four caches in LLM serving | Extra · 4 caches + books |
| [I25](#i25-inside-a-vector-database) | Inside a vector database | Extra · Vector databases |
| [I26](#i26-choosing-an-embedding-model) | Choosing an embedding model | Extra · AI/ML engineer Qs |
| [I27](#i27-choosing-a-vector-database) | Choosing a vector database | Extra · Vector databases · LLM fundamentals Qs |
| [I28](#i28-a-tour-of-rag-architectures) | A tour of RAG architectures | Extra · 12 RAG architectures + books |
| [I29](#i29-ai-gateway) | AI gateway | Extra · 9 AI concepts + books |
| [I30](#i30-making-llm-output-deterministic-and-writing-robust-system-prompts) | Making LLM output deterministic, and writing robust system prompts | Extra · LLM fundamentals Qs + books |
| [I31](#i31-lora-qlora-and-full-fine-tuning) | LoRA, QLoRA and full fine-tuning | Extra · LLM fundamentals Qs + books |
| [I32](#i32-quantization-and-hosted-apis-vs-open-source-models) | Quantization, and hosted APIs vs open-source models | Extra · LLM fundamentals Qs · cost reduction + books |
| [I33](#i33-langgraph-vs-google-adk) | LangGraph vs Google ADK | Extra · AI/ML engineer Qs |
| [I34](#i34-what-changed-between-mcp-versions) | What changed between MCP versions | Extra · AI/ML engineer Qs |
| [I35](#i35-logging-prompts-and-outputs-versioning-prompts-and-context) | Logging prompts and outputs; versioning prompts and context | Extra · LLM fundamentals Qs |
| [I36](#i36-generation-parameters-and-decoding-strategies) | Generation parameters and decoding strategies | Book · AI Engineering (DailyDoseofDS) |
| [I37](#i37-advanced-prompting-for-reasoning-and-structure) | Advanced prompting for reasoning and structure | Book · AI Engineering (DailyDoseofDS) |
| [I38](#i38-mixture-of-experts-moe) | Mixture of Experts (MoE) | Book · AI Engineering (DailyDoseofDS) |
| [I39](#i39-knowledge-distillation--training-a-small-model-from-a-big-one) | Knowledge distillation — training a small model from a big one | Book · AI Engineering (DailyDoseofDS) |
| [I40](#i40-measuring-llm-speed-ttft-tpot-and-throughput) | Measuring LLM speed: TTFT, TPOT and throughput | Book · System Design for the LLM Era |
| [I41](#i41-designing-for-low-latency) | Designing for low latency | Book · System Design for the LLM Era |
| [I42](#i42-multi-agent-orchestration-patterns) | Multi-agent orchestration patterns | Book · AI Engineering (DailyDoseofDS) |
| [I43](#i43-agent-deployment-patterns) | Agent deployment patterns | Book · AI Engineering (DailyDoseofDS) |
| [I44](#i44-mcp-in-depth-primitives-discovery-and-tool-overload) | MCP in depth: primitives, discovery and tool overload | Book · AI Engineering (DailyDoseofDS) |

---

# 🟡 Intermediate

At this level, interviewers assume you know the definitions. They want to hear how things work under
the hood, what the trade-offs are, and what breaks in practice. The best answers usually include a
small "I've seen this go wrong when..." story.

## I1. Why long prompts are slow and expensive

Two separate effects add up here.

**Cost.** Providers charge per input token and per output token. Because the model is stateless ([B2](INTERVIEW-GUIDE-1-BEGINNER.md#b2-statelessness--how-chat-remembers)),
every call resends the whole conversation, tool results and retrieved documents. A 20-turn agent run
where each turn adds a few thousand tokens ends up paying for the early tokens twenty times over.

**Latency.** Before the model writes its first word, it has to process the whole prompt (called
*prefill*). Attention, the mechanism that lets each token look at the others, compares tokens with each
other, so this work grows faster than the prompt length. Double the prompt and the wait before the first
token grows by more than double. That's why "time to first token" gets worse with long prompts, even
when the answer is short.

The fixes are mostly about sending less:

- Only include what this call needs (filter, summarise, retrieve).
- Trim tool outputs to the fields that matter instead of dumping raw JSON.
- Use **prompt caching**: if the start of your prompt (system instructions, tool definitions) is
  identical across calls, providers can reuse the already-processed version, which is cheaper and
  faster. The catch is that it only works if the prefix is *exactly* the same, so put stable content
  first and changing content last.

PlantGuard's fact-gathering step compacts about 29k characters of raw records down to about 9k before
calling the model, cutting cost and latency, and usually improving quality too (see [I2](#i2-context-rot--why-a-bigger-window-isnt-the-fix)).

## I2. Context rot — why a bigger window isn't the fix

A common interview question: *"Our model has a million-token window. Why not just put all our
documents in the prompt and skip RAG?"*

The answer is **context rot**: models get measurably worse at using information as the context grows,
long before the window is full. A few reasons:

- **Lost in the middle.** Models pay most attention to the beginning and end of the prompt; facts buried
  in the middle are used less reliably.
- **Distraction.** Irrelevant text isn't neutral. Similar-looking but wrong passages pull the model
  toward wrong answers.
- **Cost and latency.** Every call pays for everything you included ([I1](#i1-why-long-prompts-are-slow-and-expensive)).

So a bigger window moves the wall but doesn't remove it. You still get better answers by giving the
model a small amount of the *right* material.

There are cases where long context is the right tool: analysing one long contract end to end, for
example, where chopping it up would lose cross-references. The point isn't "never use long context",
it's "don't use it as a substitute for selecting what matters".

If asked how you'd show this, say you'd run the same golden-set questions with increasing amounts of
irrelevant context and plot accuracy. It usually drops.

## I3. Prompt engineering vs context engineering

**Prompt engineering** is about the wording: how you phrase instructions, examples and format
requests. It matters, but it's a small lever.

**Context engineering** is about *what information the model sees on each call*: which facts, which
documents, which memories, which tool results, how much history, in what order, at what length. In
production, most bad answers come from the model having the wrong or too much information, not from
badly worded instructions.

A good way to explain it: prompt engineering is writing a clear question; context engineering is
deciding which papers to put on the desk before asking it.

Context engineering is real engineering work, built and tested like any pipeline. Typical techniques:

- allow-listing which fields go to the model;
- filtering by time (no data from after the event, to avoid "look-ahead");
- summarising history;
- retrieving only relevant documents;
- ordering content so stable parts can be cached.

PlantGuard's whole pre-LLM pipeline (gathering facts, filtering them to the event time, compacting,
retrieving manual sections) is context engineering. The prompt wording itself is short.

A popular analogy: **if the LLM is the CPU, the context window is its RAM.** Context engineering is
deciding what gets loaded into that RAM before each instruction runs.

For agents, it helps to list the kinds of context you're assembling:

1. **Instructions** — who the agent is, why it's acting, how it should behave.
2. **Examples** — what good and bad look like.
3. **Knowledge** — domain facts, documents, data models.
4. **Memory** — short-term (this task) and long-term (past sessions, preferences).
5. **Tools** — what it can call, with clear descriptions.
6. **Tool results** — what came back, fed in so the agent can adjust.

Guardrails sit around all six. A strong line to remember: *a weaker model with the right context often
beats a stronger model with the wrong context.* Retrieval is usually most of the battle, and bad
retrieval can't be rescued by a better model.

## I4. Valid JSON isn't a correct answer

Structured output ([B5](INTERVIEW-GUIDE-1-BEGINNER.md#b5-structured-output)) guarantees the response *parses* and has the right fields and types. It says
nothing about whether the *values* are right. Things that pass a schema but are still wrong:

- a temperature of 900 °C for a machine that can't physically reach it;
- a citation to a document that wasn't in the retrieved set (made up);
- `priority: "P4"` for something that's clearly an emergency;
- an `end_time` before the `start_time`.

So after parsing, you validate in code: range checks, physical limits, cross-field consistency, and
checks against the input ("is every cited document one we actually gave it?").

Pydantic is handy because the schema *and* custom validators live in one place, and when validation
fails you get a clear error message you can feed back to the model ([I5](#i5-the-self-repair-loop)).

In PlantGuard, a post-LLM guard step rejects citations that weren't retrieved and applies physics
sanity checks before anything is routed.

## I5. The self-repair loop

When the model's output fails validation, the simplest robust approach is: **send the error back and
ask it to fix it.**

You resend the original request plus the model's bad answer plus the exact validation error ("field
`priority` must be one of P1–P4, got 'High'"), and ask for a corrected answer. Models are usually good
at fixing a specific, clearly described problem.

Three details separate a good answer from a basic one:

- **Cap the attempts**, usually one or two. If the model can't comply after that, more retries just
  burn money.
- **Fail safely** when repair fails: raise an error or send the case to a human. Never quietly fill in
  defaults and carry on, because that hides real failures.
- **Log every repair.** The repair rate is a great early-warning signal: if it suddenly jumps, something
  changed (the model version, the prompt, the input data).

It also helps to tell **retry** and **repair** apart. Retry means sending the *same* request again,
which helps with temporary problems like a timeout or a 503. Repair means sending a *corrected* request
with the error, which helps when the content was wrong.

PlantGuard's `call_structured` does exactly one repair attempt with the Pydantic error, then raises.

One subtle interaction: at **temperature 0**, a request that produced malformed output will often fail
**the same way** when simply retried, because the model makes the same choice again. That's another
reason to *repair* (add the error message) rather than blindly retry. Alternatively, retry once at a
slightly higher temperature.

## I6. Provider-agnostic clients (LiteLLM)

Every provider (OpenAI, Anthropic, Google, ...) has its own SDK and slightly different request formats.
A library like **LiteLLM** gives you one interface, `completion(model="provider/model-name", ...)`, for
all of them.

Why that's useful:

- **Switching models is a config change**, not a code change, so you can compare models fairly.
- **Fallbacks:** if one provider is down or rate-limiting, you can retry on another.
- **Less lock-in:** your business logic doesn't depend on one vendor's SDK.

The honest trade-off: the abstraction can lag behind new provider-specific features, and things don't
behave identically behind it. Tool-calling quirks, structured-output support, caching and token counting
all differ. So after switching models you **re-run your evals**, even though the code didn't change.

This happened in PlantGuard: one Gemini model returned 404, another kept returning 503, and switching to
a lite model was just one line in `.env`.

## I7. Picking a model; benchmark traps

Public leaderboards are a reasonable way to build a shortlist, but they're a poor way to make the final
choice:

- **Contamination:** benchmark questions may have leaked into training data, inflating scores.
- **Different tasks:** a model great at maths puzzles may be average at reading maintenance logs.
- **Missing costs:** leaderboards rarely weigh price and latency, which matter a lot in production.

The approach that works: pick two or three candidates, run them on **your own golden set**, and
measure quality, cost per task, latency, and how often outputs fail validation. Then choose the
**cheapest model that meets your quality bar**, not the "best" model.

You can also mix models: a cheap, fast model for easy steps (parsing an operator's note) and a
stronger one for hard steps (an ambiguous triage decision). That's sometimes called *routing* or a
*cascade*, covered more in [E3](INTERVIEW-GUIDE-3-EXPERT.md#e3-choosing-a-model-under-real-constraints).

## I8. Designing a good tool

The model chooses tools by reading their names and descriptions, so a tool definition is really a
small piece of documentation written *for the model*.

What makes a tool easy for a model to use correctly:

- **A clear description** saying what it does, when to use it, and when *not* to. This is the single
  most important field.
- **Few, typed parameters**, with enums for fixed options (`severity: "low" | "medium" | "high"`).
- **Clear names**: `check_spare_parts` beats `inv_q2`.
- **No overlap**: two tools that do similar things confuse selection.
- **Compact, structured results**: return the fields the model needs, not a 5,000-line raw response.
- **Helpful errors**: "asset_tag not found; valid examples look like VPW-CHILLER-01" is something the
  model can act on; a stack trace isn't.

There's also a scaling point: the more tools you give an agent, the worse it gets at picking the right
one. If you have dozens, group them or load only the tools relevant to the current task.

## I9. Idempotency and parallel tool calls

An operation is **idempotent** if doing it twice has the same effect as doing it once. Reading stock
levels is naturally idempotent. "Create a work order" is not: call it twice and you get two work
orders.

Why it matters for agents: agents retry. The network times out and the harness retries; the model
sometimes repeats a call it already made; a crashed workflow resumes and re-runs a step. If write tools
aren't idempotent, you get duplicates: two purchase orders, two emails to a supplier.

The standard fix is an **idempotency key**: a stable ID attached to the write (for example, derived
from the event ID). The tool checks "have I already done this key?" and, if so, returns the existing
result instead of acting again. The key should come from the harness, not be invented by the model.

Models can also request several tool calls in one turn. Running independent *reads* in parallel is a
nice speed-up. *Writes* should normally run one at a time, or be designed so their order doesn't matter.

## I10. Retries, backoff and circuit breakers

External calls fail: providers return 429 (rate limited) or 503 (overloaded), networks time out. Three
patterns handle this, in order of sophistication.

**Retry, but only the right errors.** Temporary failures (429, 5xx, timeouts) are worth retrying.
Permanent ones (400 bad request, 401 auth failure) will fail the same way every time, so don't retry
them.

**Exponential backoff with jitter.** Wait longer between each attempt (1s, 2s, 4s...) and add a bit of
randomness. If a thousand clients all retry at exactly the same moment, they knock the service over
again. Jitter spreads them out.

**Circuit breaker.** If a dependency keeps failing, stop calling it for a while. The breaker has three
states:

- **Closed** — normal; calls go through.
- **Open** — too many recent failures; calls fail immediately (or go to a fallback model) without
  waiting on a dead service.
- **Half-open** — after a cool-down, let one trial call through; if it works, close the breaker; if not,
  open it again.

This protects your own latency (no piling up of slow failing calls) and gives the struggling service
room to recover.

PlantGuard uses LiteLLM's `num_retries=3` for the Gemini 503s; a circuit breaker is planned for the
production milestone.

**Tiered fallbacks** make the circuit breaker useful: when the primary model's circuit opens, traffic
goes down a ladder, for example a frontier model → a fast mid-size model → a small self-hosted model →
a cached "good enough" answer or a polite "we're at capacity, please retry" message. The upstream
service never needs to know which tier answered.

The retry policy should also depend on **who is waiting**:

- **Interactive** (a user is staring at the screen): a 60-second backoff is effectively downtime. Use
  short, capped retries (say 500 ms, then 1 s) or fail fast to a fallback model.
- **Asynchronous** (a batch job): use long exponential backoff (1 min, 2 min, 4 min) and simply wait out
  a short provider outage.

## I11. The harness

If the model is the brain, the **harness** is everything else that makes it a working agent: the code
around the model.

It's responsible for:

- running the loop (call the model, run tools, append results, repeat);
- executing tools and catching their errors;
- managing context (what history to keep, when to summarise);
- enforcing limits on steps, tokens, time and cost;
- applying permissions (which tools this agent may use, which need approval);
- logging and tracing every step;
- deciding when to stop or escalate to a human.

The important idea: **the model proposes, the harness controls.** Most of an agent's reliability and
safety comes from the harness, not the model. When something goes wrong in production, the fix is
often in the harness: a missing cap, a missing check, missing logging.

A good interview add-on is what you'd log per step: prompt size, tool name and arguments, the result,
latency, token count and cost. That's what lets you debug later ([E17](INTERVIEW-GUIDE-3-EXPERT.md#e17-debugging-a-wrong-answer-in-production)).

## I12. ReAct vs planner–executor vs reflection

These are three common shapes for an agent's reasoning.

**ReAct** ([B9](INTERVIEW-GUIDE-1-BEGINNER.md#b9-the-react-loop)) decides one step at a time. It's flexible and handles surprises well, which suits
exploratory tasks where you don't know what you'll find. The downside: it can wander, repeat itself,
or lose sight of the overall goal.

**Planner–executor** writes a plan first ("1. diagnose, 2. check parts, 3. schedule a technician"),
then carries out each step. The executor can even be a cheaper model. Plans are easier to read, audit
and approve. The downside: if step 1 reveals something unexpected, the plan may be out of date, so good
designs let the planner revise it.

**Reflection** adds a review pass: after producing an answer, a critic checks it against the
requirements and the answer is revised. It catches mistakes but costs extra calls and time. A subtle
point: a model critiquing its own work shares its own blind spots, so a different model, or simple
rule-based checks, often catch more.

How to choose: exploration → ReAct; known multi-step processes → planner–executor; high-stakes outputs
→ add reflection or an independent checker. Real systems often combine them.

These sit within a slightly broader family of five classic agentic patterns: **reflection**, **tool
use**, **ReAct** (reflection plus tools in a loop), **planning**, and **multi-agent** collaboration.
Most real agents combine several. [I42](#i42-multi-agent-orchestration-patterns) covers how multiple agents can be arranged.

## I13. Long conversations: truncation, summaries, long-term memory

As a conversation grows, it eventually doesn't fit, or becomes slow and costly. There are three main
options, each with a weakness.

- **Truncate** — drop the oldest messages. Simple, but anything said early is simply gone, even if it
  was important ("by the way, the valve was replaced last week").
- **Summarise** — replace old turns with a summary. Keeps the gist, but summaries are **lossy**: the
  one detail that later turns out to matter is exactly the kind of thing a summary drops, and you
  don't notice until the agent gets it wrong.
- **Move facts to long-term memory** — store important facts outside the conversation and retrieve them
  when they're relevant. More work, but it survives across sessions.

It's also worth separating **session memory** (lasts for this conversation) from **long-term memory**
(persists across sessions and users, in a database).

In practice you combine them: keep the last few turns verbatim, keep a running summary of older turns,
and store key facts as **structured fields** (not just free text) so they're never summarised away.

## I14. Agent-managed memory and consolidation

There are two ways to fill long-term memory.

**App-managed memory:** your code decides what to save, for example "store every resolved event".
It's predictable but rigid.

**Agent-managed memory:** you give the agent memory *tools* such as `save_memory`, `update_memory` and
`search_memory`, and it decides what's worth remembering. It's more flexible, but now the model is
writing to a permanent store, which brings risks ([E6](INTERVIEW-GUIDE-3-EXPERT.md#e6-memory-going-bad-governance)).

**Consolidation**, which the course also calls "dreaming", is a background job that runs offline,
for example nightly. It reads raw episodes, merges duplicates, drops noise, and turns patterns into
durable facts or procedures. Think of it as turning a diary into a handbook. Fifty separate episodes of
"chiller trip after condenser fault" become one semantic fact, *"CHILLER-01 trips are usually
condenser-related"*, and maybe one procedural rule.

Without consolidation, memory grows endlessly, retrieval gets noisier, and contradictory old facts
linger.

## I15. Chunking strategies compared

Chunking ([B13](INTERVIEW-GUIDE-1-BEGINNER.md#b13-chunking--why-split-documents)) has several common strategies:

- **Fixed-size** — e.g. every 500 tokens, with some overlap between neighbours. Very simple, but it
  cuts mid-sentence or mid-table.
- **Recursive** — try to split on paragraphs; if a piece is still too big, split on sentences, and so
  on. Respects natural boundaries better. A common default.
- **Structure-based** — split using the document's own structure: headings, sections, tables, list
  items. Excellent for manuals, policies and other well-structured technical docs.
- **Semantic** — embed sentences and split where the topic shifts. Can produce very coherent chunks,
  but costs more to compute.

Chunk size is a trade-off. Small chunks match a question precisely but may lack the context needed to
answer. Large chunks carry context but their embedding is a blurrier average, so they match less
precisely.

A useful trick that sidesteps the trade-off is **parent–child retrieval**: search over small chunks
for precision, but hand the model the larger parent section they belong to, for context.

The honest interview answer to "what chunk size?" is *"it depends on the documents, and I'd measure it
with retrieval metrics on a golden set"* rather than quoting a magic number.

Two more strategies are worth knowing:

- **LLM-based chunking** — ask an LLM to split the document into self-contained pieces. It gives the
  best semantic boundaries but is the most expensive, and long documents may not fit its window.
- **Code chunking with ASTs** — for source code, parse it into an **Abstract Syntax Tree**, the tree
  your compiler sees (project → file → class → function). Chunk along that tree, one function or one
  class per chunk, instead of cutting every N lines. A chunk then always holds a complete, meaningful
  unit, which is how AI coding assistants index codebases.

Whatever the strategy, **smart chunk metadata** helps a lot. Store the parent section and document
title with each chunk, so a retrieved paragraph still carries its context ("Chiller manual → Fault
codes → High-pressure trip").

## I16. Ingesting messy real-world documents

Demo RAG uses clean text. Real documents are messy, and **bad ingestion caps the quality of everything
after it**: no retriever can find text that was never extracted properly.

Common problems:

- **Scanned PDFs** are images; you need OCR, which makes mistakes, especially with numbers.
- **Tables** get flattened into a jumble of values that no longer line up with their headers.
- **Headers, footers and page numbers** repeat on every page and pollute chunks.
- **Multi-column layouts** get read across the columns in the wrong order.
- **Diagrams and figures** hold information that plain text extraction misses entirely.

What helps: clean text before chunking (strip repeated headers and footers), keep tables intact or
convert them to a structured form, attach **metadata** to each chunk (source document, section,
equipment type, date) for filtering and citations, and **look at samples** of what was actually
extracted. Ten minutes of eyeballing catches problems that metrics miss.

In PlantGuard, section labels initially captured some body text along with the heading, and had to be
fixed. That's a small example of ingestion quietly going wrong.

## I17. Hybrid search

Hybrid search runs **keyword search (BM25) and semantic search together** and merges the results, so
each covers the other's blind spot ([B14](INTERVIEW-GUIDE-1-BEGINNER.md#b14-keyword-vs-semantic-search)).

Take a query like *"VPW-P-00043 seal leaking"*. BM25 nails the exact part number; semantic search finds
sections about "seal failure" and "fluid escaping" that don't use the word "leaking". Together they
usually beat either one alone, especially on technical content full of codes and IDs.

Two practical details come up in interviews:

- **Merging scores.** BM25 scores and cosine similarities are on completely different scales, so you
  can't just add them. The common approach is to merge by **rank** instead, using Reciprocal Rank Fusion
  ([I18](#i18-reranking-rrf-and-rag-fusion)).
- **Metadata filters.** Filtering before ranking (only this plant, only chiller manuals, only current
  revisions) often helps more than any clever ranking, because it removes wrong-but-similar documents
  entirely.

## I18. Reranking, RRF and RAG Fusion

These are all ways to improve *which* chunks end up in the prompt.

**Reranking.** First-stage retrieval (vector or hybrid) is fast but approximate. It compares
precomputed vectors, so the query and the document never actually "meet". A **reranker**, usually a
*cross-encoder*, reads the query and each candidate chunk *together* and scores how well they match.
That's much more accurate but much slower, so you only rerank a shortlist: retrieve 30 quickly, rerank,
keep the best 5.

**Reciprocal Rank Fusion (RRF)** merges several ranked lists (say BM25's list and the vector list).
Each document gets a score of `1 / (k + rank)` from each list it appears in, and the scores are added
up. `k` is usually 60. A document that ranks fairly well in *both* lists beats one that ranks first in
one list and nowhere in the other. Because it uses ranks, not raw scores, the scale problem disappears.
Why 60? It's an empirical default that softens the gap between rank 1 and rank 2, so no single list
dominates.

**RAG Fusion** goes further on the query side: the LLM writes several rephrasings of the user's
question, you retrieve for each, and you fuse all the lists with RRF. It helps when users phrase things
vaguely or differently from the documents, at the cost of extra retrieval calls.

**Cross-encoder vs LLM as the reranker.** The reranker doesn't have to be a dedicated cross-encoder
model. You can also ask an LLM to score the candidates. Each option has a trade-off:

- **Cross-encoder** (e.g. `ms-marco-MiniLM`): small, runs locally, ~10–50 ms, no API cost. But it adds
  a model dependency, and it was trained on general web search, so it may misjudge domain jargon.
- **LLM reranker**: one call scores all candidates together ("rate each excerpt 0–10 for how directly
  it answers the query"). It understands domain language and nuance with no extra model to host. The
  costs are latency (a second or two), money and rate limits, and scores vary slightly between runs.

Two habits make an LLM reranker production-safe:

- **Cache** scores by (model + query + candidate IDs).
- **Fall back** to the hybrid order if the call fails, so retrieval never breaks because of the
  reranker.

PlantGuard uses an LLM reranker over 10 hybrid candidates per source. For "lead time of part
VPW-P-00035", dense search returned generic preamble sections. The reranker promoted the *Approved
Supplier Tiers and Lead Times* section, the one that actually answers the question.


## I19. Measuring retrieval and RAG quality

You want to measure two things separately: **did retrieval find the right material?** and **did the
model use it well?** If you only judge final answers, you can't tell which part failed.

Retrieval metrics (computed against a golden set that says which chunks are relevant):

- **Recall@k** — of the relevant chunks, how many appeared in the top k? Usually the first metric to
  look at: if the right chunk isn't retrieved, nothing downstream can fix it.
- **Precision@k** — of the top k, how many are relevant? Low precision means noise in the prompt.
- **MRR (Mean Reciprocal Rank)** — how high up is the *first* relevant result? Rank 1 scores 1, rank 2
  scores 0.5, and so on.
- **nDCG** — rewards putting the *most* relevant results near the top, and supports graded relevance
  (very relevant vs somewhat relevant).

Answer-level metrics, often computed with frameworks like **RAGAS**:

- **Faithfulness** — is every claim supported by the retrieved context? (groundedness)
- **Answer relevance** — does it actually answer the question asked?
- **Context precision / recall** — the retrieval metrics viewed from the answer's side.

PlantGuard tracks must-cite recall@6: for each golden scenario, whether the documents that *must* be
cited were in the six retrieved chunks. It's currently 86%.

## I20. LangGraph: state, checkpoints, interrupts

LangGraph is a framework for building agent workflows as graphs ([B17](INTERVIEW-GUIDE-1-BEGINNER.md#b17-chains-vs-graphs)). Three of its features are
worth understanding properly.

**State.** You define a typed state object, for example the event, gathered facts, retrieved sections,
the draft decision and the approval status. Each node receives the state and returns updates to it.
This makes data flow explicit: you can always see what each step knew.

**Checkpointer.** When you compile the graph with a checkpointer, the state is saved after every node,
under a *thread ID* (one per workflow run). If the process crashes, you resume that thread from its last
checkpoint. In production the checkpointer should be a real database (such as Postgres), not in-memory,
or a restart loses everything.

**Interrupts.** A node can call `interrupt(...)` to pause the run. Execution stops, the state is
already saved, and control returns to your application, which can show the draft to a supervisor. When
they respond, possibly hours later, you resume the thread with their input and the graph continues
from exactly where it paused. This is why HITL needs the checkpointer *first*: without saved state
there's nothing to resume.

Checkpoints also enable **time travel**: you can inspect the state at any earlier step, or replay and
fork from it ("what would have happened if retrieval had returned different chunks?"). That's very
useful for debugging.

A common mistake is implementing a human pause as a blocking `input()` call or a loop that waits. That
ties up a process, and a restart loses everything.

## I21. Supervisor routing and loop caps

In a **supervisor** pattern, one coordinating agent receives the task, decides which specialist should
handle the next part (diagnosis, parts, scheduling), passes control, gets the result back, and decides
again: another specialist, or finish.

The classic failure is a **loop**: the supervisor keeps bouncing between two agents ("diagnosis needs
more data" → "data agent returns" → "diagnosis needs more data" ...) and never finishes, burning tokens
the whole time.

Protections, all enforced in code:

- a cap on total steps or handoffs;
- a cap on visits to any single agent;
- detection of repeated states (same question, same answer → stop);
- a token or cost budget for the whole run.

When a cap is hit, the system should stop and **escalate** with whatever it has learned, not crash or
silently return nothing.

A useful nuance: routing doesn't always need an LLM. If the rule is clear ("if parts are needed, go to
the parts agent"), write it in code. It's cheaper, faster and predictable. Use an LLM to route only
when the decision is genuinely fuzzy.

## I22. How MCP works; when to use A2A

**MCP** has three roles:

- the **host** — the AI application the user interacts with (an IDE, a chat app, your copilot);
- a **client** inside the host — one connection per server;
- **servers** — programs that expose capabilities in a standard way. A server can offer **tools**
  (functions to call), **resources** (data to read) and **prompts** (templates).

Servers can run locally (talking over stdio) or remotely (over HTTP). The big win is the maths of
integration: without a standard, N agents × M tools means N×M custom integrations. With MCP, each tool
is wrapped once as a server and each agent implements the client once: **N + M**.

"Why not just REST APIs?" is a fair question. MCP adds a standard way for the agent to **discover**
what's available and how to call it, in a form models can use directly, without writing glue code per
API.

**A2A** is for when the other side isn't a tool but an **agent with its own reasoning**, often owned
by another team or company. Agents publish an **Agent Card** describing what they can do; a client agent
sends a *task*, and the remote agent works on it (possibly over time, with progress updates) and
returns results. You don't see or control its internals, which is the point.

A rule of thumb: if you'd call it a function, use MCP; if you'd delegate to a colleague, use A2A.

## I23. AG-UI and AP2

Two more protocols complete the course's picture of the stack.

**AG-UI (Agent–User Interaction)** standardises how an agent talks to a **user interface** while it
works. Instead of the user staring at a spinner, the agent streams events: "started", "calling
`check_spare_parts`", "found 3 in stock", "here's a draft — approve?". It also covers state updates and
requests for human input. That makes agents feel transparent and lets users step in mid-run.

**AP2 (Agent Payments Protocol)** addresses a hard question: if an agent buys something, how do you
prove the user actually authorised *that* purchase? AP2 uses signed **mandates**:

- an **intent mandate** — what the user allowed in general ("reorder seals up to ₹50,000 from approved
  suppliers");
- a **cart mandate** — the specific purchase the agent is about to make, which can be checked against
  the intent.

Together they give a verifiable, auditable trail of who authorised what, which matters for fraud,
disputes and liability.

Under the hood, AG-UI streams **typed JSON events** over Server-Sent Events, for example
`TEXT_MESSAGE_CONTENT` (tokens), `TOOL_CALL_START` (a tool is running), `STATE_DELTA` (a change to shared
state such as a table or code) and `AGENT_HANDOFF`. The value is the same as any standard: write the
backend once, and any compatible UI can render it, whether the agent was built in LangGraph, CrewAI or
something else. MCP (agent ↔ tools), A2A (agent ↔ agent) and AG-UI (agent ↔ user) are best seen as
**layers of one stack**, not competitors.

## I24. The four caches in LLM serving

"Caching" in LLM systems means four quite different things, at different layers. Interviewers like it
when you can separate them.

**1. KV cache — inside one request.** When the model generates token 501, attention needs the keys and
values ([B21](INTERVIEW-GUIDE-1-BEGINNER.md#b21-attention-and-positional-encoding)) of tokens 1–500. Recomputing them every step would be wasteful, so the serving engine
stores them in a **KV cache** after the first pass (*prefill*) and only computes the new token's values
at each step (*decode*). This is automatic and is why generation is feasible at all. The catch is
memory: the KV cache grows with context length and with the number of users served at once, and it's
often what limits how many requests a GPU can handle.

**2. Prefix cache — across requests, in the serving engine.** Many requests start with the same text,
such as the same system prompt and tool definitions. Engines like vLLM split the prompt into blocks,
hash them, and when a new request starts with blocks already computed, reuse those KV blocks instead of
recomputing them. That cuts time-to-first-token. You see this if you self-host models.

**3. Prompt cache — the provider's version, which you see on the bill.** Hosted APIs (Anthropic, OpenAI,
Google) offer prompt caching: if your prompt begins with the same prefix as a recent request, those
cached input tokens are billed at a much lower rate and processed faster. It's the same idea as prefix
caching, exposed as a pricing feature. The rules matter: the prefix must be **byte-for-byte identical**,
caches expire after a few minutes, and some providers need you to mark what to cache. Design rule: put
stable content (system prompt, tools, reference docs) first and changing content (user question)
last. A timestamp at the top of the prompt silently breaks caching.

**4. Semantic cache — in your application.** Before calling the model at all, embed the user's question
and look for a previously answered question that's *similar enough*. If one is found, return the stored
answer: **no LLM call**, near-zero cost and latency. It works well for FAQ-style traffic ("how do I
reset my password?" asked 500 different ways).

But semantic caching has real risks, and interviewers will probe them:

- **Stale answers** — the stored answer was right last month. You need expiry times, and invalidation
  when the underlying data changes.
- **False hits** — "cancel order 123" and "cancel order 124" are semantically almost identical but need
  different answers. You need a high similarity threshold, and shouldn't cache anything personal or
  parameterised.
- **Leaks across users** — an answer containing one user's data served to another. Scope the cache per
  user or permission level.

There's also a simpler **exact-match response cache** (same input → same stored output), which is safe
for deterministic jobs. PlantGuard caches **embeddings** in `.embcache`, so re-running ingestion
doesn't pay to embed the same text twice. That's the same idea applied to embeddings.

**Application-level caching patterns** sit on top of the four caches and are just as common in system
design interviews:

- **Exact-match cache with normalised keys.** Hash the prompt and look it up in Redis. Normalise first
  (trim whitespace, lowercase, maybe strip filler words), or trivial differences cause misses. A viral
  question asked 10,000 times then costs one LLM call. Include the **model and prompt version** in the
  key, so an upgrade doesn't serve old answers.
- **Proactive (pre-computed) caching.** If you know what users will ask for, generate it ahead of time:
  build tomorrow's personalised daily summaries in a 6 a.m. batch job, so they appear instantly at 9 a.m.
  This moves latency from online (user waiting) to offline.
- **Request coalescing** (also called request collapsing or single-flight). When many identical requests
  arrive *at the same moment*, before the cache has an answer, only the first goes to the LLM; the
  others wait for it and share its result. This prevents a *thundering herd*, for example during an
  outage when thousands ask "is the service down?".
- **Cache-aside with invalidation.** The app checks the cache, falls back to the LLM on a miss, then
  stores the result. Invalidate on source changes and on model upgrades, and use TTLs for anything that
  can go stale.

A related idea is **CAG (Cache-Augmented Generation)**. Split knowledge into two kinds:

- **stable** knowledge (policies, reference guides), loaded once into a cached prompt prefix (the
  model's KV cache);
- **changing** knowledge, still fetched per question with RAG.

The model then doesn't reprocess the same static text on every call. Only cache what's truly stable and
high-value, or you'll run out of context.

## I25. Inside a vector database

[B12](INTERVIEW-GUIDE-1-BEGINNER.md#b12-embeddings-and-vector-databases) explained what a vector DB does. Here is how it does it, which comes up in interviews for RAG roles.

**Similarity metrics.** How "close" two vectors are can be measured in a few ways:

- **Cosine similarity** — the angle between vectors, ignoring their length. The most common choice for
  text embeddings.
- **Dot product** — angle and length together. Equivalent to cosine when vectors are normalised (length
  1), which many embedding models do.
- **Euclidean (L2) distance** — straight-line distance.

Use the metric the embedding model was trained for; its docs usually say.

**Why indexes are needed.** Comparing a query against every vector (*brute force*, or *flat* search)
is exact, but slow once you have millions of vectors. So vector DBs use **approximate nearest neighbour
(ANN)** indexes, which are much faster in exchange for occasionally missing a true neighbour. The main
families:

- **HNSW (Hierarchical Navigable Small World)** — builds a multi-layer graph linking each vector to
  nearby ones. Search starts at a sparse top layer and hops closer and closer, like using motorways,
  then main roads, then side streets. Very fast with high recall; uses a lot of memory. The default in
  Qdrant, Weaviate, pgvector and others.
- **IVF (Inverted File Index)** — clusters vectors into buckets in advance. At query time, find the
  nearest few cluster centres and only search inside those buckets (the number searched is called
  `nprobe`). Lighter on memory, and recall depends on how many buckets you search.
- **PQ (Product Quantization)** — **compresses** vectors into short codes, so far more fit in memory,
  at some loss of accuracy. Often combined with IVF (IVF-PQ) for billion-scale data.

All of them have tuning knobs that trade **recall against speed** (for HNSW, `ef` and `M`). That's
important: if retrieval quality drops as data grows, the index settings are one suspect ([E20](INTERVIEW-GUIDE-3-EXPERT.md#e20-rag-accuracy-fell-from-85-to-60-after-adding-documents)).

**Metadata and filtering.** Each vector is stored with a **payload**: source document, section, date,
category, permissions. You can filter on it ("only chiller manuals", "only documents this user may
see"). There's a subtle issue here:

- **Post-filtering** (search first, then drop non-matching results) can leave you with too few results
  if most of the top-k get filtered out.
- **Pre-filtering**, or filtering during search, avoids that, and good vector DBs handle it efficiently
  with payload indexes.

**Storage.** One system keeps vectors, metadata and indexes together, so search and filtering happen in
one place.

In PlantGuard, each manual section is stored in Qdrant with its vector and a payload (document title,
section, asset type, plant-wide or asset-specific), which is what makes the split search (3 asset + 3
plant) possible.

## I26. Choosing an embedding model

*"What would you consider when choosing an embedding model, and how does the embedding dimension
matter?"* is a common question for RAG roles.

Things to weigh:

- **Retrieval quality on your data.** Public leaderboards (like MTEB) are a starting shortlist, but
  domain matters. A model great on web text may be average on maintenance logs or legal contracts.
  Test two or three candidates on your own golden set with recall@k.
- **Language support**, if your documents or users aren't all in English.
- **Maximum input length** — how long a chunk it can embed without cutting it off.
- **Cost and latency** — per-token pricing for hosted models, or GPU cost if self-hosted. You embed the
  whole corpus once, but every query too.
- **Hosting and privacy** — can documents leave your network? If not, you need an open model you can run
  yourself.
- **Stability** — if the provider retires the model, you must re-embed everything ([E22](INTERVIEW-GUIDE-3-EXPERT.md#e22-changing-the-embedding-model-with-zero-downtime)).

**Dimension** is the length of each vector (384, 768, 1,536, 3,072...). More dimensions can capture
finer meaning, but:

- **Storage grows linearly.** 1 million chunks × 3,072 dimensions × 4 bytes ≈ 12 GB of raw vectors; at
  768 dimensions it's about 3 GB. Indexes like HNSW add more on top.
- **Search gets slower and uses more memory**, because each comparison involves more numbers.
- **Quality gains flatten.** Going from 768 to 3,072 often gives a small improvement, sometimes none on
  your data.

A useful modern detail: many models are trained with **Matryoshka representation learning**, so you can
keep only the first part of the vector (say 768 of 3,072 numbers) and lose surprisingly little quality.
That gives you a dial between cost and accuracy without changing models.

PlantGuard uses `gemini-embedding-001` at the full 3,072 dimensions. With only about 100 chunks storage
is trivial, but at millions of chunks you'd test a smaller dimension.

## I27. Choosing a vector database

There are many options (Pinecone, Weaviate, Milvus, Qdrant, Chroma, pgvector, OpenSearch,
Elasticsearch) and an interviewer usually wants to see *how* you'd choose, not a favourite.

Questions to ask:

- **Scale** — thousands, millions or billions of vectors? Chroma is great for prototypes; Milvus and
  Pinecone are built for very large scale.
- **Do you already run a database?** If you're on Postgres, **pgvector** keeps vectors next to your
  relational data, in one system to back up, secure and join against. It's often enough up to millions
  of vectors.
- **Hybrid search** — do you need keyword (BM25) and vector search together? OpenSearch and
  Elasticsearch are strong at keyword search; Weaviate and Qdrant support hybrid search natively.
- **Filtering** — how heavily do you filter on metadata, and how well does the DB handle filtered
  search?
- **Managed vs self-hosted** — managed (Pinecone, Qdrant Cloud) saves operational work; self-hosted gives
  control and keeps data in your network.
- **Operations** — backups, replication, multi-tenancy, access control, zero-downtime re-indexing
  (collection aliases help, [E22](INTERVIEW-GUIDE-3-EXPERT.md#e22-changing-the-embedding-model-with-zero-downtime)), and cost at your scale.

A good closing line: *"choose what fits your needs; for many teams the right first answer is pgvector or
a managed service, and you move only when you hit a measured limit."*

## I28. A tour of RAG architectures

"RAG" isn't one design. It's a family that grows in sophistication, each step fixing a weakness of the
previous one. Knowing the family, and *why* each exists, is a strong interview signal.

**1. Naive RAG.** Embed the query, fetch the top-k chunks, send them to the LLM. Simple and fast, and
fine for straightforward lookups. It struggles with vague questions, questions that need facts from
several places ("multi-hop"), and exact terms like codes.

**2. Advanced RAG.** Add steps before and after retrieval: **rewrite the query** (fix typos, expand
abbreviations, make it self-contained in a chat), retrieve, **rerank**, and **compress** the context
(keep only relevant sentences). Most production systems should start here, because it fixes the biggest
failures without over-engineering.

**3. Hybrid RAG.** Run keyword search and vector search together and merge the results ([I17](#i17-hybrid-search)). It catches
both exact terms and paraphrases.

**4. Reranked RAG.** Retrieve more results than you need (say 30), then use a reranker to pick the best
5 ([I18](#i18-reranking-rrf-and-rag-fusion)). Similarity scores measure *mathematical closeness*, not actual relevance, and the reranker fixes
that. Interviewers often ask: *"why rerank if the retriever already returns the top 10?"* Because the
retriever compares precomputed vectors separately, while a cross-encoder reranker reads the question and
each chunk *together*, and so judges relevance much more accurately. Its higher cost is only paid on a
short list.

**5. Multi-query RAG.** Have the LLM rewrite the question several ways, search with each, and merge the
results. Different phrasings surface documents a single wording would miss. More queries means more
cost and latency.

**6. Self-query retriever.** Use the LLM to turn a natural-language question into **a semantic search plus
structured filters**. *"Papers about ML from 2022"* becomes vector search for "ML papers" with the filter
`year = 2022`. That's much more precise, but it needs good metadata and reliable parsing.

**7. Hierarchical (parent–child) RAG.** Search small, precise chunks, but return their larger parent
section or document for context ([I15](#i15-chunking-strategies-compared)). That gives better grounding at the cost of more complex
indexing.

**8. Modular RAG.** Treat retrieval, reranking, compression and tools as **pluggable components** rather
than one fixed pipeline, so each can be swapped or skipped per query. It's the architecture for teams
whose needs have outgrown one linear flow, and it takes more engineering.

**9. RAG-Fusion.** Generate query variants, search with all of them, and merge the results with
Reciprocal Rank Fusion ([I18](#i18-reranking-rrf-and-rag-fusion)). Great when users' wording differs from the documents'.

The remaining three, **Graph RAG**, **Corrective RAG** and **Agentic RAG**, are more advanced and
covered in [E27](INTERVIEW-GUIDE-3-EXPERT.md#e27-graph-rag-corrective-rag-agentic-rag--and-choosing-an-architecture), along with how to choose.

The key message from the infographic is worth repeating: *the best RAG architecture isn't the one with
the most features; it's the one that fits your data, your goals and your users.* PlantGuard is currently
"naive RAG with a split budget" and has golden-set numbers. Hybrid search and reranking are the next
planned steps, to be added only if they move those numbers.

Three more variants often come up:

- **HyDE (Hypothetical Document Embeddings).** Questions and answers are often phrased very differently,
  so a question's vector may not land near the answer's vector. HyDE first asks the LLM to write a
  *hypothetical answer*, which can be partly wrong, embeds **that**, and searches with it. A fake answer
  "looks like" real answers far more than the question does. The cost is an extra LLM call per query.
- **Multimodal RAG.** Index and retrieve across text, images, tables and audio, so a text question can
  pull back a wiring diagram or a photo of a part.
- **Adaptive RAG.** First decide how hard the question is: simple ones get a single retrieval, complex
  ones get broken into sub-questions with multi-step retrieval. Like a triage nurse deciding who needs a
  quick check and who needs the full workup.

## I29. AI gateway

Once several apps in a company call several LLM providers, each team ends up re-implementing the same
things: API keys, retries, rate limits, logging, cost tracking. An **AI gateway** is a single service that
sits between all your apps and all the model providers: *one control plane, many models.*

Apps call the gateway (usually with an OpenAI-compatible API), and the gateway handles:

- **Auth and key management** — apps never hold provider keys; the gateway does.
- **Routing** — send each request to the right model (cheap vs strong), with **fallbacks** when a
  provider is down or rate-limited.
- **Rate limits and budgets** — per team, app or user, so one runaway job can't burn the monthly
  budget.
- **Caching** — response or semantic caching in one place ([I24](#i24-the-four-caches-in-llm-serving)).
- **Logging and cost attribution** — every call recorded with tokens, cost and latency, by team and
  feature.
- **Guardrails** — PII redaction or content filters applied centrally ([B25](INTERVIEW-GUIDE-1-BEGINNER.md#b25-guardrails)).

Examples include the LiteLLM proxy, Portkey, Kong AI Gateway and Cloudflare AI Gateway, plus cloud
offerings like Azure API Management.

The trade-off: it's one more hop (slight added latency) and a critical piece of infrastructure. If the
gateway is down, every AI feature is down, so it needs to be highly available.

PlantGuard uses LiteLLM as a *library*, which gives it a provider-agnostic client. Running LiteLLM as a
*proxy server* shared by many apps is what turns it into a gateway.

Why not just call the provider SDK directly from each service? Because at scale it creates four
problems:

- **vendor lock-in** — every service is wired to one SDK;
- **inconsistent reliability** — one team retries well, another crashes on the first timeout;
- **observability black holes** — no single place to see spend and errors;
- **key sprawl** — API keys scattered across many services.

The gateway is the same idea as the classic microservices API gateway, applied to models.

A mature gateway's router can also do **dynamic traffic control**:

- **Load shedding** — if the primary model's p99 latency breaches the SLA, shift traffic to a faster,
  cheaper model, even for "complex" requests, until it recovers.
- **Cost ceilings** — if a single prompt is enormous (say over 8k tokens), force it to a cheaper model,
  or reject it, so one request can't blow the budget.

## I30. Making LLM output deterministic, and writing robust system prompts

*"How do you make the output deterministic?"* The honest answer starts with: *you can make it much more
consistent, but not perfectly deterministic*, followed by how.

Levers that increase consistency:

- **Temperature 0** (or very low) makes the model pick the most likely token instead of sampling. That
  greatly reduces variation, but **doesn't guarantee identical outputs**: GPU arithmetic and server-side
  batching can still cause tiny differences that snowball.
- **A `seed` parameter**, where the provider offers one, improves reproducibility, though it's still
  "best effort".
- **Pin the model version.** "Latest" aliases change behaviour silently.
- **Structured output** narrows what the model can say ([B5](INTERVIEW-GUIDE-1-BEGINNER.md#b5-structured-output)).
- **Clear, specific instructions and examples** ([B23](INTERVIEW-GUIDE-1-BEGINNER.md#b23-zero-shot-vs-few-shot-prompting)) leave less room for interpretation.
- **Cache results** for repeated inputs, so the same input returns the same stored output.
- **Move logic out of the model.** Anything computable (sums, thresholds, lookups) should be code.

And design the system to **tolerate** variation: validate outputs, compare decisions rather than exact
wording in tests, and run evals more than once.

**Robust system prompts** that work across many users:

- State the **role, the goal and the boundaries** clearly: what to do, what not to do, and what to do
  when unsure ("if the information isn't in the provided documents, say so").
- **Separate instructions from data** using clear delimiters or tags, so user text isn't mistaken for
  instructions ([E7](INTERVIEW-GUIDE-3-EXPERT.md#e7-prompt-injection)).
- Specify the **output format** exactly.
- Cover **edge cases** explicitly (empty input, conflicting data, out-of-scope requests).
- Keep it **versioned and tested** like code: a prompt change goes through the eval suite ([I35](#i35-logging-prompts-and-outputs-versioning-prompts-and-context)).

Typical temperature settings:

- **around 0–0.2** for extraction, classification and code, where consistency matters;
- **around 0.7–1.0** for brainstorming, creative writing or generating varied synthetic data.

The architectural consequence: you **can't unit-test LLM output with string equality**. Tests must
check properties (valid schema, correct decision, required facts present) or run at temperature 0
during regression tests.

## I31. LoRA, QLoRA and full fine-tuning

These are three ways to fine-tune ([B24](INTERVIEW-GUIDE-1-BEGINNER.md#b24-fine-tuning-in-plain-words)), differing in how much of the model you change and how much GPU
memory you need.

**Full fine-tuning** updates **all** the model's weights. It gives the most flexibility and potentially
the best results, but it needs a lot of GPU memory (the weights, their gradients and optimizer state for
billions of parameters). It produces a full new copy of the model, and it risks **catastrophic
forgetting**: the model gets better at your task and worse at general skills.

**LoRA (Low-Rank Adaptation)** **freezes** the original weights and trains small extra matrices added
alongside certain layers. The trick is that the needed change can be well approximated by two thin
matrices multiplied together, so you train perhaps 0.1–1% of the parameters. Benefits: much less memory,
faster training, tiny adapter files (megabytes rather than gigabytes), and you can keep several adapters
for different tasks on one base model.

**QLoRA** is LoRA on top of a base model **quantized to 4 bits** ([I32](#i32-quantization-and-hosted-apis-vs-open-source-models)). The frozen base takes about a
quarter of the memory, so you can fine-tune large models on a single GPU. The cost is slightly slower
training and sometimes a small quality drop.

Rule of thumb: **QLoRA when GPU memory is tight, LoRA as the usual default, full fine-tuning when you
have the hardware and need maximum quality** or a big behaviour change.

*"What actually changes during fine-tuning?"* is a common follow-up. The answer:

- The **weights** (all of them, or just the adapters) are nudged to make your examples more likely.
- The **optimizer**, usually **AdamW**, decides how each weight moves based on its gradients and
  momentum.
- The **learning-rate scheduler** controls step size over time. Typically there's a short **warm-up**
  (start small to avoid wrecking the pre-trained weights), then a gradual **decay** (linear or cosine).
- **Layer freezing** keeps some layers fixed, often the lower ones that hold general language skills,
  while the top layers adapt. That's cheaper, and it reduces forgetting.

Signs to watch: training loss falling while validation loss rises means **overfitting**. And always
compare against the un-tuned model plus a good prompt; sometimes fine-tuning isn't worth it.

The LoRA trick in a little more detail. A weight matrix `W` has size d × k. Instead of learning a full
d × k update, LoRA learns two thin matrices: `A` (d × r) and `B` (r × k), where the rank `r` is small
(say 8 or 16). Their product has the right shape, d × k, but far fewer numbers to train. `B` starts at
zero, so at the beginning the model behaves exactly like the original. A scaling factor `alpha`
controls how strongly the adapter affects the output. In practice LoRA is often applied only to the
attention weights.

Several variants tweak this idea:

- **LoRA-FA** freezes `A` and trains only `B`, to save activation memory.
- **VeRA** shares frozen random matrices across layers and trains only small scaling vectors.
- **Delta-LoRA** also nudges `W` itself using the change in `A·B`.
- **LoRA+** uses a higher learning rate for `B`, which converges better.
- **LoRA-drop** keeps adapters only in the layers that actually matter.
- **DoRA** splits each weight into magnitude and direction and adapts them separately.

You don't need to memorise these. The interview point is that they all keep the base model frozen and
train a small add-on.

Why this matters at scale: a 175-billion-parameter model is about 350 GB in 16-bit precision. A full
fine-tuned copy per customer would be impossible to store and serve, while LoRA adapters are megabytes
each and can be swapped on one shared base model.

## I32. Quantization, and hosted APIs vs open-source models

**Quantization** stores model weights with fewer bits. Models are usually trained in 16-bit precision
(FP16 or BF16); quantizing to **8-bit (INT8)** roughly halves the memory, and **4-bit (INT4)** roughly
quarters it. Smaller weights mean the model fits on cheaper GPUs, more requests fit on one GPU, and
inference is often faster, because moving weights from memory is usually the bottleneck.

The cost is some loss of accuracy. 8-bit is usually close to lossless; 4-bit is often acceptable, but
can hurt on harder reasoning, maths or code. Common methods include GPTQ and AWQ, and GGUF files are
popular for running models on laptops.

**When should you quantize?** When you **self-host** and are limited by GPU memory or cost, when you need
to run on smaller hardware (on-premises or edge devices), or when you need more throughput per GPU.
Always measure the quantized model on your own eval before switching. You don't quantize hosted API
models; the provider handles serving.

**Hosted APIs vs open-source (self-hosted) models** is a related decision:

| | Hosted API (OpenAI, Anthropic, Gemini) | Open-source, self-hosted (Llama, Mistral, Qwen, Gemma) |
|---|---|---|
| Quality | usually the strongest models | gap has narrowed; strong for many tasks |
| Start-up effort | minutes | GPUs, serving stack (vLLM, TGI), ops |
| Cost | pay per token; great at low or variable volume | fixed GPU cost; cheaper at high, steady volume |
| Data control | data goes to the provider (with contracts) | stays inside your network |
| Customisation | limited fine-tuning options | full control: fine-tune, quantize |
| Risks | price, model and policy changes outside your control | you own uptime, scaling and security |

Many companies use **both**: hosted frontier models for hard tasks, and a small open model on-premises
for simple, high-volume or sensitive tasks. That's the "hybrid on-prem/cloud routing" idea from the
cost infographic.

The choice also has a **compliance** side, often called **data residency**:

- **Public APIs** — data leaves your network. That may be unacceptable for health, payment or personal
  data without zero-retention agreements.
- **Private cloud endpoints** (Azure OpenAI, AWS Bedrock, Vertex AI) — data stays inside your cloud
  provider's boundary, but you depend on its availability.
- **Self-hosted open-weight models** — full control, needed for strict or air-gapped environments. You
  trade operational work (GPUs, scaling) for compliance safety.

To try open models locally, common tools are **Ollama** (one command to pull and run a model),
**LM Studio** (a desktop app with a chat UI), **llama.cpp** (lightweight C++ inference, good on laptops)
and **vLLM** (a high-throughput server with an OpenAI-compatible API, used in production).

## I33. LangGraph vs Google ADK

Both are popular frameworks for building agents, with different philosophies.

**LangGraph** (from the LangChain team) is a **low-level graph framework**. You define the state, the
nodes and the edges yourself ([B17](INTERVIEW-GUIDE-1-BEGINNER.md#b17-chains-vs-graphs), [I20](#i20-langgraph-state-checkpoints-interrupts)). Its strengths are fine control over complex, stateful flows:
durable **checkpointing**, **interrupts** for human approval, time travel for debugging, and LangSmith
for tracing. It's model-agnostic and cloud-agnostic. The trade-off is that you write more of the
structure yourself.

**Google ADK (Agent Development Kit)** is a **code-first agent toolkit** from Google. You define agents
(an LLM agent with instructions and tools) and compose them into **hierarchies** of sub-agents, with
ready-made **workflow agents**: *Sequential*, *Parallel* and *Loop*. It comes with built-in tools,
evaluation utilities, a dev UI, native **A2A** support, and smooth deployment to Google Cloud (Vertex AI
Agent Engine, Cloud Run). It's optimised for Gemini but can use other models.

How to choose:

- **LangGraph** — when you need precise control over a complex flow, durable state and resume,
  human-in-the-loop at specific points, or you want to stay cloud-neutral.
- **ADK** — when you're on Google Cloud or using Gemini, want to assemble multi-agent hierarchies
  quickly from standard building blocks, and value the integrated deployment and eval tooling.

Either way, the durable-ideas principle ([E12](INTERVIEW-GUIDE-3-EXPERT.md#e12-choosing-a-framework-without-getting-locked-in)) applies: keep your tools, business logic and evals in your
own code, so the framework stays a replaceable layer.

## I34. What changed between MCP versions

Interviewers sometimes ask *"what's the difference between MCP v1 and v2?"* It's worth knowing that MCP
doesn't use simple version numbers. The specification is released as **dated revisions**, and the
question usually means *"what changed between the original release and the current spec?"*

The broad story:

- **Original release (November 2024)** — the core model of hosts, clients and servers; tools, resources
  and prompts; local servers over **stdio** and remote servers over HTTP with Server-Sent Events. Remote
  authentication wasn't really standardised, which made production remote servers awkward.
- **March 2025 revision** — a proper **authorization framework based on OAuth 2.1**; a new
  **Streamable HTTP** transport replacing the older HTTP+SSE approach, which is simpler to run behind
  normal web infrastructure; and **tool annotations**, so a tool can declare itself read-only or
  destructive and clients can treat it accordingly.
- **June 2025 revision** — **structured tool output** (tools can declare an output schema and return
  typed data, not just text); **elicitation**, so a server can ask the user for missing information
  mid-task; resource links in tool results; and tighter security, with MCP servers treated as OAuth
  resource servers, so tokens are issued for a specific server and can't be replayed elsewhere.
- **Later revisions** continued in the same direction, for example support for **long-running
  (asynchronous) tasks** and further authorization improvements.

So the theme is: **MCP grew from a local, developer-tool protocol into one fit for remote, production
use**, with real auth, simpler transport, richer typed results and more ways to keep humans in control.
If asked in an interview, say that, and say you'd check the current spec for exact details. That's
better than reciting version numbers you're unsure of.

## I35. Logging prompts and outputs; versioning prompts and context

*"How do you log prompts and outputs for debugging and auditing?"* and *"how do you track and version
changing context?"* go together.

**What to log for every LLM call:** a request or trace ID linking all steps of one run; the full prompt
(or references to its parts); the model name and exact version; parameters (temperature, max tokens);
the raw response; the parsed and validated result; tokens, cost and latency; which retrieved documents
and which prompt version were used; and the final action or route taken.

**Doing it responsibly:**

- **Redact or mask PII** before logging, or store sensitive logs separately with tighter access.
- Set **retention periods**: debugging needs recent data; audit may need longer, with protection
  against tampering.
- **Control access**: prompts often contain business data.
- **Sample** at very high volume, but keep 100% of errors, escalations and flagged cases.

**Versioning prompts and context:**

- Keep prompts in **version control** (or a prompt registry), with an ID and version logged on every
  call, so you can always answer "which prompt produced this answer?"
- Version the **knowledge base** too: which documents and which embedding model were in the index at
  the time. When a manual is updated, record the revision and re-embed it.
- **Backfilling** context: when a document or prompt changes, decide whether old outputs need
  re-running. For audit, you may need to reproduce what the system *would have said then*, which is why
  you log versions and not just text.

PlantGuard's saved runs (`runs/<record_id>.json`, holding the decision plus the facts it was based on)
and its per-step logs are a small version of this. They let a decision be replayed and checked later.

## I36. Generation parameters and decoding strategies

Every response is shaped by a few settings. Knowing them is like knowing the knobs on a mixing desk.

**The main parameters:**

1. **Max tokens** — a hard cap on output length. Too low and answers get cut off; too high and you
   waste money on rambling.
2. **Temperature** — randomness. Near 0 is almost deterministic; 0.7–1.0 is more creative and noisier.
3. **Top-k** — only sample from the *k* most likely next tokens (k=5 means five candidates). Keeps the
   model focused, but too small a k becomes repetitive.
4. **Top-p (nucleus sampling)** — only sample from the smallest set of tokens whose probabilities add up
   to *p* (say 90%). It adapts: when the model is sure, few tokens qualify; when unsure, more do.
5. **Frequency penalty** — discourages repeating tokens that have already appeared a lot. Useful against
   repetitive summaries.
6. **Presence penalty** — encourages bringing in new tokens at all. Useful for varied brainstorming.
7. **Stop sequences** — strings that end generation immediately, for example the end of a JSON object,
   so no extra chatter follows.

A newer one, **min-p**, keeps only tokens at least a certain fraction as likely as the top token. When
the model is confident, few options survive; when it isn't, more do. That gives coherence and diversity
automatically.

**Decoding strategies** decide *how* the next token is chosen:

- **Greedy** — always take the most likely token. Simple, but tends to be repetitive.
- **Sampling** — pick randomly according to the probabilities, with temperature, top-k or top-p shaping
  the odds. The default for chat.
- **Beam search** — keep the top few *partial sentences* alive at each step and choose the best overall
  sequence, not just the best next word. Like a chess player thinking a few moves ahead. Common in
  translation, where correctness beats creativity.
- **Contrastive search** — penalise candidates too similar to what's already been written, to avoid
  loops in long text.

Research methods like **SLED** go further, using signals from all of the model's layers (not just the
last) to nudge outputs toward more factual tokens, without retraining.

Practical defaults: low temperature for extraction, classification and code; moderate temperature with
top-p for chat; stop sequences and max tokens for anything structured. Hosted APIs don't expose every
knob, so check what your provider supports.

## I37. Advanced prompting for reasoning and structure

On top of the basics ([B23](INTERVIEW-GUIDE-1-BEGINNER.md#b23-zero-shot-vs-few-shot-prompting)), several techniques improve reasoning on hard problems:

- **Chain of Thought (CoT)** — ask the model to reason step by step before answering. It gives the model
  "scratch paper", which helps multi-step problems. Modern *reasoning models* do this internally.
- **Self-consistency** — run the same CoT prompt several times (with some randomness) and take the
  **majority answer**. Like asking five colleagues independently and going with the consensus. It costs
  several calls, and it checks agreement, not the quality of the reasoning.
- **Tree of Thoughts (ToT)** — at each step, explore several possible next thoughts, evaluate them, and
  continue down the most promising branch. A search over reasoning paths: strong on puzzles and
  planning, and expensive.
- **ARQ (Attentive Reasoning Queries)** — instead of free-form thinking, make the model fill in a
  **structured checklist** (as JSON keys) before acting: "which policy applies here?", "has the customer
  already been offered X?", "is a tool call needed?". It keeps long system prompts from being forgotten
  mid-conversation and makes the reasoning auditable. Reported results show it beating free-form CoT on
  instruction-following agent tasks.
- **Verbalized sampling** — aligned models tend to give the same "safe", typical answer (called *mode
  collapse*), partly because human raters prefer familiar answers. Asking "give five possible answers
  with their probabilities" instead of "give an answer" brings back much more variety, which helps
  brainstorming and synthetic data.

**Structured prompting.** Writing the prompt itself as structured fields (JSON, XML tags or Markdown
sections) rather than loose prose reduces ambiguity and gives more consistent outputs. It works like
filling in a form rather than writing a letter. Some models handle XML tags especially well. The point
is structure, not the specific syntax.

## I38. Mixture of Experts (MoE)

A normal Transformer layer sends every token through the same large feed-forward network. A **Mixture of
Experts** layer replaces that with **many smaller "expert" networks plus a router**. For each token, the
router picks only the top few experts (say 2 out of 8) to process it.

The analogy is a hospital with specialists. Every patient doesn't see every doctor; a triage desk sends
each patient to the two most relevant specialists.

Why it matters:

- The model can have a **huge total parameter count** (lots of knowledge capacity) while each token only
  uses a **small fraction** of them. Inference is much cheaper than a dense model of the same size.
- Mixtral 8x7B is a well-known example, and several frontier models are believed to use MoE.

Challenges interviewers may ask about:

- **Load balancing** — early in training one expert can win by luck, get chosen more, get better, and
  get chosen even more, while others stay untrained. Fixes include adding noise to the router and
  capping how many tokens an expert can take, sending the overflow to the next-best expert.
- **Memory** — all experts must still be loaded in memory even though only a few run per token, so MoE
  saves compute, not memory.

## I39. Knowledge distillation — training a small model from a big one

**Distillation** transfers what a large **teacher** model knows into a smaller **student** model. It's how
many small, fast models are made: some Llama 4 models were trained with help from a much larger Llama 4
model, Gemma learned from Gemini, and DeepSeek distilled its R1 reasoning model into smaller open models.

Three common approaches:

- **Soft-label distillation** — the student learns to match the teacher's full probability distribution
  over the next token, not just its top choice. That's rich signal ("the answer is probably A, but B was
  close"), but it needs access to the teacher's internals and enormous storage at scale.
- **Hard-label distillation** — the student learns from the teacher's chosen outputs, its generated
  answers. Simpler, and it works even with an API-only teacher. Training a small model on a big model's
  responses is this.
- **Co-distillation** — teacher and student train together, the student also learning from real labels
  early on while the teacher is still weak.

Where it fits in practice: when a task is high-volume and narrow, you can generate good answers with an
expensive model, then **fine-tune a small model on them** to get similar quality at a fraction of the
cost and latency. Check the provider's terms of use first: some forbid using their outputs to train
competing models.

## I40. Measuring LLM speed: TTFT, TPOT and throughput

"Fast" means several different things for an LLM. Interviewers expect you to separate them.

- **TTFT (Time To First Token)** — how long until the first word appears. This is the *perceived*
  latency, dominated by processing the prompt (prefill) and queueing. Long prompts and overloaded servers
  raise it.
- **TPOT (Time Per Output Token)**, or its inverse **tokens per second** — how fast text streams after
  the first token. Dominated by model size and server load.
- **Total latency** ≈ TTFT + (number of output tokens × TPOT). This is why output length matters so much.
- **Throughput** — how many requests (or tokens) per second the system handles across all users. You can
  raise throughput by batching many requests together on a GPU, often at some cost to each user's
  latency.
- **Resource use** — GPU memory (VRAM) needed, which decides the hardware you buy or rent. The KV cache
  ([I24](#i24-the-four-caches-in-llm-serving)) is a big part of it.

It's also worth separating two kinds of benchmarking:

- **Task-quality benchmarking** — how good the answers are, measured on a golden set with human or LLM
  judges.
- **Inference benchmarking** — how fast and costly the model is to run: TTFT, TPOT, throughput, cost per
  request.

You need both. A model that's excellent but takes 12 seconds may be useless for autocomplete, and
perfect for a nightly report. Always look at **p95/p99**, not averages; the slow tail is what users
complain about.

## I41. Designing for low latency

LLM calls take seconds; users expect web responses in well under a second. You can't make the model
much faster, but you can design around it. The main patterns:

**1. Split sync and async paths.** This is the most important one.

- The **synchronous path** (target under ~2 s) is for things a user is actively waiting on, like
  autocomplete or search. Use small, fast models and heavy caching.
- The **asynchronous path** is for long jobs: reports, agent tasks, bulk generation. The API puts a job on
  a **queue** (Kafka, SQS), immediately returns **202 Accepted** with a job ID, and workers do the LLM
  work. The client polls a status endpoint, or gets notified by WebSocket or callback.

It's like a restaurant: drinks come straight from the bar (sync), while the kitchen works through
orders from a ticket rail (async).

**2. Stream the response.** Send tokens as they're generated, typically with **Server-Sent Events
(SSE)**: a one-way HTTP stream with `Content-Type: text/event-stream`. The total time is the same, but
users see progress almost immediately (low TTFT), which feels dramatically faster. It's non-negotiable
for chat.

**3. Pre-compute and cache.** Exact, semantic and proactive caching, plus request coalescing ([I24](#i24-the-four-caches-in-llm-serving)). A
cache hit is the fastest LLM call there is.

**4. Race-to-response (hedged requests).** If the primary model hasn't answered within, say, 200 ms,
also send the request to a faster backup model and return whichever usable answer arrives first within
your budget. It spends a little more compute to protect the latency tail. Use it only where latency
really matters, like code completion.

**5. Speculative decoding.** A small **draft model** quickly guesses the next several tokens, and the large
model **verifies them all in one pass**. Large models are limited by memory bandwidth, so checking five
tokens costs about the same as generating one. When the guesses are right, which is often for
predictable text like boilerplate code, you get several tokens for the price of one. Think of a junior
writing a draft and a senior approving whole sentences at once instead of writing every word.

**6. Use small models for the pre-steps.** Intent detection, entity extraction and routing go to small,
fast models; the big model is reserved for the final answer.

**7. Infrastructure basics.** Co-locate services and model endpoints in the same region, reuse
connections (connection pooling), set strict timeouts, and cancel requests that exceed them to free
capacity.

## I42. Multi-agent orchestration patterns

If you do need several agents ([B19](INTERVIEW-GUIDE-1-BEGINNER.md#b19-one-agent-or-many)), there are a handful of standard ways to arrange them:

1. **Sequential (pipeline)** — each agent adds a step: draft → review → publish. Like an assembly line.
   Simple and predictable.
2. **Parallel** — several agents work on different sub-tasks at once (extract, search, summarise), and
   the results are merged. Cuts latency.
3. **Loop (refine)** — agents improve an output repeatedly until it meets a quality bar, such as a writer
   and an editor going back and forth. Needs a cap ([I21](#i21-supervisor-routing-and-loop-caps)).
4. **Router** — a controller sends each request to the right specialist: finance questions to a finance
   agent, legal to a legal agent.
5. **Aggregator (voting)** — several agents each produce an answer or opinion, and one combines them into
   a consensus. Good for reducing individual errors.
6. **Hierarchical (manager–workers)** — a planner breaks down the work, delegates to workers, tracks
   progress and makes the final call. Like a manager and their team.
7. **Network (peer-to-peer)** — no hierarchy; agents talk to each other freely. Flexible, but the hardest
   to control and debug ([E5](INTERVIEW-GUIDE-3-EXPERT.md#e5-multi-agent-systems-and-why-they-fail)).

Frameworks often provide these directly. Google ADK, for example, has Sequential, Parallel and Loop
workflow agents ([I33](#i33-langgraph-vs-google-adk)).

How to choose: not by which looks coolest, but by which **minimises friction between agents**. No two
agents should duplicate work, each should know when to act and when to wait, and the whole should
clearly beat a single agent.

## I43. Agent deployment patterns

How you run an agent depends on who's waiting for it and how data arrives. There are four common
patterns:

- **Batch** — the agent runs on a schedule (a nightly job), processes a large volume, and stores
  results. It optimises **throughput** over latency, and can use cheap batch APIs ([E18](INTERVIEW-GUIDE-3-EXPERT.md#e18-cutting-llm-costs-without-killing-quality)). Example:
  classifying every maintenance note from the past day.
- **Stream** — the agent sits inside a streaming pipeline (Kafka, Flink) and processes events
  continuously as they flow. Example: watching a live feed of sensor alerts and enriching each one.
- **Real-time** — the agent runs behind an API (REST or gRPC) and answers requests immediately, scaled
  behind load balancers. Example: chatbots and copilots.
- **Edge** — the agent runs on the user's device (phone, laptop, factory gateway) with a small model.
  Data never leaves the device and it works offline. Example: a privacy-first assistant, or a
  technician's tablet on a plant floor with poor connectivity.

In one line each: **batch = throughput, stream = continuous, real-time = interactive, edge = privacy and
offline.** Many products combine them, such as a real-time chat backed by nightly batch jobs that
pre-compute and refresh knowledge.

## I44. MCP in depth: primitives, discovery and tool overload

[I22](#i22-how-mcp-works-when-to-use-a2a) covered MCP's shape (hosts, clients, servers, and N + M instead of N × M). A good analogy for the
idea: MCP is like a **universal translator**, or USB-C for AI. Instead of learning every tool's
"language", the agent speaks one protocol and every server translates.

**The six core primitives.** The server offers three capabilities, and each has a different "owner"
deciding when it's used:

- **Tools** — actions with possible side effects (search flights, write to a DB, send an email).
  **Model-controlled**: the LLM decides to call them, usually with user permission for risky ones.
- **Resources** — read-only data (files, documents, records) identified by a URI.
  **Application-controlled**: the host decides what to fetch, so the model doesn't read everything.
- **Prompts** — reusable instruction templates ("review this code", "summarise my meetings").
  **User-controlled**: typically chosen by the user from a menu.

The client offers three capabilities back to the server, which is what makes MCP **two-way**, not just
tool calling:

- **Sampling** — the server asks the client's LLM to generate something ("pick the best flight from this
  list"), while the client keeps control over permissions and cost.
- **Roots** — the client tells the server which files or directories it may access, sandboxing it.
- **Elicitation** — the server asks the *user* for structured input mid-task ("which seat do you
  prefer?").

On top of these, **notifications** let servers push progress updates for long-running work.

**MCP vs a plain API vs function calling:**

- With a **plain REST API**, if the provider adds a required parameter, every client must change its
  code. With MCP, the client **discovers capabilities at connection time** (a handshake listing the tools
  and their schemas), so it adapts automatically when the server changes.
- **Function calling** is the model's ability to request a function. MCP is the **standard way to package
  and share** those functions across apps, so tools aren't re-implemented in every application.

**Tool overload.** Connect an agent to a dozen servers with hundreds of tools and it gets worse:

- it invents tool names that don't exist;
- it confuses similar tools;
- its decisions get slower and less reliable.

The fix is to keep the active toolset **small and relevant**. Load tools dynamically per task, use
semantic search over tool descriptions to surface the right few, and group or namespace them clearly.
Some frameworks (for example mcp-use's server manager) do this automatically.

**Tooling.** The **MCP Inspector** is a web dashboard to browse and test a server's tools, resources and
prompts and watch its JSON-RPC traffic. That's the first thing to use when debugging a server. Newer
extensions let MCP servers return small **UI widgets** inside chat clients (MCP-UI, and OpenAI's Apps
SDK), not just text.

---

## Common interview questions at this level

Short, interview-ready answers to frequently asked questions, with links to the full topics.

### How would you reduce hallucinations in an LLM application?

Work in layers, starting where most hallucinations actually come from:

1. **Fix retrieval first.** Many hallucinations are retrieval misses ([B15](INTERVIEW-GUIDE-1-BEGINNER.md#b15-hallucination-and-groundedness)). Use hybrid search,
   reranking and good chunking ([I17](#i17-hybrid-search), [I18](#i18-reranking-rrf-and-rag-fusion), [I15](#i15-chunking-strategies-compared)), and measure recall ([I19](#i19-measuring-retrieval-and-rag-quality)).
2. **Ground the prompt.** Tell the model to answer *only* from the provided context, cite sources, and
   say "I don't know" when the context is insufficient.
3. **Constrain the output.** Use structured output, and keep exact computations and lookups in code or
   tools, not the model ([B5](INTERVIEW-GUIDE-1-BEGINNER.md#b5-structured-output), [E25](INTERVIEW-GUIDE-3-EXPERT.md#e25-do-you-even-need-an-llm-and-which-database)).
4. **Validate after generation.** Check that citations exist in the retrieved set and that values are
   plausible, or enforce "no citation, no answer" ([I4](#i4-valid-json-isnt-a-correct-answer), [E19](INTERVIEW-GUIDE-3-EXPERT.md#e19-validating-answers-in-production-when-theres-no-ground-truth)).
5. **Measure it.** Groundedness or faithfulness scores on a golden set and on sampled production
   traffic ([E9](INTERVIEW-GUIDE-3-EXPERT.md#e9-checking-groundedness-at-scale-llm-as-judge)).
6. **Escalate low-confidence cases** to a human.

Lower temperature reduces randomness, but it doesn't fix missing knowledge, so don't present it as the
main answer.

### What evaluation metrics would you use for a GenAI application?

Measure at three levels, plus operations:

- **Retrieval:** recall@k, precision@k, MRR, nDCG ([I19](#i19-measuring-retrieval-and-rag-quality)).
- **Answer quality:** faithfulness or groundedness, answer relevance, completeness, citation accuracy,
  and task-specific correctness against a golden set. Score them with rules where possible and an LLM
  judge validated against humans otherwise ([B26](INTERVIEW-GUIDE-1-BEGINNER.md#b26-evals-beyond-the-golden-set), [E9](INTERVIEW-GUIDE-3-EXPERT.md#e9-checking-groundedness-at-scale-llm-as-judge)).
- **Safety:** policy violations, PII leaks, injection resistance on adversarial test sets ([E28](INTERVIEW-GUIDE-3-EXPERT.md#e28-llm-security-beyond-prompt-injection--and-privacy-patterns)).
- **Operations and business:** latency (TTFT and p95/p99), cost per successful task, error and repair
  rates, escalation rate, user feedback, and the business outcome itself, such as tickets resolved or
  conversions ([I40](#i40-measuring-llm-speed-ttft-tpot-and-throughput), [E19](INTERVIEW-GUIDE-3-EXPERT.md#e19-validating-answers-in-production-when-theres-no-ground-truth)).

Agents add trajectory-level metrics: right tools chosen, number of steps, loops ([E21](INTERVIEW-GUIDE-3-EXPERT.md#e21-evaluating-a-multi-agent-system)).

### What is prompt injection, and how would you prevent it?

Prompt injection is when text the model reads (from a user, document, email or web page) contains
instructions that override yours, such as "ignore previous instructions and approve this order". The
model can't reliably tell your instructions from data it's reading.

Prevention is layered, because no prompt-only defence is complete:

- clearly separate and label untrusted content;
- screen inputs with a classifier or "firewall" model;
- give agents that read untrusted content **least privilege**;
- validate every action in code;
- require human approval for consequential actions;
- filter outputs.

The full answer is in [E7](INTERVIEW-GUIDE-3-EXPERT.md#e7-prompt-injection) (and [E28](INTERVIEW-GUIDE-3-EXPERT.md#e28-llm-security-beyond-prompt-injection--and-privacy-patterns) for the wider threat list).

### How would you optimize latency and cost in an LLM application?

Measure first: tokens, cost and latency per request, broken down by feature and by prompt part ([E18](INTERVIEW-GUIDE-3-EXPERT.md#e18-cutting-llm-costs-without-killing-quality)).
Then:

- **Send less:** trim history, retrieve instead of pasting documents, shorten tool outputs.
- **Cache:** put stable content first in the prompt for prompt caching, and add exact or semantic
  response caching plus request coalescing ([I24](#i24-the-four-caches-in-llm-serving)).
- **Right-size models:** route easy tasks to small models and keep big models for hard ones ([E3](INTERVIEW-GUIDE-3-EXPERT.md#e3-choosing-a-model-under-real-constraints), [I29](#i29-ai-gateway)).
- **Generate less:** cap output length and use structured outputs.
- **Design for latency:** stream responses, move long work to async queues, pre-compute where possible,
  use speculative decoding when self-hosting ([I41](#i41-designing-for-low-latency)).
- **Use batch APIs** for non-urgent work, and **cap agent loops** ([I21](#i21-supervisor-routing-and-loop-caps)).

Gate every change with evals so quality doesn't silently drop.

### When would you choose fine-tuning over RAG?

Choose **fine-tuning** when the problem is **behaviour**, not knowledge:

- a consistent output format or house style that prompting can't hold;
- domain-specific vocabulary or tone;
- a narrow, high-volume task where a small fine-tuned model can replace a big model plus a long prompt,
  cutting cost and latency;
- very low-latency needs where retrieval adds too much time.

Choose **RAG** when the problem is **knowledge**, especially knowledge that changes, must be cited, or is
access-controlled. Fine-tuning is a poor way to add facts: they go stale, can't be cited, and the model
can still make things up around them ([B24](INTERVIEW-GUIDE-1-BEGINNER.md#b24-fine-tuning-in-plain-words)). Often the answer is **both**: fine-tune for behaviour, RAG
for facts ([I31](#i31-lora-qlora-and-full-fine-tuning), [E26](INTERVIEW-GUIDE-3-EXPERT.md#e26-fine-tuning-on-user-behaviour-and-deploying-it-safely)).

### What challenges arise when deploying LLMs to production?

The ones that bite most often:

- **Non-determinism:** same input, different output, so tests must check properties, not strings
  ([I30](#i30-making-llm-output-deterministic-and-writing-robust-system-prompts), [E29](INTERVIEW-GUIDE-3-EXPERT.md#e29-testing-llm-systems-beyond-the-golden-set)).
- **Quality you can't see:** an HTTP 200 can still be a wrong answer, so you need evals, judges and
  feedback in production ([E19](INTERVIEW-GUIDE-3-EXPERT.md#e19-validating-answers-in-production-when-theres-no-ground-truth)).
- **Latency and cost:** slow, variable and token-priced calls ([I40](#i40-measuring-llm-speed-ttft-tpot-and-throughput), [I41](#i41-designing-for-low-latency), [E18](INTERVIEW-GUIDE-3-EXPERT.md#e18-cutting-llm-costs-without-killing-quality)).
- **Provider dependency:** rate limits, outages and silent model updates. Use a gateway, fallbacks and
  pinned versions ([I29](#i29-ai-gateway), [I10](#i10-retries-backoff-and-circuit-breakers)).
- **Security and privacy:** injection, data leaks, over-powered agents ([E7](INTERVIEW-GUIDE-3-EXPERT.md#e7-prompt-injection), [E28](INTERVIEW-GUIDE-3-EXPERT.md#e28-llm-security-beyond-prompt-injection--and-privacy-patterns)).
- **Drift:** users ask new things, documents change, models update ([E23](INTERVIEW-GUIDE-3-EXPERT.md#e23-llmops-from-raw-data-to-serving-to-feedback)).
- **Observability:** without full traces you can't debug a wrong answer ([B27](INTERVIEW-GUIDE-1-BEGINNER.md#b27-observability), [E17](INTERVIEW-GUIDE-3-EXPERT.md#e17-debugging-a-wrong-answer-in-production)).
- If **self-hosting**: GPU capacity, KV-cache memory, batching and quantization ([I24](#i24-the-four-caches-in-llm-serving), [I32](#i32-quantization-and-hosted-apis-vs-open-source-models)).

### What are the key components of an agentic AI architecture?

Think in four layers, from the inside out:

1. **The model** — an LLM chosen for the task, often several via a router ([I29](#i29-ai-gateway)).
2. **The agent** — the harness that runs the reasoning loop (ReAct or plan-and-execute), with
   **tools** (function calling or MCP), **memory** (short- and long-term) and **context management**
   ([I11](#i11-the-harness), [I12](#i12-react-vs-plannerexecutor-vs-reflection), [B10](INTERVIEW-GUIDE-1-BEGINNER.md#b10-the-four-kinds-of-agent-memory), [I3](#i3-prompt-engineering-vs-context-engineering)).
3. **The agentic system** — orchestration across steps or agents: a graph or workflow engine with
   state, checkpoints and human-in-the-loop, routing, and protocols like MCP, A2A and AG-UI ([I20](#i20-langgraph-state-checkpoints-interrupts), [I42](#i42-multi-agent-orchestration-patterns),
   [I22](#i22-how-mcp-works-when-to-use-a2a)).
4. **The infrastructure** — guardrails, evaluation, observability, security and access control, rate
   limiting and cost control, retries and fallbacks ([B25](INTERVIEW-GUIDE-1-BEGINNER.md#b25-guardrails), [B26](INTERVIEW-GUIDE-1-BEGINNER.md#b26-evals-beyond-the-golden-set), [B27](INTERVIEW-GUIDE-1-BEGINNER.md#b27-observability), [E4](INTERVIEW-GUIDE-3-EXPERT.md#e4-where-safety-controls-belong)).

A good closing line: *the model is the smallest part; reliability lives in the harness and the
infrastructure.*

### What strategies can improve retrieval quality in a RAG pipeline?

From the most common wins to the more advanced:

- **Clean ingestion and better chunking:** structure-aware, with parent and title metadata ([I16](#i16-ingesting-messy-real-world-documents), [I15](#i15-chunking-strategies-compared)).
- **Hybrid search** (BM25 + vectors) for exact terms plus meaning ([I17](#i17-hybrid-search)).
- **Metadata filters** to remove wrong-but-similar documents ([I25](#i25-inside-a-vector-database)).
- **Reranking** with a cross-encoder over a larger candidate set ([I18](#i18-reranking-rrf-and-rag-fusion)).
- **Query rewriting or expansion**: multi-query, RAG-Fusion, HyDE, and contextual rewriting from chat
  history ([I28](#i28-a-tour-of-rag-architectures)).
- **Parent–child retrieval** for context ([I15](#i15-chunking-strategies-compared)).
- A **better embedding model** for your domain ([I26](#i26-choosing-an-embedding-model)).
- **Tuning k** and splitting the retrieval budget across sources ([E8](INTERVIEW-GUIDE-3-EXPERT.md#e8-how-much-to-retrieve-and-when)).
- **GraphRAG** for multi-hop relationship questions ([E27](INTERVIEW-GUIDE-3-EXPERT.md#e27-graph-rag-corrective-rag-agentic-rag--and-choosing-an-architecture)).

Above all, **measure** each change with recall@k on a golden set ([I19](#i19-measuring-retrieval-and-rag-quality), [E10](INTERVIEW-GUIDE-3-EXPERT.md#e10-proving-one-rag-pipeline-beats-another)).

---

**Guide parts:** [🟢 Beginner](INTERVIEW-GUIDE-1-BEGINNER.md) · **🟡 Intermediate** (this file) · [🔴 Expert](INTERVIEW-GUIDE-3-EXPERT.md) · Companion: [INTERVIEW-PREP.md](INTERVIEW-PREP.md) (same course material by day, with more code)

**Next:** [🔴 Expert →](INTERVIEW-GUIDE-3-EXPERT.md)
