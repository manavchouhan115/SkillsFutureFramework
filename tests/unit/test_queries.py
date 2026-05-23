import pytest
import os
from src.query_service import QueryService
from dotenv import load_dotenv

load_dotenv()

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PWD = os.getenv("NEO4J_PASSWORD", "password")

@pytest.fixture(scope="module")
def query_service():
    service = QueryService(URI, USER, PWD)
    yield service
    service.close()

# Sample Profiles from Dataset
# LP-01: Needs Data Scientist skills
LP_01_SKILLS = []
LP_01_ROLE = "ROL-01" # Data Scientist

# LP-02: Partial skills for AI Engineer
LP_02_SKILLS = ["SKL-01", "SKL-03"] # Assuming these are Python and basic stats
LP_02_ROLE = "ROL-02" # AI Engineer

# LP-03: Experienced looking to transition
LP_03_SKILLS = ["SKL-01", "SKL-02", "SKL-03", "SKL-04"]
LP_03_ROLE = "ROL-03" # Data Engineer

def test_learning_path_lp01(query_service):
    res = query_service.get_learning_path(current_skills=LP_01_SKILLS, target_role_id=LP_01_ROLE)
    assert "learning_path" in res
    assert res["total_skills_needed"] > 0
    
    # Check topological sort (prerequisites should appear before dependents)
    # We can just verify the structure is returned
    path = res["learning_path"]
    seen_skills = set()
    for step in path:
        # For each prerequisite, it must have been seen already
        for prereq in step["prerequisites"]:
            # If prereq is not in the path at all, that's fine (might not be missing)
            # But if it is in the path, it MUST come before this step
            path_skill_ids = [s["skill_id"] for s in path]
            if prereq in path_skill_ids:
                assert prereq in seen_skills, f"Prerequisite {prereq} for {step['skill_id']} was not seen before it!"
        seen_skills.add(step["skill_id"])

def test_gap_analysis_lp02(query_service):
    res = query_service.get_gap_analysis(current_skills=LP_02_SKILLS, target_role_id=LP_02_ROLE)
    assert "skill_gaps" in res
    assert res["total_gaps"] > 0
    
    gaps = res["skill_gaps"]
    # Check ranking: highest priority_score first
    for i in range(1, len(gaps)):
        assert gaps[i-1]["priority_score"] >= gaps[i]["priority_score"]
        
    # Check course recommendations
    assert all("courses" in gap for gap in gaps)

def test_fully_qualified_edge_case(query_service):
    # Dynamically get all required skills for ROL-01
    with query_service.get_driver().session() as session:
        result = session.run("MATCH (s:Skill)-[:REQUIRED_BY]->(r:JobRole {id: 'ROL-01'}) RETURN s.id as id")
        all_skills = [record["id"] for record in result]
        
    res = query_service.get_learning_path(
        current_skills=all_skills, 
        target_role_id="ROL-01"
    )
    assert res["total_skills_needed"] == 0
    assert "fully qualified" in res.get("message", "").lower()
