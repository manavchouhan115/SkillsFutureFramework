import os
import json
import logging
import time
from groq import Groq

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, query_service):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "llama-3.3-70b-versatile"
        self.query_service = query_service
        self._load_vocabulary()

    def _load_vocabulary(self):
        # Load ID mappings to inject into the prompt
        self.role_map = {}
        self.skill_map = {}
        self.sector_map = {}
        try:
            with self.query_service.get_driver().session() as session:
                roles = session.run("MATCH (r:JobRole) RETURN r.id as id, r.name as name")
                for record in roles:
                    self.role_map[record["name"]] = record["id"]

                skills = session.run("MATCH (s:Skill) RETURN s.id as id, s.name as name")
                for record in skills:
                    self.skill_map[record["name"]] = record["id"]
                    
                sectors = session.run("MATCH (s:Sector) RETURN s.id as id, s.name as name")
                for record in sectors:
                    self.sector_map[record["name"]] = record["id"]
        except Exception as e:
            logger.warning(f"Could not load vocabulary from Neo4j: {e}")

    def _get_extraction_prompt(self):
        vocab_str = f"Roles: {json.dumps(self.role_map)}\nSkills: {json.dumps(self.skill_map)}\nSectors/Economies: {json.dumps(self.sector_map)}"
        
        return f"""You are an intent extraction engine for a Skills Graph API.
Your task is to parse a user's natural language query into a strict JSON object.

Valid Intents: "learning_path", "gap_analysis", "transferable_skills", "find_courses"

Available Vocabulary Mapping:
{vocab_str}

Output JSON Schema:
{{
  "intent": "learning_path" | "gap_analysis" | "transferable_skills" | "find_courses",
  "target_role": "ROL-XX" | null,
  "current_skills": ["SKL-XX", ...] | [],
  "source_sector": "SEC-XX" | null,
  "target_sector": "SEC-XX" | null,
  "target_skill": "SKL-XX" | null,
  "confidence": 0.0 to 1.0
}}

Rules:
1. Output ONLY valid JSON. No markdown backticks, no preamble, no explanation.
2. You MUST use the exact IDs (e.g., 'ROL-01') from the Vocabulary Mapping based on the user's text.
3. If a role or skill mentioned is not in the vocabulary, leave it null or omit it.

Few-Shot Examples:

Query: "What skills do I need to become a Data Scientist?"
{{
  "intent": "learning_path",
  "target_role": "ROL-01",
  "current_skills": [],
  "source_sector": null,
  "target_sector": null,
  "target_skill": null,
  "confidence": 0.95
}}

Query: "I know Data Analytics. What are my gaps for becoming a Data Engineer?"
{{
  "intent": "gap_analysis",
  "target_role": "ROL-03",
  "current_skills": ["SKL-06"],
  "source_sector": null,
  "target_sector": null,
  "target_skill": null,
  "confidence": 0.95
}}

Query: "What SkillsFuture courses should I take to learn Machine Learning?"
{{
  "intent": "find_courses",
  "target_role": null,
  "current_skills": [],
  "source_sector": null,
  "target_sector": null,
  "target_skill": "SKL-04",
  "confidence": 0.95
}}
"""

    def extract_intent(self, user_query: str):
        retries = 2
        for attempt in range(retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self._get_extraction_prompt()},
                        {"role": "user", "content": f"Query: \"{user_query}\""}
                    ],
                    temperature=0.2,
                    max_tokens=300,
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content
                logger.info(f"LLM Extraction Output: {content}")
                
                parsed = json.loads(content)
                return parsed

            except Exception as e:
                logger.error(f"Groq Extraction API error (attempt {attempt+1}): {e}")
                if attempt == retries:
                    raise RuntimeError("Failed to connect to Groq API after retries.")
                time.sleep(1)

    def format_response(self, user_query: str, extracted_data: dict, graph_data: dict):
        system_prompt = """You are a helpful career advisor for a Skills Graph API.
Your job is to translate raw JSON data from a graph database query into a friendly, plain English response for the user.
Keep it concise, supportive, and clearly structured. Mention specific courses if available."""

        retries = 2
        for attempt in range(retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"User Query: {user_query}\n\nExtracted Parameters: {json.dumps(extracted_data)}\n\nDatabase Results: {json.dumps(graph_data)}"}
                    ],
                    temperature=0.7,
                    max_tokens=800
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.error(f"Groq Formatting API error (attempt {attempt+1}): {e}")
                if attempt == retries:
                    return "I found some information, but I'm having trouble formatting it right now. Please check the raw data below."
                time.sleep(1)

    def process_chat(self, user_query: str):
        # 1. Intent Extraction
        try:
            extracted = self.extract_intent(user_query)
        except RuntimeError as e:
            return {"intent": "error", "reply": "I'm having trouble connecting to my AI brain right now. Please try again later."}

        # 2. Confidence Fallback
        confidence = extracted.get("confidence", 0)
        if confidence < 0.7:
            return {
                "intent": "unknown", 
                "reply": "I'm not entirely sure what you mean. Could you please clarify if you're looking for a learning path, a gap analysis, or transferable skills?"
            }

        intent = extracted.get("intent")
        target_role = extracted.get("target_role")
        current_skills = extracted.get("current_skills", [])

        # 3. Graph Execution
        graph_data = {}
        try:
            if intent == "learning_path":
                if not target_role:
                    return {"intent": intent, "reply": "I understand you want a learning path, but I need to know the specific target role. E.g., 'Data Scientist'."}
                graph_data = self.query_service.get_learning_path(current_skills, target_role)

            elif intent == "gap_analysis":
                if not target_role:
                    return {"intent": intent, "reply": "I understand you want a gap analysis, but I need to know the specific target role. E.g., 'AI Engineer'."}
                graph_data = self.query_service.get_gap_analysis(current_skills, target_role)

            elif intent == "transferable_skills":
                source_sector = extracted.get("source_sector")
                target_sector = extracted.get("target_sector")
                if not source_sector:
                    return {"intent": intent, "reply": "I need to know which sector you are transferring from. E.g., 'Healthcare'."}
                graph_data = self.query_service.get_transferable_skills(source_sector, target_sector)

            elif intent == "find_courses":
                target_skill = extracted.get("target_skill")
                if not target_skill:
                    return {"intent": intent, "reply": "I need to know which specific skill you want to learn. E.g., 'Machine Learning'."}
                graph_data = self.query_service.get_courses_for_skill(target_skill)

            else:
                return {"intent": "unknown", "reply": "I couldn't recognize that request."}
                
        except Exception as e:
            logger.error(f"Graph execution error: {e}")
            return {"intent": intent, "reply": "I encountered an error while searching the graph database. Please ensure your query is valid."}

        # 4. LLM Formatting
        formatted_reply = self.format_response(user_query, extracted, graph_data)

        return {
            "intent": intent,
            "reply": formatted_reply,
            "raw_graph_data": graph_data
        }
