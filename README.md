# Skills & Competency Graph System

An AI-powered, graph-based personalised learning platform designed for the SkillsFuture Skills Framework. 
This system ingests skill data into Neo4j, computes learning paths and gap analyses using topological sorting, and overlays an intelligent natural language interface powered by Groq (LLaMA-3).

## Features
- **Graph Database Backend**: Data is ingested into Neo4j with a robust schema separating Sectors, SkillTracks, Skills, JobRoles, and Courses.
- **Topological Learning Paths**: Computes the optimal sequence of skills a learner must acquire to reach a target role, respecting prerequisites.
- **Intelligent Gap Analysis**: Ranks skill gaps based on an "unlock score" and distance from current skills to prioritize foundational skills.
- **LLM Integration (Part C)**: Translate natural language questions (e.g., "What do I need to become an AI Engineer?") into precise graph queries.
- **Interactive Visualization (Part D)**: A web-based `vis-network` UI that displays a live graph alongside the AI Chatbot.

## 1. Prerequisites
- **Python 3.9+**
- **Docker & Docker Compose**
- **Groq API Key**: Create a free account at [groq.com](https://groq.com) and get an API key.

## 2. Setup Instructions

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables**
   Create a `.env` file in the root directory:
   ```env
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=password
   GROQ_API_KEY=your_groq_api_key_here
   ```

3. **Start the Database**
   ```bash
   docker-compose up -d
   ```

4. **Ingest Data into Neo4j**
   ```bash
   python src/graph_builder.py
   ```
   *Note: This will clear existing data, setup constraints, and ingest the `skillsfuture_dataset.json`.*

5. **Start the API & Web App**
   ```bash
   uvicorn api.main:app --reload
   ```
   Navigate to [http://localhost:8000](http://localhost:8000) to see the interactive Visualization & Chat app!

---

## 3. API Documentation & Examples

You can interact with the API endpoints manually or through the interactive Swagger UI at [http://localhost:8000/docs](http://localhost:8000/docs).

### Learning Path
Compute a topological learning path towards a role.
```bash
curl -X 'POST' \
  'http://localhost:8000/api/learning-path' \
  -H 'Content-Type: application/json' \
  -d '{
  "target_role": "ROL-01",
  "current_skills": ["SKL-01"]
}'
```

### Gap Analysis
Find and prioritize skill gaps.
```bash
curl -X 'POST' \
  'http://localhost:8000/api/gap-analysis' \
  -H 'Content-Type: application/json' \
  -d '{
  "target_role": "ROL-02",
  "current_skills": ["SKL-01", "SKL-03"]
}'
```

### Natural Language Query
```bash
curl -X 'POST' \
  'http://localhost:8000/api/chat' \
  -H 'Content-Type: application/json' \
  -d '{
  "message": "What skills do I need to become a Data Scientist?"
}'
```

---

## 4. Troubleshooting

- **ConnectionError (503)**: If the API returns a 503 error, your Neo4j database is likely down. Ensure `docker-compose up -d` is running.
- **ModuleNotFoundError: No module named 'src'**: If you get this running tests, make sure you are running pytest as a module: `python -m pytest tests/`
- **LLM Error**: If the Chatbot says "I'm having trouble connecting to my AI brain", ensure your `GROQ_API_KEY` is valid and the model `llama-3.3-70b-versatile` is supported.

## 5. Tests
Run the entire suite to verify graph ingestion, query logic, and LLM mocking:
```bash
python -m pytest tests/
```

## Demo Video
*(Insert Demo Video Link Here)*
