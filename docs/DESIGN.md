# System Design & Architecture

This document outlines the high-level design choices, trade-offs, and scalability considerations for the Skills & Competency Graph platform.

## 1. Graph Schema Design Choices
The data was modeled into Neo4j with the following core entities:
- **`Sector` & `SkillTrack`**: Hierarchical grouping for skills.
- **`Skill`**: The atomic unit of competency.
- **`JobRole`**: Represents the target destination.
- **`Course`**: The actionable learning resource.

**Trade-offs:** 
Instead of modeling "Prerequisites" as a property on a node, they are modeled as explicit `[:PREREQUISITE_OF]` relationships. This allows for complex graph traversal (e.g., recursive prerequisite resolution) natively within Cypher. However, calculating massive chains purely in Cypher can lead to Cartesian product explosion, which influenced the query optimization logic.

## 2. Query Logic & Algorithm Optimization

### Why Python + Cypher?
For complex graph traversal, we fetch a constrained subgraph using Cypher and process the deep topology in Python:
1. **Cypher Step**: `MATCH (s)-[:REQUIRED_BY]->(role)`. Filter out `current_skills`, then fetch `[:PREREQUISITE_OF]` edges *strictly between* the missing skills.
2. **Python Step**: We run a **Topological Sort** (Kahn's Algorithm/DFS) in memory. 

**Why not 100% Cypher?** While Neo4j's APOC library supports topological sorting, doing it in the application layer (Python) provides two major benefits:
- **Testability**: The ranking algorithm is easily unit-tested with mocked data without hitting the database.
- **Custom Metrics**: It allows us to mathematically calculate custom metrics like `unlock_score` (number of descendants) dynamically during the traversal.

### Gap Analysis Ranking
The priority of a gap is determined by:
`Priority Score = (Unlock Score * 10) - Distance`
- **Unlock Score**: A skill that acts as a prerequisite for 3 other missing skills gets an unlock score of 3. High unlock scores represent foundational knowledge.
- **Distance**: A skill with no unfulfilled prerequisites has a distance of 1. If it requires another missing skill, its distance increases. Lower distance means it can be started sooner.

## 3. LLM Architecture (Groq LLaMA-3)

**Why Groq?** 
Groq's LPU infrastructure provides inference speeds of >800 tokens per second. For a synchronous Chat UI, this eliminates the typical LLM "thinking" latency, making the tool feel incredibly responsive.

**Two-Step Pipeline (Intent -> Execute -> Format)**
Instead of using a framework like LangChain to let the LLM directly write and execute Cypher queries (which is slow and poses massive security/hallucination risks), we use a deterministic two-step pipeline:
1. **Strict JSON Extraction**: The LLM acts purely as an intent parser (`learning_path` vs `gap_analysis`). We enforce a rigid JSON schema.
2. **Graph Execution**: Python executes safe, parameterized Cypher queries.
3. **Friendly Formatting**: The raw JSON output from Neo4j is fed back into Groq to generate a plain-english response.

## 4. Scaling the Architecture

To scale this system to the full SkillsFramework (38 Sectors, 119+ Job Roles, 80+ Skills), we would implement the following optimizations:

### A. Transitioning to Vector Search (RAG)
Currently, to help the LLM extract the correct `target_role` ID from natural language, we inject a dictionary of all Roles and Skills directly into the System Prompt.
- **The Problem**: Prompt injection hits token limits and degrades performance as the vocabulary grows to thousands of elements.
- **The Solution**: We would replace this with a **Vector Database (e.g., Pinecone or Neo4j Vector Indexes)**. When a user asks "How to become a Data Scientist?", we would embed the query, perform a cosine similarity search against the Role database, retrieve the closest `ROL-XX` ID, and *then* pass it to the Graph.

### B. Neo4j Indexing & Caching
- **Indexes**: We have already implemented UNIQUE constraints on IDs (`CREATE CONSTRAINT role_id FOR (r:JobRole) REQUIRE r.id IS UNIQUE`). As data grows, we would add composite indexes on `economy` and `seniority` for faster filtering.
- **Caching**: Learning paths for standard roles (e.g., "From Scratch to AI Engineer") are highly deterministic. We would introduce a Redis cache layer for the `/api/learning-path` endpoint to avoid recalculating the topological sort for identical queries.
