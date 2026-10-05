# Agentic AI Interview Guide — 🟢 Beginner

**Guide parts:** **🟢 Beginner** (this file) · [🟡 Intermediate](INTERVIEW-GUIDE-2-INTERMEDIATE.md) · [🔴 Expert](INTERVIEW-GUIDE-3-EXPERT.md) · Companion: [INTERVIEW-PREP.md](INTERVIEW-PREP.md) (same course material by day, with more code)

This is a three-part interview guide for agentic AI and LLM engineering, organised by how deep
interviewers usually go. It's written to help you **understand** each idea well enough to explain it in
your own words, with simple examples and, where it helps, a technical analogy.

- 🟢 **Beginner** (this file): "what is it and why does it exist?"
- 🟡 **Intermediate**: "how does it work, and what goes wrong?"
- 🔴 **Expert**: "how would you design it, prove it works, and keep it safe?" It includes four full
  system-design case studies.

Interviewers often start at 🟢 and keep digging into the same topic until you run out of depth. When you
read a topic here, the links take you to its deeper neighbours in the other parts.

**What it covers.** Topics are merged from several sources, so each idea appears once, in the place
where it fits best:

- the IITH Applied AI course decks (Days 1–3);
- interview infographics and posts (caches, cost, RAG architectures, vector DBs, guardrails, LLMOps,
  fine-tuning, data engineering and SQL);
- *System Design for the LLM Era* (Sampriti Mitra): production patterns and four case studies;
- *AI Engineering: System Design Patterns for LLMs, RAG and Agents* (DailyDoseofDS);
- the article *AI-SDLC: Engineering Intelligence, Not Just Software*.

**Numbering.** **B / I / E** are AI topics at each level; **D** topics are a data-engineering and SQL
track at the end of each part. PlantGuard, our maintenance copilot from the capstone, appears as an
example where it fits; elsewhere the examples are simple hypothetical ones.

---

## Topics in this part

