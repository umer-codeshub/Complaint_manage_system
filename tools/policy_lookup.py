"""Read authorized demo policies from JSON. No LLM-created policy text."""
import json
from pathlib import Path

class PolicyDataError(Exception):
    pass

def lookup_policy(category: str, path: str | Path) -> dict:
    try:
        with open(path, encoding='utf-8') as stream:
            policies = json.load(stream)
        if not isinstance(policies, dict):
            raise ValueError('Expected policy object')
        policy = policies.get(category)
        if policy is None:
            return {'found': False, 'reason': 'No matching verified demo policy'}
        required = {'id', 'title', 'text', 'conditions', 'restrictions', 'escalate_when'}
        if not isinstance(policy, dict) or not required.issubset(policy):
            raise ValueError('Malformed policy')
        return {'found': True, 'policy': policy, 'demo': True}
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise PolicyDataError('Policy reference unavailable or malformed') from exc
