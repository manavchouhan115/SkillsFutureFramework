import os
from dotenv import load_dotenv
from src.query_service import QueryService
from src.llm_service import LLMService

load_dotenv()

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PWD = os.getenv("NEO4J_PASSWORD", "password")

print("Initializing services...")
q_srv = QueryService(URI, USER, PWD)
llm_srv = LLMService(q_srv)

print("Sending chat request to Groq & Neo4j...")
response = llm_srv.process_chat("What skills do I need to become an AI Engineer?")

print("\n================== INTENT ==================")
print(response.get("intent"))

print("\n================ RAW GRAPH ================")
print(response.get("raw_graph_data"))

print("\n================ AI REPLY =================")
print(response.get("reply"))
