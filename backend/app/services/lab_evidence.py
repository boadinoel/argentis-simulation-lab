"""Keep source claims, observed simulation events and hypotheses distinct."""
import json
from collections import Counter
from pathlib import Path

EVIDENCE_RULES = '''Evidence rules (override any conflicting forecasting template):
This is a synthetic strategic exercise, not a forecast, market survey or actual stakeholder testimony.
Graph searches retrieve uploaded background claims, NOT observed simulation outcomes.
Distinguish source-documented claims, founder-reported claims, scenario assumptions,
observed simulated responses, and your interpretation. Never promote scenario instructions
into completed experiments. Only say a branch was tested if its round appears in the run log.
Quote only observed responses with role and round. Preserve dissent. No invented probabilities,
customers, contracts, revenue outcomes or valuation. Real organization names denote synthetic roles.
Identify missing evidence, correlated personas, facilitator influence and untested alternatives.
Compare buying vetoes, costs, distribution incentives and measurable next experiments.
'''


def bind_seed_posts(posts, agents):
    """An exact identity is mandatory; matching only a broad entity type is unsafe."""
    by_id = {a.agent_id: a for a in agents}
    result = []
    for post in posts:
        agent = by_id.get(post.get('poster_agent_id'))
        if agent is None or post.get('poster_name') != agent.entity_name:
            raise ValueError('Opening post identity must exactly match an agent ID and name. Regenerate the configuration.')
        result.append({**post, 'poster_type': agent.entity_type})
    return result


def observed_context(simulation_id):
    from ..config import Config
    root = Path(Config.UPLOAD_FOLDER) / 'simulations' / simulation_id
    def read(name, default):
        path = root / name
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    state = read('run_state.json', {})
    config = read('simulation_config.json', {})
    events = []
    counts = Counter()
    for platform in ('reddit', 'twitter'):
        path = root / platform / 'actions.jsonl'
        if not path.exists():
            continue
        for line in path.read_text(encoding='utf-8').splitlines():
            event = json.loads(line)
            if not event.get('action_type'):
                continue
            counts[event.get('action_type')] += 1
            if event.get('action_type') in ('CREATE_POST', 'CREATE_COMMENT'):
                events.append(event)
    # Stable sample across the whole run, not just the first rounds.
    stride = max(1, (len(events) + 159) // 160)
    sample = events[::stride]
    for event in sample:
        args = event.get('action_args', {})
        if 'content' in args:
            args['content'] = args['content'][:1800]
    return json.dumps({'evidence_kind': 'actual_saved_run',
        'status': state.get('runner_status'), 'completed_rounds': state.get('current_round'),
        'action_counts': dict(counts), 'personas': config.get('agent_configs', []),
        'method': config.get('method', 'OASIS social simulation'),
        'planned_rounds': config.get('strategic_rounds', []),
        'source_manifest': read('source_manifest.json', {}),
        'observed_posts_sample': sample, 'sample_stride': stride,
        'note': 'Round zero contains predefined seed posts, not emergent responses.'}, ensure_ascii=False)
