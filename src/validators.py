import os
import logging
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GraphValidator:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def validate_counts(self):
        expected_counts = {
            "Sector": 8,
            "SkillTrack": 12,
            "Skill": 52,
            "JobRole": 18,
            "Course": 30
        }
        
        all_passed = True
        with self.driver.session() as session:
            for label, expected in expected_counts.items():
                result = session.run(f"MATCH (n:{label}) RETURN count(n) as count").single()
                actual = result["count"]
                if actual == expected:
                    logger.info(f"✅ {label} count matches: {actual}")
                else:
                    logger.error(f"❌ {label} count mismatch! Expected {expected}, got {actual}")
                    all_passed = False

            # Edge count validation (116 total expected from dataset metadata)
            # 12 sector_has_track + 74 skill_required_by_role + 30 skill_prerequisite_of = 116 explicit edges.
            result = session.run("""
                MATCH ()-[r:HAS_TRACK|REQUIRED_BY|PREREQUISITE_OF]->() 
                RETURN count(r) as count
            """).single()
            if result["count"] == 116:
                logger.info(f"✅ Explicit edge count matches: 116")
            else:
                logger.error(f"❌ Explicit edge count mismatch! Expected 116, got {result['count']}")
                all_passed = False
                
        return all_passed

    def check_orphans(self):
        with self.driver.session() as session:
            # Nodes without any relationships
            result = session.run("""
                MATCH (n) WHERE NOT (n)--() RETURN count(n) as count
            """).single()
            
            if result["count"] == 0:
                logger.info("✅ No orphaned nodes found.")
                return True
            else:
                logger.error(f"❌ Found {result['count']} orphaned nodes!")
                return False

    def check_dag(self):
        with self.driver.session() as session:
            # Look for cycles in PREREQUISITE_OF
            result = session.run("""
                MATCH path = (n:Skill)-[:PREREQUISITE_OF*]->(n)
                RETURN count(path) as count
            """).single()
            
            if result["count"] == 0:
                logger.info("✅ Prerequisite graph is acyclic (DAG).")
                return True
            else:
                logger.error(f"❌ Found {result['count']} cycles in prerequisite graph!")
                return False

    def run_all(self):
        logger.info("Running Data Validation...")
        counts_ok = self.validate_counts()
        orphans_ok = self.check_orphans()
        dag_ok = self.check_dag()
        
        if counts_ok and orphans_ok and dag_ok:
            logger.info("🎉 All validations passed successfully!")
            return True
        else:
            logger.error("⚠️ Validation failed.")
            return False

if __name__ == "__main__":
    URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    USER = os.getenv("NEO4J_USER", "neo4j")
    PWD = os.getenv("NEO4J_PASSWORD", "password")
    
    validator = GraphValidator(URI, USER, PWD)
    try:
        validator.run_all()
    finally:
        validator.close()
