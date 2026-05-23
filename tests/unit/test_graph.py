import pytest
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PWD = os.getenv("NEO4J_PASSWORD", "password")

@pytest.fixture(scope="module")
def neo4j_session():
    driver = GraphDatabase.driver(URI, auth=(USER, PWD))
    session = driver.session()
    yield session
    session.close()
    driver.close()

def test_node_counts(neo4j_session):
    assert neo4j_session.run("MATCH (n:Sector) RETURN count(n) as c").single()["c"] == 8
    assert neo4j_session.run("MATCH (n:SkillTrack) RETURN count(n) as c").single()["c"] == 12
    assert neo4j_session.run("MATCH (n:Skill) RETURN count(n) as c").single()["c"] == 52
    assert neo4j_session.run("MATCH (n:JobRole) RETURN count(n) as c").single()["c"] == 18
    assert neo4j_session.run("MATCH (n:Course) RETURN count(n) as c").single()["c"] == 30

def test_explicit_edge_count(neo4j_session):
    result = neo4j_session.run("MATCH ()-[r:HAS_TRACK|REQUIRED_BY|PREREQUISITE_OF]->() RETURN count(r) as c").single()
    assert result["c"] == 116

def test_no_orphans(neo4j_session):
    result = neo4j_session.run("MATCH (n) WHERE NOT (n)--() RETURN count(n) as c").single()
    assert result["c"] == 0

def test_prerequisite_is_dag(neo4j_session):
    result = neo4j_session.run("MATCH path = (n:Skill)-[:PREREQUISITE_OF*]->(n) RETURN count(path) as c").single()
    assert result["c"] == 0
