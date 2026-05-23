import logging
import os
from collections import defaultdict, deque
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

logger = logging.getLogger(__name__)

class QueryService:
    def __init__(self, uri, user, password):
        self.uri = uri
        self.user = user
        self.password = password
        self._driver = None

    def get_driver(self):
        if not self._driver:
            self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        return self._driver

    def close(self):
        if self._driver:
            self._driver.close()

    def get_full_graph(self):
        """Returns the entire graph structure for visualization."""
        with self.get_driver().session() as session:
            # Fetch all valid nodes
            nodes_res = session.run("MATCH (n) WHERE n.id IS NOT NULL RETURN n.id as id, n.name as name, labels(n)[0] as group")
            nodes = [{"id": r["id"], "name": r["name"], "group": r["group"]} for r in nodes_res]
            
            # Fetch all relationships
            edges_res = session.run("MATCH (n)-[r]->(m) WHERE n.id IS NOT NULL AND m.id IS NOT NULL RETURN n.id as source, m.id as target, type(r) as type")
            edges = [{"source": r["source"], "target": r["target"], "type": r["type"]} for r in edges_res]
            
            return {"nodes": nodes, "edges": edges}

    def _get_missing_skills_graph(self, session, current_skills, target_role_id):
        # 1. Get all skills required by the role
        result = session.run("""
            MATCH (s:Skill)-[:REQUIRED_BY]->(r:JobRole {id: $role_id})
            RETURN s.id AS id, s.name AS name, s.difficulty AS difficulty
        """, role_id=target_role_id)
        
        required_skills = {record["id"]: {"id": record["id"], "name": record["name"]} for record in result}
        
        if not required_skills:
            raise ValueError(f"Role '{target_role_id}' not found or has no required skills.")

        # 2. Subtract current skills
        missing_skills = {k: v for k, v in required_skills.items() if k not in current_skills}
        
        if not missing_skills:
            return {}, {}, []

        missing_ids = list(missing_skills.keys())

        # 3. Build prerequisite subgraph for missing skills
        # Only care about prerequisites that are ALSO missing. 
        # If a prerequisite is already in current_skills, it's considered fulfilled.
        rels_result = session.run("""
            MATCH (s1:Skill)-[:PREREQUISITE_OF]->(s2:Skill)
            WHERE s1.id IN $missing_ids AND s2.id IN $missing_ids
            RETURN s1.id AS pre, s2.id AS post
        """, missing_ids=missing_ids)

        edges = [(record["pre"], record["post"]) for record in rels_result]

        # 4. Get courses for missing skills
        courses_result = session.run("""
            MATCH (c:Course)-[:TEACHES]->(s:Skill)
            WHERE s.id IN $missing_ids
            RETURN s.id AS skill_id, c.id AS course_id, c.name AS course_name
        """, missing_ids=missing_ids)

        courses_by_skill = defaultdict(list)
        for record in courses_result:
            courses_by_skill[record["skill_id"]].append({
                "course_id": record["course_id"],
                "course_name": record["course_name"]
            })

        return missing_skills, edges, courses_by_skill

    def _compute_metrics(self, missing_skills, edges):
        # Build adjacency lists
        adj = defaultdict(list)
        rev_adj = defaultdict(list)
        in_degree = {sk: 0 for sk in missing_skills}
        
        for pre, post in edges:
            adj[pre].append(post)
            rev_adj[post].append(pre)
            in_degree[post] += 1

        # Topological Sort & Distance Calculation
        # distance = longest path from a root in the missing graph
        distances = {sk: 1 for sk in missing_skills}
        
        queue = deque([sk for sk in missing_skills if in_degree[sk] == 0])
        topo_order = []

        while queue:
            node = queue.popleft()
            topo_order.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                # Distance is max distance of prerequisites + 1
                if distances[node] + 1 > distances[neighbor]:
                    distances[neighbor] = distances[node] + 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(topo_order) != len(missing_skills):
            logger.warning("Circular dependency detected in prerequisite graph!")
            # Add remaining nodes to topo order to ensure we don't drop them
            for sk in missing_skills:
                if sk not in topo_order:
                    topo_order.append(sk)

        # Unlock Score = Number of descendants in the missing graph
        unlock_scores = {sk: 0 for sk in missing_skills}
        # Iterate in reverse topological order to compute descendants efficiently
        descendants = {sk: set() for sk in missing_skills}
        for node in reversed(topo_order):
            for neighbor in adj[node]:
                descendants[node].add(neighbor)
                descendants[node].update(descendants[neighbor])
            unlock_scores[node] = len(descendants[node])

        return topo_order, distances, unlock_scores, rev_adj

    def get_learning_path(self, current_skills, target_role_id):
        try:
            with self.get_driver().session() as session:
                missing_skills, edges, courses_by_skill = self._get_missing_skills_graph(
                    session, current_skills, target_role_id
                )

                if not missing_skills:
                    return {"learning_path": [], "total_skills_needed": 0, "message": "Learner is fully qualified for this role."}

                topo_order, _, _, rev_adj = self._compute_metrics(missing_skills, edges)

                learning_path = []
                for i, skill_id in enumerate(topo_order):
                    learning_path.append({
                        "skill_id": skill_id,
                        "skill_name": missing_skills[skill_id]["name"],
                        "order": i + 1,
                        "prerequisites": rev_adj[skill_id],
                        "recommended_courses": courses_by_skill[skill_id]
                    })

                # Basic duration estimation based on skills needed (e.g., 1.5 months per skill)
                months = len(learning_path) * 1.5
                estimated_duration = f"{int(months)} months" if months % 1 == 0 else f"{months:.1f} months"

                return {
                    "learning_path": learning_path,
                    "total_skills_needed": len(learning_path),
                    "estimated_duration": estimated_duration
                }
        except ServiceUnavailable as e:
            logger.error(f"Neo4j connection error: {e}")
            raise ConnectionError("Service Unavailable: Cannot connect to the database.")
        except Exception as e:
            logger.error(f"Error in get_learning_path: {e}")
            raise

    def get_gap_analysis(self, current_skills, target_role_id):
        try:
            with self.get_driver().session() as session:
                missing_skills, edges, courses_by_skill = self._get_missing_skills_graph(
                    session, current_skills, target_role_id
                )

                if not missing_skills:
                    return {"skill_gaps": [], "total_gaps": 0, "message": "Learner is fully qualified for this role."}

                _, distances, unlock_scores, _ = self._compute_metrics(missing_skills, edges)

                skill_gaps = []
                for skill_id in missing_skills:
                    # Priority Score = unlock_score - distance (so high unlock and low distance is better)
                    # We can normalize it or just use a raw score for sorting
                    # Let's say: priority_score = (unlock_score * 10) - distances[skill_id]
                    priority_score = (unlock_scores[skill_id] * 10) - distances[skill_id]
                    
                    skill_gaps.append({
                        "skill_id": skill_id,
                        "skill_name": missing_skills[skill_id]["name"],
                        "priority_score": priority_score,
                        "unlock_score": unlock_scores[skill_id],
                        "distance_from_current": distances[skill_id],
                        "courses": courses_by_skill[skill_id][:2] # Return up to 2 courses
                    })

                # Sort by priority score descending
                skill_gaps.sort(key=lambda x: x["priority_score"], reverse=True)

                return {
                    "skill_gaps": skill_gaps,
                    "total_gaps": len(skill_gaps)
                }
        except ServiceUnavailable as e:
            logger.error(f"Neo4j connection error: {e}")
            raise ConnectionError("Service Unavailable: Cannot connect to the database.")
        except Exception as e:
            logger.error(f"Error in get_gap_analysis: {e}")
            raise

    def get_transferable_skills(self, source_sector_id: str, target_sector_id: str = None) -> dict:
        """Finds highly transferable skills from the source sector."""
        if not source_sector_id:
            raise ValueError("Source sector must be provided.")
            
        with self.get_driver().session() as session:
            query = """
                MATCH (sec:Sector {id: $source})
                OPTIONAL MATCH (sec)-[:HAS_TRACK]->(t:SkillTrack)-[:CONTAINS_SKILL]->(s:Skill)
                WHERE s.transferability IN ['High', 'Medium']
                RETURN sec.name as sector_name, s.id as skill_id, s.name as skill_name, s.transferability as transferability
            """
            result = session.run(query, source=source_sector_id)
            skills = []
            sector_name = None
            
            for record in result:
                if not sector_name and record["sector_name"]:
                    sector_name = record["sector_name"]
                if record["skill_id"]:
                    skills.append({
                        "skill_id": record["skill_id"], 
                        "skill_name": record["skill_name"], 
                        "transferability": record["transferability"]
                    })
                    
            return {
                "source_sector": sector_name or source_sector_id,
                "transferable_skills": skills,
                "total_skills": len(skills)
            }

    def get_courses_for_skill(self, target_skill_id: str) -> dict:
        """Finds courses that teach a specific skill."""
        if not target_skill_id:
            raise ValueError("Target skill must be provided.")
            
        with self.get_driver().session() as session:
            query = """
                MATCH (c:Course)-[:TEACHES]->(s:Skill {id: $skill_id})
                RETURN c.id as course_id, c.name as course_name, c.provider as provider, s.name as skill_name
            """
            result = session.run(query, skill_id=target_skill_id)
            courses = []
            skill_name = None
            
            for record in result:
                if not skill_name and record["skill_name"]:
                    skill_name = record["skill_name"]
                courses.append({
                    "course_id": record["course_id"],
                    "course_name": record["course_name"],
                    "provider": record["provider"]
                })
                
            return {
                "target_skill_id": target_skill_id,
                "target_skill_name": skill_name or target_skill_id,
                "courses": courses,
                "total_courses": len(courses)
            }

# Singleton instance initialization will be done in the FastAPI app