| # | Topic | Source |
|---|---|---|
| [B1](#b1-tokens-and-how-a-model-writes-an-answer) | Tokens and how a model writes an answer | Day 1 · S1 + books |
| [B2](#b2-statelessness--how-chat-remembers) | Statelessness — how chat "remembers" | Day 1 · S1 |
| [B3](#b3-the-context-window) | The context window | Day 1 · S1 |
| [B4](#b4-what-goes-into-a-prompt) | What goes into a prompt | Day 1 · S1 + books |
| [B5](#b5-structured-output) | Structured output | Day 1 · S1 |
| [B6](#b6-what-an-ai-agent-is) | What an AI agent is | Day 1 · S1 + books |
| [B7](#b7-training-cutoff--why-models-need-tools) | Training cutoff — why models need tools | Day 1 · S2 |
| [B8](#b8-tools--function-calling) | Tools / function calling | Day 1 · S2 |
| [B9](#b9-the-react-loop) | The ReAct loop | Day 1 · S2 + books |
| [B10](#b10-the-four-kinds-of-agent-memory) | The four kinds of agent memory | Day 2 · S1 + books |
| [B11](#b11-rag--retrieval-augmented-generation) | RAG — Retrieval-Augmented Generation | Day 2 · S2 |
| [B12](#b12-embeddings-and-vector-databases) | Embeddings and vector databases | Day 2 · S2 |
| [B13](#b13-chunking--why-split-documents) | Chunking — why split documents | Day 2 · S2 |
| [B14](#b14-keyword-vs-semantic-search) | Keyword vs semantic search | Day 2 · S2 |
| [B15](#b15-hallucination-and-groundedness) | Hallucination and groundedness | Day 2 · S2 + books |
| [B16](#b16-golden-sets) | Golden sets | Day 2 · S2 |
| [B17](#b17-chains-vs-graphs) | Chains vs graphs | Day 3 · S1 |
| [B18](#b18-checkpoints-and-human-in-the-loop) | Checkpoints and human-in-the-loop | Day 3 · S1 |
| [B19](#b19-one-agent-or-many) | One agent or many? | Day 3 · S1 |
| [B20](#b20-mcp-and-a2a-in-one-picture) | MCP and A2A in one picture | Day 3 · S2 |
| [B21](#b21-attention-and-positional-encoding) | Attention and positional encoding | Extra · LLM fundamentals Qs |
| [B22](#b22-why-tokens-decide-your-ai-bill) | Why tokens decide your AI bill | Extra · LLM post · 9 AI concepts + books |
| [B23](#b23-zero-shot-vs-few-shot-prompting) | Zero-shot vs few-shot prompting | Extra · LLM fundamentals Qs + books |
| [B24](#b24-fine-tuning-in-plain-words) | Fine-tuning, in plain words | Extra · LLM fundamentals Qs + books |
| [B25](#b25-guardrails) | Guardrails | Extra · 9 AI concepts |
| [B26](#b26-evals-beyond-the-golden-set) | Evals beyond the golden set | Extra · 9 AI concepts |
| [B27](#b27-observability) | Observability | Extra · 9 AI concepts |
| [B28](#b28-agent-skills--and-how-mcp-rag-and-skills-differ) | Agent Skills — and how MCP, RAG and Skills differ | Extra · MCP vs RAG vs Skills + books |
| [B29](#b29-ai-vs-ml-vs-deep-learning-vs-genai-llms-vs-slms) | AI vs ML vs deep learning vs GenAI; LLMs vs SLMs | Book · System Design for the LLM Era |
| [B30](#b30-how-an-llm-is-built-and-trained) | How an LLM is built and trained | Book · AI Engineering (DailyDoseofDS) |
| [D1](#d1-etl-vs-elt) | ETL vs ELT | Extra · Data engineer Qs |
| [D2](#d2-data-warehouse-vs-data-lake-and-lakehouse) | Data warehouse vs data lake (and lakehouse) | Extra · Data engineer Qs |
| [D3](#d3-star-schema-vs-snowflake-schema) | Star schema vs snowflake schema | Extra · Data engineer Qs |
| [D4](#d4-window-functions--the-inventory-stock-level-question) | Window functions — the inventory stock-level question | Extra · SQL inventory post |

---

# 🟢 Beginner

These are the foundations. Interviewers use them to check that your mental model is right. A wrong
mental model here ("the model remembers me", "the model calls the API") is a red flag even for senior
roles.

## B1. Tokens and how a model writes an answer

A language model doesn't read words the way we do. Text is first cut into **tokens**: small pieces,
often part of a word (in English, a token is roughly four characters). Each token becomes a number, and
the model works only with those numbers.

The model then writes its answer **one token at a time**. At each step it looks at everything so far
and predicts which token is most likely to come next, picks one, adds it, and repeats. That's all
generation is: very good next-token prediction, over and over.

This explains a lot of behaviour that surprises people. The model has no separate "look up the fact"
step and no built-in "check I'm right" step. It produces what *sounds* like a good continuation. So if
you ask it for a sensor value, it may happily answer "around 28 bar, which seems a bit high". That's a
fluent sentence, but not a number your code can use, and possibly not even correct.

In an interview, the simple version is: *"The model predicts the next token based on everything before
it, repeatedly. It doesn't look things up or verify them, which is why answers can be fluent but wrong."*
If they push, mention that tokens also drive cost and limits: you pay per token and the window is
measured in tokens.

Under the hood, "predict the next token" is **conditional probability**: given everything so far, the
model scores every token in its vocabulary, turns the scores into probabilities (a *softmax*), and picks
one. If it always took the single most likely token, the text would be dull and repetitive, so it
usually **samples**, and **temperature** controls how adventurous that sampling is. Low temperature
sticks to the safest choice; high temperature spreads the chances out. [I36](INTERVIEW-GUIDE-2-INTERMEDIATE.md#i36-generation-parameters-and-decoding-strategies) covers the full set of these
knobs.

## B2. Statelessness — how chat "remembers"

This is probably the most important runtime fact about LLMs: **the model has no memory between calls.**
Each API call starts completely fresh.

So how does ChatGPT remember what you said ten messages ago? The *application* keeps the whole
conversation as a list of messages, and on every new turn it sends the **entire list** again: system
instructions, your earlier messages, the model's earlier replies, and your new message. The model reads
it all from scratch and answers. The "memory" lives in the app, not in the model.

Think of it like talking to someone with no short-term memory who is handed a full transcript before
every reply. They seem to remember, but only because you keep handing them the transcript.

Two consequences come up in interviews:

- **Cost grows with the conversation.** You pay for the whole history on every call, so long chats get
  expensive.
- **Memory is your job.** If you want the system to remember something across sessions, you must store
  it and put it back into the prompt later. That's what the memory topics ([B10](#b10-the-four-kinds-of-agent-memory), [I13](INTERVIEW-GUIDE-2-INTERMEDIATE.md#i13-long-conversations-truncation-summaries-long-term-memory)) are about.

In PlantGuard, the agent loop keeps a `messages` list and appends every tool result to it, then resends
the whole list each step. That's statelessness in practice.

## B3. The context window

The **context window** is the maximum number of tokens the model can look at in one call. Everything
has to fit in it together: the system prompt, conversation history, retrieved documents, tool results,
and space for the model's answer.

It's like a desk of fixed size. You can only spread out so many papers at once; if you want to add
more, something has to come off.

Modern windows are huge (hundreds of thousands, even a million tokens), so beginners often assume the
problem is solved. It isn't. Long prompts are slower, cost more, and the model gets *worse* at using
information as the window fills. That's the 🟡 topic [I2](INTERVIEW-GUIDE-2-INTERMEDIATE.md#i2-context-rot--why-a-bigger-window-isnt-the-fix). For a beginner answer it's enough to say the
window is a hard limit on what the model can see per call, and that filling it isn't free.

## B4. What goes into a prompt

A useful way to think about a prompt is in four parts:

1. **Instruction** — what you want done ("triage this maintenance event").
2. **Context** — background that steers the answer (facts about the machine, relevant manual sections).
3. **Input data** — the thing to work on (the alarm and the operator's note).
4. **Output format** — what shape the answer should take ("return JSON with these fields").

Beginners usually focus on the instruction and keep rewording it. In real systems the instruction is
the easy part. What decides the quality of the answer is mostly the **context**: did you give the model
the right facts, and only the right facts? That idea grows into "context engineering" ([I3](INTERVIEW-GUIDE-2-INTERMEDIATE.md#i3-prompt-engineering-vs-context-engineering)).

Many guides add a fifth part, the **persona** or **role**: "You are a senior reliability engineer
explaining this to a new technician." A role changes tone, vocabulary and what the model pays
attention to, much like telling a colleague which hat to wear before they review your work.

## B5. Structured output

Models are trained to write human-like text. Software needs typed data: a number, a date, one of a fixed
set of values. If the model says "around 450" and your code does `float(...)`, it breaks.

**Structured output** means asking the model to answer in a fixed format, usually JSON that matches a
schema you define. For example: `priority` must be one of `P1`, `P2`, `P3`, `P4`; `estimated_hours`
must be a number; `citations` must be a list of strings. Most providers can enforce the shape directly.

Two points worth making in an interview:

- It turns a "chat" into something your program can reliably use.
- It guarantees the **shape**, not the **truth**. Valid JSON can still contain a wrong priority or a
  made-up citation. You still have to check values in code (that's [I4](INTERVIEW-GUIDE-2-INTERMEDIATE.md#i4-valid-json-isnt-a-correct-answer)).

In PlantGuard, the LLM's answer is a Pydantic model (`LLMDecision`), so the code downstream always gets
the same fields, already type-checked.

## B6. What an AI agent is

The course definition: an agent **perceives** its environment, **reasons** about it, and **takes
actions** toward a goal a human gave it, on its own, in a loop, and ideally learns over time.

The difference from a chatbot is who decides the next step. A chatbot answers your question and stops.
An agent decides what it needs to do, uses tools to do it, looks at what happened, and continues until
the goal is met (or it hits a limit).

A simple formula that works well in interviews: **agent = model + harness + tools**. The model does the
reasoning; the tools let it touch the real world; the harness is the code that runs the loop, executes
tools, and enforces limits.

Example: given an alarm, a maintenance agent decides to look at recent sensor readings, then checks
whether spare parts are in stock, then reads the right manual section, and only then recommends a fix.
Nobody told it that exact sequence; it chose it.

A good thing to add: a single LLM call is **not** an agent. It's a building block that agents use.

A handy analogy to separate three terms people mix up:

- the **LLM is the brain** — it can reason, but only with what it already knows;
- **RAG is feeding that brain fresh information** — it reads relevant pages before answering;
- the **agent is the decision-maker** — it uses the brain and the tools to plan, act and check its work.

Agency isn't on/off; it's a dial. A useful five-step scale:

1. **Basic responder** — a human controls the flow; the LLM just answers.
2. **Router** — the human defines the paths; the LLM picks which one to take.
3. **Tool calling** — the human defines the tools; the LLM decides when to use them and with what
   arguments.
4. **Multi-agent** — a manager agent coordinates sub-agents and decides the next step.
5. **Autonomous** — the LLM writes and runs new code or plans on its own.

Each step up gives the model more control over *what happens next*, so each step needs stronger
limits and checks. Most production systems sit at level 2 or 3, on purpose.

Good agents are also built from a few recurring ingredients: a clear **role**, a narrow **focus** (one
job done well beats five done badly), the **right tools** (more tools isn't better), **cooperation**
with other agents where needed, **guardrails**, and **memory**.

## B7. Training cutoff — why models need tools

A model's knowledge comes from its training data, which stops at some date: the **training cutoff**.
After that, it knows nothing new. It also has no live connection to anything: it can't check today's
weather, read your database, or run code. All it can do is produce text.

So for anything live or private (current stock levels, today's sensor readings, your company's
documents), the model must be *given* the information, either by putting it in the prompt or by letting
it ask for it through a **tool**.

This is why "can't we fine-tune it on our data?" is usually the wrong answer for live facts.
Fine-tuning bakes in a snapshot that goes stale the next day; a tool fetches the current value every
time.

## B8. Tools / function calling

A **tool** is a function in your code that the model is allowed to ask for. You describe each tool to
the model with three things: a name, a plain-language description, and a schema of its parameters.

When the model decides it needs a tool, it doesn't run anything. It replies with a structured
**request**: "please call `check_spare_parts` with `asset_tag = VPW-CHILLER-01`". Your application reads
that request, decides whether to allow it, runs the function, and sends the result back to the model as
a new message. The model then continues with that information.

The key sentence for interviews: **the model requests, your code decides and executes.** That's
also the basis of safety. Since your code sits between the model and the real world, that's where you
put permissions, checks and limits.

## B9. The ReAct loop

**ReAct** stands for *Reason + Act*. It's the basic loop under most agents:

1. **Think** — the model reasons about what it still needs.
2. **Act** — it calls a tool.
3. **Observe** — it reads the tool's result.
4. Repeat, until it decides it can give a final answer.

Example: *"I need recent readings"* → calls `get_sensor_history` → sees the readings → *"the
temperature is rising, let me check the manual for this fault"* → calls `search_manuals` → reads the
section → gives a recommendation.

The one thing you must mention: **a step cap.** The model decides when it's done, and sometimes it never
decides, or keeps calling the same tool. The harness must stop the loop after N steps. In PlantGuard
that's `AGENT_MAX_STEPS = 8`; after that, the agent is forced to give its best structured answer.

If you build a ReAct loop by hand (a good exercise), the classic first version asks the model to write
lines like `Action: lookup_population: India` and parses them with a regex. It works in a demo but is
brittle: an extra space or a slightly different label breaks the parser, and the model may invent a tool
that doesn't exist. Production versions use the provider's native **function calling** (structured tool
requests) instead of parsing free text, and validate every requested tool name and argument.

## B10. The four kinds of agent memory

The course uses the CoALA framework, which borrows from how human memory is described:

- **Working memory** — whatever is in the context window right now. It disappears after the call.
- **Episodic memory** — specific past events with a time: *"CHILLER-01 tripped on 2 July after a
  condenser fault."*
- **Semantic memory** — general facts that stay true: *"CHILLER-01 is a class-B asset and trips often in
  summer."*
- **Procedural memory** — how to do things, rules and skills: *"for chiller trips, check condenser
  water flow first."*

Plain chat history is only working memory. It feels like memory, but it's gone when the session ends.
A useful agent needs the long-term kinds too, stored outside the model and brought back into the
prompt when relevant.

A common beginner mistake is to say "memory = a vector database". A vector DB is one way to store and
search memory; it isn't the concept itself.

Some frameworks add a few practical sub-types on top: **entity memory** (facts about specific things,
such as a customer or a machine), **user memory** (preferences of this user) and **contextual memory**
(what's relevant right now). They're all ways of organising the same long-term store.

There's also a neat way to see how memory relates to RAG:

- **RAG** is *read-only, one-shot*: fetch once, answer once.
- **Agentic RAG** is *read-only, on demand*: the agent decides when and where to search.
- **Agent memory** is *read-write*: the agent also **writes** what it learned, so next time it knows.

That last step is what lets an agent improve across sessions without retraining the model. Memory is a
system-design problem, not a property of the model.

## B11. RAG — Retrieval-Augmented Generation

Models don't know your private documents, and retraining them every time a document changes isn't
practical. **RAG** solves this at question time:

1. **Beforehand:** split your documents into pieces and index them for search.
2. **At question time:** search for the pieces most relevant to the question.
3. **Put those pieces in the prompt**, and ask the model to answer *using them*, ideally citing which
   piece supports which claim.

It's an open-book exam: the model doesn't need to have memorised the manual, it just needs the right
pages in front of it.

Why RAG rather than fine-tuning? Documents can change instantly (just re-index), answers can cite
sources, and private data stays in your store rather than inside model weights. Fine-tuning is
better for teaching a *style* or *behaviour*, not for keeping facts current.

PlantGuard uses RAG over 24 equipment manuals and SOPs: for a chiller alarm it fetches the chiller
manual's fault section and the plant's safety procedure.

## B12. Embeddings and vector databases

How do you find "relevant" text when the words differ? "Machine cut out" and "unit tripped" mean the
same thing but share no words.

An **embedding model** turns a piece of text into a long list of numbers (a vector) such that texts with
similar *meaning* end up with similar numbers, close together in that space. A **vector database**
(Qdrant, Pinecone, pgvector, and so on) stores these vectors and can very quickly find the ones closest
to a given vector.

So at question time you embed the question with the **same** embedding model, ask the database for the
nearest vectors, and get back the most similar chunks.

People use three overlapping terms: **vector search** is the mechanism (nearest neighbours in number
space), **dense** describes the vectors (every position has a value), and **semantic search** is the
goal (matching meaning). They usually refer to the same thing.

In PlantGuard each manual section becomes a vector of 3,072 numbers stored in Qdrant.

## B13. Chunking — why split documents

You don't embed whole manuals as one vector. A 40-page manual covers dozens of topics; its single
vector would be a blurry average of all of them, and retrieving it would dump 40 pages into the prompt.

So documents are split into **chunks**, smaller pieces that each cover roughly one idea. Retrieval can
then return just the few relevant chunks, keeping the prompt small and focused.

The hard part is *where* to cut. Cut in the middle of a fault table and neither half makes sense.
PlantGuard chunks by manual section, so each fault table or procedure stays whole. Other strategies are
compared in [I15](INTERVIEW-GUIDE-2-INTERMEDIATE.md#i15-chunking-strategies-compared).

## B14. Keyword vs semantic search

There are two basic ways to search text:

- **Keyword (sparse) search**, the classic algorithm being **BM25**: matches the actual words. It's
  excellent for exact things like part numbers, error codes, names and acronyms. It doesn't understand
  synonyms: "cut out" won't find "tripped".
- **Semantic (dense) search** using embeddings: matches meaning. It handles paraphrase well but is weak
  on exact identifiers. To an embedding model, `VPW-P-00043` and `VPW-P-00034` look almost the same.

Neither is better overall; they fail in opposite places. That's why production systems often combine
them (hybrid search, [I17](INTERVIEW-GUIDE-2-INTERMEDIATE.md#i17-hybrid-search)). A nice interview example: *"if a technician searches a part number, I want
keyword search; if they describe a symptom in their own words, I want semantic search."*

## B15. Hallucination and groundedness

A **hallucination** is a confident claim that isn't supported by any real source. An answer is
**grounded** when everything it claims can be traced back to the documents it was given.

A point that shows real understanding: in RAG systems, many "hallucinations" are actually **retrieval
failures**. The right document was never retrieved, so the model filled the gap with something
plausible. Before blaming the model or upgrading it, check whether retrieval found the right material.

Example from the course: the model correctly quotes a general procedure but misses that a specific
machine has an exception, because the exception lived in a different document that wasn't retrieved.

It helps to name the three classic failure types in LLM output:

- **Hallucination** — confident, plausible, false. Fix: ground the answer with retrieved sources.
- **Knowledge cutoff** — correct once, out of date now. Fix: give current data through RAG or tools.
- **Bias** — patterns absorbed from human training text. It's the hardest to remove. You manage it
  with careful data, guardrails, evaluation on sensitive cases, and human review.

## B16. Golden sets

A **golden set** is a small, carefully built list of realistic questions where a human has written down
the correct answer, and often which documents must be used. Every time you change something (prompt,
model, chunking), you run the system on the whole set and compare scores.

Without one, you end up judging changes by trying a few examples by hand, which hides regressions: a
change fixes the case you looked at and quietly breaks three others.

It doesn't need to be big to be valuable. Twenty to fifty good cases, drawn from real usage and real
failures, already tell you far more than demos. PlantGuard has a golden set listing which documents
each scenario must cite; retrieval currently finds them 86% of the time.

## B17. Chains vs graphs

A **chain** runs fixed steps in a fixed order: A → B → C, every time. A **graph** lets the workflow
branch, merge and loop, choosing the next step based on what has happened.

Three words to know for graph frameworks like LangGraph:

- **State** — the shared record of everything known so far (the event, facts gathered, the draft
  decision...).
- **Nodes** — steps that read the state and update it.
- **Edges** — rules for which node runs next, possibly depending on the state ("if safety-critical, go
  to human approval; otherwise go to logging").

The beginner takeaway: graphs are for workflows where the path genuinely varies. If every run goes
through the same steps, a simple chain of functions is easier to build and debug.

## B18. Checkpoints and human-in-the-loop

**Checkpointing** means saving the workflow's state after each step. If something crashes at step 7,
you resume from step 7 instead of redoing everything, which matters when earlier steps were slow or
cost money.

**Human-in-the-loop (HITL)** means the workflow deliberately pauses at a chosen point, waits for a
person to review or approve, and then continues. You put it before risky or irreversible actions:
issuing a permit-to-work, ordering an expensive part, shutting a machine down.

The two are connected: to pause for a human (who may answer hours later) and resume, you must have
saved the state somewhere. So **the checkpointer comes first**; HITL is built on top of it.

Note that you don't want a human at every step; that defeats the point of automation. You want them at
the few points where a mistake would be costly.

## B19. One agent or many?

It's tempting to design a team of agents: a diagnosis agent, a parts agent, a scheduling agent. The
course's advice is to **start with one agent**. A single agent can use many tools; having many tools
doesn't mean you need many agents.

Split into multiple agents only when there's a real reason:

- **Different roles or permissions** — e.g. only a procurement agent should be able to spend money.
- **An independent check** — a reviewer that didn't produce the answer can catch its mistakes.
- **Truly parallel work** — independent sub-tasks that can run at the same time.

Every extra agent adds handoffs, where information gets lost, plus extra cost and new ways to fail.
Interviewers like hearing that you'd prove a single agent isn't enough before adding more.

## B20. MCP and A2A in one picture

Both are open protocols, but they connect different things.

- **MCP (Model Context Protocol)** connects an agent to **tools and data**. A team wraps a system (say,
  the inventory database) as an MCP server once, and any MCP-compatible agent can use it. Without
  standards, every agent needs custom code for every tool.
- **A2A (Agent-to-Agent)** connects an agent to **another agent**: one with its own reasoning, perhaps
  built by another team or company. Instead of calling a function, you hand over a task.

A memorable image: MCP is vertical (agent reaching down to its tools); A2A is horizontal (agent talking
sideways to a peer). They complement each other rather than compete. Details are in [I22](INTERVIEW-GUIDE-2-INTERMEDIATE.md#i22-how-mcp-works-when-to-use-a2a).

## B21. Attention and positional encoding

When a model reads a sentence, each word's meaning depends on the others. In *"the pump tripped
because its bearing overheated"*, the word "its" only makes sense if the model links it back to
"pump". **Attention** is the mechanism that does this linking.

Here's the simple picture. For every token, the model builds three small vectors:

- a **query** — "what am I looking for?"
- a **key** — "what do I contain?"
- a **value** — "what information do I pass on if someone attends to me?"

Each token compares its query with every other token's key to get a relevance score, then takes a
weighted mix of their values. "its" ends up pulling in information from "pump". Models do this many
times in parallel ("multi-head" attention) and across many layers, each picking up different kinds of
relationships.

Attention on its own has a blind spot: it doesn't know word **order**. "Dog bites man" and "man bites
dog" would look the same. **Positional encoding** fixes that by adding information about each token's
position. Older models added fixed sine/cosine patterns; many modern models use **RoPE** (rotary
position embeddings), which encodes the *relative* distance between tokens and copes better with long
inputs.

Why interviewers ask this: it explains two practical facts. Attention compares every token with every
other token, so cost grows quickly with prompt length ([I1](INTERVIEW-GUIDE-2-INTERMEDIATE.md#i1-why-long-prompts-are-slow-and-expensive)). And how positions are encoded affects how
well a model handles very long context ([I2](INTERVIEW-GUIDE-2-INTERMEDIATE.md#i2-context-rot--why-a-bigger-window-isnt-the-fix)).

## B22. Why tokens decide your AI bill

A very common real-world question is *"why did our AI bill get so high?"* The answer almost always
comes down to tokens.

You pay for **input tokens** (everything you send) and **output tokens** (everything the model writes),
and output tokens usually cost several times more than input tokens. A single request quietly includes
far more than the user's question:

- the system prompt (often 1,000–3,000 tokens);
- the whole conversation history, resent every turn ([B2](#b2-statelessness--how-chat-remembers));
- retrieved documents (RAG chunks);
- tool definitions and tool results;
- the model's answer, including any reasoning tokens.

So a "short question" can easily be 10,000 tokens. Multiply by thousands of users and dozens of turns,
and it adds up fast. A classic mistake is sending an entire PDF with every question instead of
retrieving the three relevant chunks.

Tokenization also has some quirks worth knowing:

- **Numbers and IDs split oddly** (`VPW-CHILLER-01` may be six or seven tokens), which is one reason
  models are shaky at arithmetic and exact codes.
- **Non-English text** often uses more tokens for the same meaning, so it costs more.
- Models see tokens, not letters, which is why "how many r's in strawberry?" used to trip them up.

The fixes (trimming history, retrieving instead of pasting, caching, smaller models) are covered in
[I24](INTERVIEW-GUIDE-2-INTERMEDIATE.md#i24-the-four-caches-in-llm-serving) and [E18](INTERVIEW-GUIDE-3-EXPERT.md#e18-cutting-llm-costs-without-killing-quality). The beginner point is: **cost scales with tokens, and most tokens aren't the user's
question.**

There's also a speed angle. A model reads the input tokens **in parallel** (all at once) but writes
output tokens **one after another**. So 500 extra output tokens hurt latency far more than 500 extra
input tokens. If you need a fast reply, cap and shorten the output first.

## B23. Zero-shot vs few-shot prompting

**Zero-shot** means you just describe the task: *"Classify this maintenance note as mechanical,
electrical or process."* The model relies on what it learned in training.

**Few-shot** means you also show a few worked examples in the prompt:

> Note: "motor humming, breaker tripped twice" → electrical
> Note: "seal leaking oil near shaft" → mechanical
> Note: "feed pressure keeps drifting low" → process
> Note: "bearing temperature climbing" → ?

Examples teach the format, the tone and the edge cases far better than a description can.

Which works better where?

- **Zero-shot** is fine for common, well-defined tasks (summarise, translate, extract obvious fields)
  with modern strong models. It's cheaper, because the prompt is shorter.
- **Few-shot** helps when the task has a specific format, house style or tricky boundaries ("a loose
  wire is electrical, even if the symptom is mechanical"), or with smaller models.

Two practical tips: choose examples that cover the **hard cases**, not just easy ones; and vary them,
because models copy patterns, so if all your examples end with "electrical" you may bias the answer.
Examples also cost tokens on every call, so drop them if zero-shot measures just as well on your eval.

Beyond examples, a few simple prompting habits make a big difference:

- **Enrich the context.** "Fix this bug" is weak; "here is the error, the stack trace, the table schema
  and the function, find why the object is null" is strong.
- **Give a role** (see [B4](#b4-what-goes-into-a-prompt)).
- **State what not to do** (negative prompting): "do not invent API names", "do not run destructive
  commands; print a dry-run list and ask for confirmation".
- **Ask for step-by-step reasoning** (chain of thought) on multi-step problems: "first extract the IPs,
  then remove duplicates, then count".

[I37](INTERVIEW-GUIDE-2-INTERMEDIATE.md#i37-advanced-prompting-for-reasoning-and-structure) covers the more advanced reasoning techniques built on top of these.

## B24. Fine-tuning, in plain words

**Fine-tuning** means taking a pre-trained model and training it a bit more on your own examples, so
its weights change. It's different from prompting (which only changes the input) and from RAG (which
gives the model documents at question time).

A simple way to choose between them:

- **Prompting** — try this first. It's fast and free to change.
- **RAG** — when the model needs **knowledge** it doesn't have, especially knowledge that changes
  (manuals, policies, stock levels).
- **Fine-tuning** — when you need to change **behaviour**: a consistent style or format, a narrow
  specialised task done cheaply by a small model, or a very long prompt you'd like to "bake in" so you
  stop paying for it on every call.

A useful one-liner: **RAG teaches the model what to know; fine-tuning teaches it how to behave.**

Fine-tuning is a poor way to add facts. They go stale, you can't cite them, and the model may still
make things up around them. It also needs good training data, an evaluation set, and re-training when
the base model changes. The techniques (LoRA, QLoRA, full fine-tuning) are covered in [I31](INTERVIEW-GUIDE-2-INTERMEDIATE.md#i31-lora-qlora-and-full-fine-tuning).

A simple 2×2 helps decide. Ask two questions: *does the task need knowledge the model doesn't have?*
and *does the model need to behave differently (style, vocabulary, format)?*

| | Behaviour is fine | Behaviour must change |
|---|---|---|
| **No extra knowledge needed** | prompt engineering | fine-tuning |
| **Extra knowledge needed** | RAG | RAG + fine-tuning (hybrid) |

Example: summarising meetings full of internal jargon might need fine-tuning (vocabulary and style);
answering questions about this month's policies needs RAG.

## B25. Guardrails

**Guardrails** are checks wrapped around the model, on the way in and on the way out. A simple picture
is a filter on each side:

**Input guardrails** check what goes *into* the model:

- detect and mask personal data (PII) such as phone numbers, emails or ID numbers;
- detect prompt-injection or jailbreak attempts ([E7](INTERVIEW-GUIDE-3-EXPERT.md#e7-prompt-injection));
- keep the conversation on topic (a maintenance assistant shouldn't write poems).

**Output guardrails** check what comes *out* before anyone sees it or acts on it:

- block toxic, harmful or policy-breaking content;
- catch leaked personal or confidential data;
- check format and facts: valid schema, citations that exist, values within physical limits.

They can be simple rules (regexes, allow-lists), small classifier models (for toxicity, PII or
injection), or an LLM acting as a checker. Libraries such as Guardrails AI, NVIDIA NeMo Guardrails and
Llama Guard package common ones.

In PlantGuard, an input-side guard makes sure fields like `ground_truth` never reach the prompt, and
output-side guards reject invented citations and impossible readings before routing.

One thing to say in an interview: guardrails are a **layer**, not a guarantee. They reduce risk, but the
real safety comes from also limiting what the system *can do* ([E4](INTERVIEW-GUIDE-3-EXPERT.md#e4-where-safety-controls-belong)).

## B26. Evals beyond the golden set

An **eval** is a repeatable test of how well your AI system performs. The golden set ([B16](#b16-golden-sets)) is the most
common kind, but the general shape is always the same:

1. **Test cases** — inputs, ideally with expected answers or at least clear criteria.
2. **Run the system** and collect outputs.
3. **Score** each output: with exact checks (does the JSON parse, is the priority correct?), with rules
   (is every citation real?), or with an **LLM judge** following a rubric (is this answer relevant and
   complete?).
4. **Aggregate into metrics** — accuracy, safety violations, task success rate, cost, latency.

The saying on the infographic sums it up: *what you can't measure, you can't ship.* Without evals,
every prompt change is a gamble.

Different evals answer different questions:

- **Offline evals** run before release, on a fixed set, to catch regressions. Think of them as unit
  tests for AI.
- **Online evals** run on live traffic: judge sampled responses, track user feedback.
- **Component evals** test one piece (retrieval, a single agent); **end-to-end evals** test the whole
  task.

A beginner-level answer that impresses: *"I'd start with 30 real examples and simple checks, run it on
every change, and grow it from real failures."*

## B27. Observability

**Observability** means being able to see what your AI system actually did, so that when something goes
wrong you can find out why. The infographic's line is a good one: *you can't fix what you can't see.*

For AI systems there are four main signals:

- **Traces** — the full path of one request: each step, LLM call, tool call and retrieval, with timing.
  Think of it as a timeline of the run.
- **Logs** — detailed records: the prompt sent, the response received, errors.
- **Metrics** — numbers over time: latency, tokens, cost per request, error rate, cache hit rate.
- **Feedback** — signals from users (thumbs up or down, edits, escalations) or from judges.

Why AI needs this more than normal software: the same input can produce different outputs, and failures
are often *quiet*. Nothing crashes; the answer is just wrong. Without a trace showing which chunks were
retrieved and what the model saw, you can't tell a retrieval bug from a model mistake ([E17](INTERVIEW-GUIDE-3-EXPERT.md#e17-debugging-a-wrong-answer-in-production)).

Common tools are LangFuse, LangSmith and Arize Phoenix, often built on **OpenTelemetry**. PlantGuard logs
each step today (including which documents were cited), and LangFuse tracing is planned for the
production milestone.

## B28. Agent Skills — and how MCP, RAG and Skills differ

**Agent Skills** are a newer idea, popularised by Anthropic and now supported by several agent tools.
A skill is a **folder of know-how** that an agent can load when it needs it:

- a `SKILL.md` file with a name, a short description and step-by-step instructions;
- optionally scripts, templates or reference files the instructions can use.

The clever part is **progressive disclosure**. At the start, the agent only sees each skill's name and
one-line description, which is cheap. When a task matches ("create the monthly maintenance report"),
it loads that skill's full instructions, and only then any scripts or files. So you can give an agent
hundreds of skills without stuffing them all into the context window.

People often mix up three ideas that solve different problems:

| | What it gives the agent | Think of it as | Example |
|---|---|---|---|
| **RAG** | **knowledge** — relevant text pulled into the prompt | a library | "what does the chiller manual say about a high-pressure trip?" |
| **MCP** | **access** — tools and live data in other systems | hands | "check stock in the inventory system" |
| **Skills** | **procedure** — how to do a particular kind of task | a playbook | "how we write and format the monthly downtime report" |

They combine naturally. A "report" skill might tell the agent to fetch data through an MCP tool, look
up definitions with RAG, then run a script to build the chart.

A hypothetical example: a company has a strict format for incident reports. Instead of repeating the
format in every prompt, they write an `incident-report` skill. Any agent that needs to write one loads
it, follows the steps and uses the bundled template.

Think of a skill as an **SOP for the agent**: a procedure written once and reused, instead of
re-explaining the steps every time.

The context saving comes from three layers:

1. the main context, always loaded;
2. each skill's short metadata (name and description, typically well under 200 tokens);
3. the full `SKILL.md` and its files, loaded only when that skill is used. Scripts and templates are
   read from disk when needed, so they cost nothing until then.

Skills also sit alongside other building blocks rather than replacing them. **Projects** organise the
workspace, **MCP** connects tools, **sub-agents** handle delegated reasoning, and **skills** carry the
reusable know-how all of them can use.

## B29. AI vs ML vs deep learning vs GenAI; LLMs vs SLMs

These terms nest inside each other like Russian dolls.

- **AI (Artificial Intelligence)** — the broad goal: machines doing tasks that normally need human
  intelligence. Rule-based expert systems count too.
- **Machine Learning (ML)** — a subset of AI where the system **learns patterns from data** instead of
  being hand-coded with rules. A spam filter trained on labelled emails is ML.
- **Deep Learning (DL)** — a subset of ML using **neural networks with many layers**. It's very good at
  messy data like images, audio and text.
- **Generative AI (GenAI)** — deep-learning models that **create** new content (text, images, code,
  audio) rather than only classifying or predicting a number.
- **NLP (Natural Language Processing)** — the field of making computers work with human language. It
  predates LLMs; LLMs are now its dominant tool.
- **LLM (Large Language Model)** — a generative model trained on huge amounts of text to predict the
  next token, with billions of parameters. It's general-purpose: one model can summarise, translate,
  answer questions and write code.
- **SLM (Small Language Model)** — the same idea at a smaller size (roughly a few hundred million to a
  few billion parameters). Less broadly capable, but cheaper, faster, and able to run on a laptop, phone
  or on-premises server. Often fine-tuned for one narrow job.

A simple rule for interviews: *use an SLM when the task is narrow and speed, cost or privacy matter;
use an LLM when the task is broad or needs strong reasoning.* Many systems use both: an SLM for intent
detection and an LLM for the final answer.

Models also differ by **modality**, meaning the kinds of input and output they handle: text, images,
audio, video, and even spatial or 3D data. A **multimodal** model can, say, look at a photo of a leaking
pump and read the maintenance note together.

## B30. How an LLM is built and trained

**What makes it "large"?** Three things scaled together: the number of **parameters** (the adjustable
numbers inside the network, now billions), the amount of **training data**, and the **compute** used.
At large enough scale, models started doing things nobody explicitly programmed, such as following
detailed instructions and multi-step reasoning.

**The architecture** is the **Transformer**:

- text is split into tokens ([B1](#b1-tokens-and-how-a-model-writes-an-answer));
- tokens become vectors, with **positional encoding** so order is known ([B21](#b21-attention-and-positional-encoding));
- a stack of layers, each using **attention** to let tokens look at each other and refine their
  meaning;
- training is spread across many GPUs, because the model is far too large for one.

**Training happens in stages**, a bit like education:

1. **Pre-training** — "reading the library." The model predicts the next token over a massive text
   corpus and absorbs grammar, facts and patterns. Afterwards it can continue text, but it isn't yet a
   good assistant: ask it a question and it might just write more questions.
2. **Instruction fine-tuning (supervised fine-tuning, SFT)** — "learning to follow instructions." It
   trains on curated instruction → response pairs, so it learns to answer, summarise and follow formats.
3. **Preference fine-tuning (RLHF)** — "learning what people prefer." Humans compare two answers; a
   **reward model** learns to predict their preference; the LLM is then optimised (classically with PPO)
   to produce preferred answers. This shapes helpfulness, tone and safety where there's no single
   "correct" answer. **DPO** is a simpler alternative that learns directly from preference pairs.
4. **Reasoning fine-tuning (RL with verifiable rewards)** — "practising exam questions with an answer
   key." For maths, code and logic, correctness can be checked automatically, so the reward comes from
   whether the answer is right. **GRPO** (popularised by DeepSeek) is a well-known method.

Why it matters in interviews: it explains why a base model and a chat model behave differently, why
models are good at some things (fluent text) and weak at others (exact arithmetic), and where
fine-tuning fits in ([E30](INTERVIEW-GUIDE-3-EXPERT.md#e30-reinforcement-fine-tuning-rlhf-dpo-grpo--and-when-to-use-which)).

---

# 🟢 Data engineering and SQL track

## D1. ETL vs ELT

Both describe moving data from source systems (apps, databases, sensors) into an analytics store. The
difference is **where the transformation happens**.

- **ETL — Extract, Transform, Load.** Data is cleaned and reshaped *before* loading, often on a separate
  processing server. This was the classic pattern when warehouse storage and compute were expensive, so
  you loaded only tidy, final data.
- **ELT — Extract, Load, Transform.** Raw data is loaded first, then transformed *inside* the warehouse
  or lakehouse using its own compute (SQL, Spark, dbt). This became the norm with cheap cloud storage
  and powerful engines like Snowflake, BigQuery and Databricks.

Why ELT is popular now: you keep the raw data, so if a business rule changes you can re-transform
history without re-extracting it. Transformations are just SQL that analysts can read and version. And
loading is fast and simple.

When ETL still makes sense: when you **must not** store raw data (for example, personal data that has
to be masked before it lands), or when the target is a system with little compute of its own.

Hypothetical example: a factory streams raw sensor readings into a lake every minute (load), then a
nightly SQL job turns them into hourly averages per machine (transform). That's ELT.

## D2. Data warehouse vs data lake (and lakehouse)

- A **data warehouse** stores **structured**, cleaned data in tables with a fixed schema, optimised for
  fast SQL analytics and BI dashboards. Schema is applied when data is written (*schema-on-write*).
  Examples: Snowflake, BigQuery, Redshift, Synapse.
- A **data lake** stores **any** data in its raw form (CSV, JSON, logs, images, Parquet) cheaply in
  object storage such as S3 or ADLS. Schema is applied when you read it (*schema-on-read*). It's
  flexible and cheap, but without discipline it becomes a "data swamp" that nobody trusts.
- A **lakehouse** combines the two: data stays in cheap open files in the lake, but a table format
  (Delta Lake, Apache Iceberg, Apache Hudi) adds warehouse features on top: ACID transactions, schema
  enforcement, time travel and fast SQL. Databricks is the best-known example.

A common pattern on top of a lake or lakehouse is the **medallion architecture**:

- **bronze** — raw data as it arrived;
- **silver** — cleaned and conformed;
- **gold** — business-level aggregates ready for reports.

Simple way to say it in an interview: *a warehouse is a tidy, organised library; a lake is a storage
unit where you keep everything; a lakehouse puts a library catalogue on top of the storage unit.*

## D3. Star schema vs snowflake schema

Both organise warehouse tables into **facts** and **dimensions**:

- A **fact table** holds the events or measurements you analyse: sales, sensor readings, work orders.
  It's long and narrow: keys plus numbers.
- **Dimension tables** hold descriptive context: product, store, date, machine, customer.

In a **star schema**, each dimension is a single, flat (denormalised) table joined directly to the fact
table. Draw it and it looks like a star. Queries need few joins, so they're simple and fast, which is
why BI tools love it. The cost is some repeated data (each product row repeats its category name).

In a **snowflake schema**, dimensions are **normalised** into sub-tables: product → category →
department, each its own table. That's less duplication and easier to keep consistent, but queries need
more joins and are harder to write.

Hypothetical example: `fact_downtime(machine_key, date_key, minutes_lost, cost)` with dimensions
`dim_machine` and `dim_date`. In a star, `dim_machine` includes `plant_name` and `machine_class`
directly; in a snowflake, `dim_machine` points to `dim_plant`.

The usual interview answer: *star for analytics speed and simplicity, which is the common default;
snowflake when dimensions are huge or change often and storage or consistency matters more.*

## D4. Window functions — the inventory stock-level question

A favourite SQL interview problem goes like this: *"For each product at each store, say whether the
stock is HIGH, LOW or NORMAL compared with that product's average stock across all stores."*

The trap is reaching for `GROUP BY`. `GROUP BY product_id` gives you the average, but it **collapses**
the rows, so you lose the individual store rows you need to compare against it.

The tool you need is a **window function** with `PARTITION BY`. It computes an aggregate over a group
of rows but **keeps every row**: *like GROUP BY, but you keep the details.*

Sample table `inventory`:

| store_id | product_id | quantity |
|---|---|---|
| S1 | P1 | 50 |
| S2 | P1 | 20 |
| S3 | P1 | 32 |
| S1 | P2 | 8 |
| S2 | P2 | 12 |

```sql
WITH stock AS (
    SELECT
        store_id,
        product_id,
        quantity,
        AVG(quantity) OVER (PARTITION BY product_id) AS avg_qty
    FROM inventory
)
SELECT
    store_id,
    product_id,
    quantity,
    ROUND(avg_qty, 1) AS avg_qty,
    CASE
        WHEN quantity > avg_qty + 10 THEN 'HIGH'
        WHEN quantity < avg_qty - 10 THEN 'LOW'
        ELSE 'NORMAL'
    END AS stock_level
FROM stock
ORDER BY product_id, store_id;
```

Result:

| store_id | product_id | quantity | avg_qty | stock_level |
|---|---|---|---|---|
| S1 | P1 | 50 | 34.0 | HIGH |
| S2 | P1 | 20 | 34.0 | LOW |
| S3 | P1 | 32 | 34.0 | NORMAL |
| S1 | P2 | 8 | 10.0 | NORMAL |
| S2 | P2 | 12 | 10.0 | NORMAL |

How to explain it:

- `AVG(quantity) OVER (PARTITION BY product_id)` computes P1's average (34) and writes it on **every**
  P1 row, without merging them.
- The **CTE** (`WITH stock AS ...`) is there because you can't use a window function directly in a
  `WHERE` or a later `CASE` at the same level. Compute it first, then use it.
- The threshold of 10 units is a business rule; a percentage (say ±30% of the average) often makes more
  sense when products have very different volumes.

Likely follow-ups, all using the same window idea:

- **Rank stores by stock within each product:** `RANK() OVER (PARTITION BY product_id ORDER BY quantity DESC)`.
- **Running total of stock movements over time:** `SUM(qty_change) OVER (PARTITION BY product_id ORDER BY movement_date)`.
- **Change since the last count:** `quantity - LAG(quantity) OVER (PARTITION BY store_id, product_id ORDER BY count_date)`.
- **Flag items below their reorder point** by joining a `products` table with `reorder_level`.

---

**Guide parts:** **🟢 Beginner** (this file) · [🟡 Intermediate](INTERVIEW-GUIDE-2-INTERMEDIATE.md) · [🔴 Expert](INTERVIEW-GUIDE-3-EXPERT.md) · Companion: [INTERVIEW-PREP.md](INTERVIEW-PREP.md) (same course material by day, with more code)

**Next:** [🟡 Intermediate →](INTERVIEW-GUIDE-2-INTERMEDIATE.md)
