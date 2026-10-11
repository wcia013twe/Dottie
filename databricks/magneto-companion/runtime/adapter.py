"""Map the durable invocation envelope to the companion plan contract."""
from agent.agent import run_agent


def _parts(value):
    if not isinstance(value, dict) or set(value) != {'snapshot', 'available_mcp_tools'}:
        raise ValueError('input must carry snapshot and available_mcp_tools')
    return value['snapshot'], value['available_mcp_tools']


async def invoke(value, context):
    snapshot, tools = _parts(value)
    if not isinstance(snapshot, dict) or snapshot.get('request_id') != context.invocation_id:
        raise ValueError('request_id must match the invocation UUID')
    result = await run_agent(snapshot, tools, session_id=context.session_id)
    await context.emit({'type': 'plan', 'result': result})
    return {'plan': result['plan'], 'model': result['model'], 'elapsed_ms': result['elapsed_ms']}


# No physical side effects: a replay can repeat inference, never hardware.
recover = invoke
