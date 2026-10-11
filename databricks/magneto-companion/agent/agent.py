"""Single-node LangGraph: a companion snapshot in, one validated tool plan out."""
import asyncio
from typing import TypedDict

from databricks_agentkit.langgraph import configure_tracing, start_trace
from langgraph.graph import StateGraph, START, END

from agent.plan import decide, validate_snapshot


class PlanState(TypedDict):
    snapshot: dict
    tools: list
    result: dict


def configure():
    from pathlib import Path

    from magneto_platform import ServiceConfig, Services

    Services(ServiceConfig.load(Path(__file__).resolve().parents[1] / 'services.toml')).configure_tracing()
    configure_tracing()


async def _plan_node(state):
    return {'result': await asyncio.to_thread(decide, state['snapshot'], state['tools'])}


builder = StateGraph(PlanState)
builder.add_node('plan', _plan_node)
builder.add_edge(START, 'plan')
builder.add_edge('plan', END)
# Stateless and self-contained: no checkpointer and no memory tools.
graph = builder.compile()


async def run_agent(snapshot, tools, *, session_id):
    validate_snapshot(snapshot)
    if snapshot['session_id'] != session_id:
        raise ValueError('Invocation session does not match snapshot')
    with start_trace(name='magneto_companion_plan', inputs={'snapshot': snapshot, 'tools': tools},
                     session_id=session_id) as span:
        import mlflow
        mlflow.update_current_trace(client_request_id=snapshot['request_id'])
        result = (await graph.ainvoke({'snapshot': snapshot, 'tools': tools}))['result']
        if span is not None:
            span.set_outputs(result)
            span.set_attributes({'model': result['model'], 'elapsed_ms': result['elapsed_ms'],
                                 'request_id': result['request_id'], 'tool': result['plan']['tool']})
        return result
