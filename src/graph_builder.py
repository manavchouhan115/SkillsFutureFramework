import json
import logging
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

class GraphBuilder:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def setup_constraints(self):
        logger.info("Setting up constraints and indexes...")
        constraints = [
            "CREATE CONSTRAINT sector_id IF NOT EXISTS FOR (n:Sector) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT track_id IF NOT EXISTS FOR (n:SkillTrack) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT skill_id IF NOT EXISTS FOR (n:Skill) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT role_id IF NOT EXISTS FOR (n:JobRole) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT course_id IF NOT EXISTS FOR (n:Course) REQUIRE n.id IS UNIQUE"
        ]
        with self.driver.session() as session:
            for query in constraints:
                session.run(query)
        logger.info("Constraints setup complete.")

    def clear_database(self):
        logger.info("Clearing existing database...")
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    def load_data(self, data_path):
        with open(data_path, 'r') as f:
            data = json.load(f)
        
        with self.driver.session() as session:
            # 1. Create Nodes
            logger.info(f"Loading {len(data.get('sectors', []))} Sectors...")
            for sector in data.get("sectors", []):
                session.run("""
                    CREATE (s:Sector {id: $id, name: $name, economy: $economy, description: $description})
                """, **sector)

            logger.info(f"Loading {len(data.get('skill_tracks', []))} Skill Tracks...")
            for track in data.get("skill_tracks", []):
                session.run("""
                    CREATE (t:SkillTrack {id: $id, name: $name, description: $description})
                """, id=track["id"], name=track["name"], description=track.get("description", ""))

            logger.info(f"Loading {len(data.get('skills', []))} Skills...")
            for skill in data.get("skills", []):
                session.run("""
                    CREATE (sk:Skill {
                        id: $id, name: $name, difficulty: $difficulty, 
                        economy: $economy, transferability: $transferability, 
                        sdfe_priority: $sdfe_priority
                    })
                """, **{k: v for k, v in skill.items() if k != 'track_ids'})

            logger.info(f"Loading {len(data.get('job_roles', []))} Job Roles...")
            for role in data.get("job_roles", []):
                session.run("""
                    CREATE (r:JobRole {id: $id, name: $name, seniority: $seniority, economy: $economy})
                """, id=role["id"], name=role["name"], seniority=role.get("seniority", ""), economy=role.get("economy", ""))

            logger.info(f"Loading {len(data.get('courses', []))} Courses...")
            for course in data.get("courses", []):
                session.run("""
                    CREATE (c:Course {
                        id: $id, name: $name, provider: $provider, 
                        duration_hours: $duration_hours, difficulty: $difficulty, 
                        sfc_funded: $sfc_funded
                    })
                """, **{k: v for k, v in course.items() if k != 'skill_ids'})

            # 2. Create Edges
            logger.info("Creating Relationships...")
            
            # Explicit edges from JSON
            edges = data.get("edges", {})
            for edge in edges.get("sector_has_track", []):
                session.run("""
                    MATCH (s:Sector {id: $source}), (t:SkillTrack {id: $target})
                    MERGE (s)-[:HAS_TRACK]->(t)
                """, source=edge["source"], target=edge["target"])
                
            for edge in edges.get("skill_required_by_role", []):
                session.run("""
                    MATCH (sk:Skill {id: $source}), (r:JobRole {id: $target})
                    MERGE (sk)-[:REQUIRED_BY]->(r)
                """, source=edge["source"], target=edge["target"])
                
            for edge in edges.get("skill_prerequisite_of", []):
                session.run("""
                    MATCH (s1:Skill {id: $source}), (s2:Skill {id: $target})
                    MERGE (s1)-[:PREREQUISITE_OF {note: $note}]->(s2)
                """, source=edge["source"], target=edge["target"], note=edge.get("note", ""))

            # Implicit edges (CONTAINS_SKILL and TEACHES)
            for skill in data.get("skills", []):
                for track_id in skill.get("track_ids", []):
                    session.run("""
                        MATCH (t:SkillTrack {id: $track_id}), (sk:Skill {id: $skill_id})
                        MERGE (t)-[:CONTAINS_SKILL]->(sk)
                    """, track_id=track_id, skill_id=skill["id"])

            for course in data.get("courses", []):
                for skill_id in course.get("skill_ids", []):
                    session.run("""
                        MATCH (c:Course {id: $course_id}), (sk:Skill {id: $skill_id})
                        MERGE (c)-[:TEACHES]->(sk)
                    """, course_id=course["id"], skill_id=skill_id)

            logger.info("Data ingestion completed successfully.")

if __name__ == "__main__":
    data_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "skillsfuture_dataset.json")
    builder = GraphBuilder(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    try:
        builder.setup_constraints()
        builder.clear_database()
        builder.load_data(data_file)
    finally:
        builder.close()
