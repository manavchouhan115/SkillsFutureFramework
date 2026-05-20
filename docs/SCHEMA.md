# Neo4j Graph Schema Design

## Nodes
- **Sector**: `id`, `name`, `economy`, `description`
- **SkillTrack**: `id`, `name`, `description`
- **Skill**: `id`, `name`, `difficulty`, `economy`, `transferability`, `sdfe_priority`
- **JobRole**: `id`, `name`, `seniority`, `economy`, `description`
- **Course**: `id`, `name`, `provider`, `duration_hours`, `difficulty`, `sfc_funded`

## Relationships
- `(:Sector)-[:HAS_TRACK]->(:SkillTrack)`
- `(:SkillTrack)-[:CONTAINS_SKILL]->(:Skill)`
- `(:Skill)-[:REQUIRED_BY]->(:JobRole)`
- `(:Skill)-[:PREREQUISITE_OF]->(:Skill)`
- `(:Course)-[:TEACHES]->(:Skill)`

## Indexes and Constraints
To ensure data integrity and query performance, we apply the following Cypher constraints:

```cypher
CREATE CONSTRAINT sector_id IF NOT EXISTS FOR (s:Sector) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT track_id IF NOT EXISTS FOR (t:SkillTrack) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT skill_id IF NOT EXISTS FOR (sk:Skill) REQUIRE sk.id IS UNIQUE;
CREATE CONSTRAINT role_id IF NOT EXISTS FOR (r:JobRole) REQUIRE r.id IS UNIQUE;
CREATE CONSTRAINT course_id IF NOT EXISTS FOR (c:Course) REQUIRE c.id IS UNIQUE;
```
