import pytest
from unittest.mock import patch, MagicMock
from src.llm_service import LLMService

class MockQueryService:
    def get_driver(self):
        class MockDriver:
            def session(self):
                class MockSession:
                    def __enter__(self): return self
                    def __exit__(self, *args): pass
                    def run(self, query):
                        if "JobRole" in query:
                            return [{"id": "ROL-01", "name": "Data Scientist"}, {"id": "ROL-02", "name": "AI Engineer"}]
                        elif "Skill" in query:
                            return [{"id": "SKL-01", "name": "Python Programming"}, {"id": "SKL-03", "name": "SQL & Database Management"}]
                        return []
                return MockSession()
        return MockDriver()
    
    def get_learning_path(self, current_skills, target_role):
        return {"learning_path": [], "total_skills_needed": 0}
        
    def get_gap_analysis(self, current_skills, target_role):
        return {"skill_gaps": [], "total_gaps": 0}

@pytest.fixture
def llm_service():
    with patch('src.llm_service.Groq'):
        service = LLMService(MockQueryService())
        return service

def test_intent_extraction_query_1(llm_service):
    # "What skills does a Data Scientist need?"
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content='{"intent": "learning_path", "target_role": "ROL-01", "current_skills": [], "confidence": 0.95}'))]
    llm_service.client.chat.completions.create.return_value = mock_response
    
    res = llm_service.extract_intent("What skills does a Data Scientist need?")
    assert res["intent"] == "learning_path"
    assert res["target_role"] == "ROL-01"

def test_intent_extraction_query_2(llm_service):
    # "I know Python and SQL. What is the fastest path to becoming an AI Engineer?"
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content='{"intent": "learning_path", "target_role": "ROL-02", "current_skills": ["SKL-01", "SKL-03"], "confidence": 0.9}'))]
    llm_service.client.chat.completions.create.return_value = mock_response
    
    res = llm_service.extract_intent("I know Python and SQL. What is the fastest path to becoming an AI Engineer?")
    assert res["intent"] == "learning_path"
    assert res["target_role"] == "ROL-02"
    assert "SKL-01" in res["current_skills"]

def test_intent_extraction_query_3(llm_service):
    # "Which skills are most transferable between the Digital and Green economies?"
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content='{"intent": "transferable_skills", "target_role": null, "current_skills": [], "confidence": 0.85}'))]
    llm_service.client.chat.completions.create.return_value = mock_response
    
    res = llm_service.extract_intent("Which skills are most transferable between the Digital and Green economies?")
    assert res["intent"] == "transferable_skills"

def test_intent_extraction_query_4(llm_service):
    # "I am a healthcare data analyst. What skill gaps do I have for a Sustainability Consultant role?"
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content='{"intent": "gap_analysis", "target_role": "ROL-16", "current_skills": [], "confidence": 0.9}'))]
    llm_service.client.chat.completions.create.return_value = mock_response
    
    res = llm_service.extract_intent("I am a healthcare data analyst. What skill gaps do I have for a Sustainability Consultant role?")
    assert res["intent"] == "gap_analysis"
    assert res["target_role"] == "ROL-16"

def test_intent_extraction_query_5(llm_service):
    # "What SkillsFuture courses should I take to learn Machine Learning?"
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content='{"intent": "learning_path", "target_role": null, "current_skills": [], "confidence": 0.8}'))]
    llm_service.client.chat.completions.create.return_value = mock_response
    
    res = llm_service.extract_intent("What SkillsFuture courses should I take to learn Machine Learning?")
    # Might lack target role
    assert res["intent"] == "learning_path"

def test_process_chat_full_flow(llm_service):
    # Mock extract
    mock_extract_response = MagicMock()
    mock_extract_response.choices = [MagicMock(message=MagicMock(content='{"intent": "learning_path", "target_role": "ROL-01", "current_skills": [], "confidence": 0.9}'))]
    
    # Mock format
    mock_format_response = MagicMock()
    mock_format_response.choices = [MagicMock(message=MagicMock(content="Here is your learning path..."))]
    
    # Set side effect to return different responses for the 2 LLM calls
    llm_service.client.chat.completions.create.side_effect = [mock_extract_response, mock_format_response]
    
    result = llm_service.process_chat("How to become a Data Scientist?")
    
    assert result["intent"] == "learning_path"
    assert result["reply"] == "Here is your learning path..."
    assert "raw_graph_data" in result
