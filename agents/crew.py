"""CrewAI orchestration with Groq inference; Python owns all business actions."""
import os

from agents.schemas import ComplaintAnalysis, DraftOutput
from agents.tasks import analysis_description, draft_description

class AIUnavailable(Exception):
    pass

class ComplaintCrew:
    def __init__(self, api_key: str, model: str = 'openai/gpt-oss-120b'):
        self.api_key = api_key
        self.model = model.removeprefix('groq/')

    def _run(self, role, goal, description, output_type):
        if not self.api_key:
            raise AIUnavailable('Groq API key not configured')
        # Lazy import: deterministic tools and tests work without live API or CrewAI.
        try:
            from crewai import Agent, Crew, Task, Process, LLM
            # CrewAI's LiteLLM adapter reads GROQ_API_KEY. Avoid key exposure to UI/logs.
            os.environ['GROQ_API_KEY'] = self.api_key
            llm = LLM(model=f'groq/{self.model}', max_tokens=900, timeout=65, max_retries=1)
            agent = Agent(role=role, goal=goal,
                          backstory='Careful customer-support specialist. Never invent facts.',
                          allow_delegation=False, verbose=False, llm=llm, max_iter=2)
            task = Task(description=description, expected_output='Strict validated structured response',
                        agent=agent, output_pydantic=output_type)
            result = Crew(agents=[agent], tasks=[task], process=Process.sequential,
                          verbose=False, memory=False).kickoff()
            if result.pydantic is None:
                raise ValueError('CrewAI did not return validated structured output')
            return output_type.model_validate(result.pydantic)
        except Exception as exc:
            raise AIUnavailable('AI service or structured output unavailable') from exc

    def analyze(self, complaint):
        return self._run('Complaint Analyst', 'Accurate complaint triage',
                         analysis_description(complaint), ComplaintAnalysis)

    def draft(self, complaint, analysis, decision, order_result, policy_result):
        return self._run('Customer Communication Drafter', 'Fact-grounded email drafts',
                         draft_description(complaint, analysis, decision, order_result, policy_result), DraftOutput)
