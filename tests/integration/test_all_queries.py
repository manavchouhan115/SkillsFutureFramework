import requests
import json
import time

URL = "http://127.0.0.1:8000/api/chat"

queries = [
    "What skills does a Data Scientist need?",
    "I know Python and SQL. What is the fastest path to becoming an AI Engineer?",
    "Which skills are most transferable between the Digital and Green economies?",
    "I am a healthcare data analyst. What skill gaps do I have for a Sustainability Consultant role?",
    "What SkillsFuture courses should I take to learn Machine Learning?"
]

for idx, q in enumerate(queries):
    print(f"\n--- Query {idx+1}: {q} ---")
    try:
        response = requests.post(URL, json={"message": q})
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Intent Extracted: {data.get('intent')}")
        print(f"Reply Length: {len(data.get('reply', ''))} characters")
        graph = data.get('raw_graph_data')
        if graph:
            print(f"Graph Data present: Yes (Keys: {list(graph.keys())})")
        else:
            print("Graph Data present: No")
    except Exception as e:
        print(f"Error: {e}")
    time.sleep(1) # to avoid rate limits if any
