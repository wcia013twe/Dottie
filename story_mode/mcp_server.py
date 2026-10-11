"""Real MCP stdio server. All tools use the live viewer's authoritative controller."""
import json
import os
from typing import Literal
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from mcp.server.fastmcp import FastMCP

mcp = FastMCP('Magneto Story Mode')

def bridge(name, session_id, revision=None, **arguments):
    payload=json.dumps({'name':name,'session_id':session_id,'revision':revision,'arguments':arguments}).encode()
    request=Request(os.environ['MAGNETO_STORY_URL']+'/api/story/mcp', data=payload,
                    headers={'Content-Type':'application/json','X-Story-Key':os.environ['MAGNETO_STORY_KEY']})
    try:
        with urlopen(request,timeout=5) as response:return json.load(response)
    except HTTPError as exc:
        raise ValueError(json.load(exc).get('error','Story tool rejected')) from None

@mcp.tool()
def get_story_context(session_id: str) -> dict:
    """Read current passage, approved targets, teacher observations, policy, revision and hardware status."""
    return bridge('get_story_context',session_id)

@mcp.tool()
def propose_activity(session_id: str, revision: int, activity: Literal['introduce','identify','match'], target: str, prompt: str, hint: str, reason: str) -> dict:
    """Propose one approved letter/word activity for teacher review. No speech or hardware action. Reason is a brief evidence summary, not private reasoning."""
    return bridge('propose_activity',session_id,revision,activity=activity,target=target,prompt=prompt,hint=hint,reason=reason)

@mcp.tool()
def recommend_continue(session_id: str, revision: int, reason: str) -> dict:
    """Recommend continuing without an activity. Teacher decides whether to resume."""
    return bridge('recommend_continue',session_id,revision,reason=reason)

@mcp.tool()
def prepare_braille(session_id: str, revision: int) -> dict:
    """After teacher approval, prepare deterministic Braille cells. Preview only; never claims physical readiness."""
    return bridge('prepare_braille',session_id,revision)

@mcp.tool()
def speak_prompt(session_id: str, revision: int) -> dict:
    """After teacher confirms tactile material, queue the approved learner prompt. Browser speech is a separate adapter."""
    return bridge('speak_prompt',session_id,revision)

@mcp.tool()
def give_hint(session_id: str, revision: int) -> dict:
    """Queue the approved hint while waiting for a response; mark subsequent observation as assisted."""
    return bridge('give_hint',session_id,revision)

@mcp.tool()
def submit_response(session_id: str, revision: int, text: str) -> dict:
    """Capture an UNCONFIRMED response transcript; never grade it or establish mastery."""
    return bridge('submit_response',session_id,revision,text=text)

@mcp.tool()
def propose_word_emphasis(session_id: str, revision: int, activity: Literal['emphasize'], target: str, prompt: str, hint: str, reason: str) -> dict:
    """Propose exploring an approved story keyword letter by letter on one cell. Exposure, not a recognition assessment. No hardware execution."""
    return bridge('propose_word_emphasis',session_id,revision,activity=activity,target=target,prompt=prompt,hint=hint,reason=reason)

@mcp.tool()
def prepare_word_sequence(session_id: str, revision: int) -> dict:
    """After educator approval, prepare ordered Braille cells and bounded timing for the keyword. Preview only; no serial writes or physical-ready claim."""
    return bridge('prepare_word_sequence',session_id,revision)

if __name__=='__main__':mcp.run(transport='stdio')
