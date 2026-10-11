"""Conservative practice scheduling, not a mastery assessment."""
from datetime import datetime, timedelta, timezone
from uuid import UUID

MAX_HISTORY = 40

def validate_history(rows, targets):
    if not isinstance(rows,list) or len(rows)>MAX_HISTORY: raise ValueError('Invalid practice history size.')
    seen=set()
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'id','target','activity','outcome','source','hint_used','observed_at','passage_id'}: raise ValueError('Invalid practice observation.')
        UUID(row['id'])
        date=datetime.fromisoformat(row['observed_at'].replace('Z','+00:00'))
        if date.tzinfo is None or date>datetime.now(timezone.utc)+timedelta(minutes=5):raise ValueError('Invalid observation time.')
        if (row['id'] in seen or row['target'] not in targets or row['activity'] not in ('introduce','identify','match','emphasize')
            or row['outcome'] not in ('independent','with_help','try_later') or row['source']!='teacher'
            or type(row['hint_used']) is not bool or not isinstance(row['passage_id'],str)
            or len(row['passage_id'])>100 or (row['outcome']=='independent' and row['hint_used'])):raise ValueError('Invalid practice evidence.')
        seen.add(row['id'])
    return rows

def summarize(rows, now=None):
    now=now or datetime.now(timezone.utc)
    unique={r['id']:r for r in rows if r.get('source')=='teacher' and r.get('observed_at') and r.get('id')}
    groups={}
    for row in sorted(unique.values(),key=lambda r:datetime.fromisoformat(r['observed_at'].replace('Z','+00:00'))):
        if row['outcome']=='try_later':continue  # Skip is not evidence of difficulty.
        groups.setdefault((row['target'],row['activity']),[]).append(row)
    result=[]
    for (target,activity),attempts in groups.items():
        recent=attempts[-5:];last=attempts[-1];streak=0
        for row in reversed(attempts):
            if row['outcome']!='independent':break
            streak+=1
        # Introductions are exposure, never evidence of independent recognition.
        days=1 if last['outcome']=='with_help' or activity in ('introduce','emphasize') else (1,3,7,14)[min(streak-1,3)]
        due=datetime.fromisoformat(last['observed_at'].replace('Z','+00:00'))+timedelta(days=days)
        helped=sum(r['outcome']=='with_help' for r in recent)
        reason=(f'Needed help in {helped} of {len(recent)} recent {activity} attempts.' if helped else
                'Word/letter exposure recorded; recognition not established.' if activity in ('introduce','emphasize') else
                f'{len(recent)} recent independent {activity} observations.')
        result.append(dict(target=target,activity=activity,reason=reason,review_due_at=due.isoformat(),
                           due=due<=now,needs_support=last['outcome']=='with_help',observations=len(recent)))
    return sorted(result,key=lambda r:(not r['due'],not r['needs_support'],r['review_due_at'],r['target'],r['activity']))
