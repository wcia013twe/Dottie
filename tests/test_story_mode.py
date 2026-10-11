import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from story_mode.controller import Controller, StoryError
from story_mode.selection import decision_context, allowed_tools
from story_mode.preparation import Preparation

class StoryTests(unittest.TestCase):
    def setUp(self):
        self.c=Controller();self.s=self.c.create();self.call('set_context',{'passage_id':'rabbit'},'teacher')
    def call(self,name,args=None,actor='orchestrator'):
        self.s=self.c.call(self.s['session_id'],self.s['revision'],name,args,actor=actor);return self.s
    def propose(self,target='r'):
        return self.call('propose_activity',{'activity':'identify','target':target,'prompt':'Feel the letter. What is it?','hint':'Find the middle dot on the right.','reason':'Offer a brief recognition activity at this story moment.'})
    def start(self):
        self.propose();self.call('approve_activity',actor='teacher');self.call('prepare_braille');self.call('confirm_tactile',actor='teacher');self.call('speak_prompt')
    def test_stale_navigation_cannot_start_activity(self):
        old=self.s['revision'];self.call('set_context',{'passage_id':'gate'},'teacher')
        with self.assertRaises(StoryError):self.c.call(self.s['session_id'],old,'recommend_continue',{'reason':'old'})
    def test_model_cannot_confirm_tactile_or_grade(self):
        self.propose()
        with self.assertRaises(StoryError):self.call('approve_activity')
        self.call('approve_activity',actor='teacher');self.call('prepare_braille')
        with self.assertRaises(StoryError):self.call('confirm_tactile')
        with self.assertRaises(StoryError):self.call('speak_prompt')
        self.assertFalse(self.s['device']['ready']);self.assertFalse(self.s['braille']['physical_ready'])
    def test_transcript_is_not_a_score(self):
        self.start();self.call('submit_response',{'text':'are'})
        self.assertEqual(self.s['observations'],[])
        with self.assertRaises(StoryError):self.call('record_observation',{'outcome':'independent'})
        self.call('record_observation',{'outcome':'independent'},'teacher')
        self.assertEqual(self.s['observations'][0]['target'],'r')
    def test_hint_requires_assisted_observation(self):
        self.start();self.call('give_hint')
        with self.assertRaises(StoryError):self.call('record_observation',{'outcome':'independent'},'teacher')
        self.call('record_observation',{'outcome':'with_help'},'teacher')
    def test_word_cells_and_letter_are_distinct(self):
        self.propose('rabbit');self.call('approve_activity',actor='teacher');self.call('prepare_braille')
        self.assertEqual(len(self.s['braille']['cells']),6)
        self.assertEqual(self.s['braille']['cells'][0]['dots'],[1,2,3,5])
    def test_target_guard_and_atomic_error(self):
        before=self.c.get(self.s['session_id'])
        with self.assertRaises(StoryError):self.propose('z')
        self.assertEqual(before,self.c.get(self.s['session_id']))
    def test_navigation_clears_activity_but_keeps_observations(self):
        self.start();self.call('record_observation',{'outcome':'with_help'},'teacher')
        self.call('set_context',{'passage_id':'lettuce'},'teacher')
        self.assertEqual(self.s['phase'],'reading');self.assertIsNone(self.s['proposal']);self.assertNotIn('speech',self.s)
        self.assertEqual(self.s['observations'][0]['outcome'],'with_help')
    def test_selection_context_excludes_unrelated_and_private_state(self):
        state=self.c.sessions[self.s['session_id']]
        state['observations']=[{'id':str(i),'target':'r','source':'teacher',
            'outcome':'with_help','activity':'identify','hint_used':True,'passage_id':'rabbit'} for i in range(10)]
        state['observations'] += [{'target':'g','source':'teacher'}, {'target':'r','source':'transcript'}]
        state['response']={'text':'Private unconfirmed transcript'}
        context=decision_context(self.c.get(self.s['session_id']))
        self.assertEqual([o['id'] for o in context['observations']],['6','7','8','9'])
        self.assertEqual(context['observations_omitted'],6)
        self.assertNotIn('response',context)
        self.assertNotIn('trace',context)
        self.assertNotIn('device',context)
        self.assertEqual(allowed_tools(context),{'propose_activity','recommend_continue','propose_word_emphasis'})

    def test_selection_is_unavailable_during_an_activity(self):
        self.start()
        with self.assertRaises(ValueError):decision_context(self.s)

    def test_budget(self):
        self.c.sessions[self.s['session_id']]['activities_started']=6
        with self.assertRaises(StoryError):self.propose()
        self.call('recommend_continue',{'reason':'The activity limit has been reached.'})

    def test_persona_is_opt_in_and_never_seeded_as_outcomes(self):
        self.assertNotIn('synthetic_persona',self.s)
        self.s=self.c.create(synthetic_persona_id='alex-morgan')
        self.assertTrue(self.s['synthetic_persona']['synthetic'])
        self.assertEqual(self.s['observations'],[])
        self.call('set_context',{'passage_id':'rabbit'},'teacher')
        self.assertEqual(self.s['synthetic_persona']['display_name'],'Alex Morgan')
        with self.assertRaises(ValueError):self.c.create(synthetic_persona_id='../../live')

    def test_synthetic_follow_up_cannot_grade_or_skip_approval(self):
        self.s=self.c.create(synthetic_persona_id='alex-morgan')
        self.call('set_context',{'passage_id':'rabbit'},'teacher')
        self.start();self.call('submit_response',{'text':'I am confused.'})
        self.propose()
        self.assertEqual(self.s['phase'],'proposed')
        self.assertEqual(self.s['observations'],[])
        self.assertIsNone(self.s['response'])
        self.assertNotIn('braille',self.s)
        with self.assertRaises(StoryError):self.call('speak_prompt')

    def test_real_session_rejects_unconfirmed_follow_up(self):
        self.start();self.call('submit_response',{'text':'I am confused.'})
        with self.assertRaises(StoryError):self.propose()
class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.c=Controller();self.s=self.c.create()
        self.s=self.c.call(self.s['session_id'],0,'set_context',{'passage_id':'rabbit'},actor='teacher')
        self.p=Preparation(self.c)
        self.plan={'tool':'recommend_continue','arguments':{'session_id':self.s['session_id'],
            'revision':self.s['revision'],'reason':'Synthetic test recommendation.'}}
    def begin(self):return self.p.begin(self.s['session_id'],self.s['revision'])
    def finish(self,ticket):return self.p.finish(self.s['session_id'],ticket,self.plan,{})
    def test_prepare_does_not_mutate_lesson_and_apply_is_once_only(self):
        ticket,needed=self.begin();self.assertTrue(needed)
        self.finish(ticket);self.assertEqual(self.c.get(self.s['session_id']),self.s)
        cached,needed=self.begin();self.assertFalse(needed)
        result=self.p.apply(self.s['session_id'],self.s['revision'],cached['preparation_id'])
        self.assertEqual(result['state']['phase'],'continue_proposed')
        with self.assertRaises(StoryError):self.p.apply(self.s['session_id'],self.s['revision'],cached['preparation_id'])
    def test_inflight_duplicate_is_rejected_and_failure_allows_retry(self):
        ticket,_=self.begin()
        with self.assertRaises(StoryError):self.begin()
        self.p.fail(self.s['session_id'],ticket)
        retry,needed=self.begin();self.assertTrue(needed)
        self.assertNotEqual(retry['preparation_id'],ticket['preparation_id'])
    def test_navigation_invalidates_ready_plan(self):
        ticket,_=self.begin();self.finish(ticket)
        changed=self.c.call(self.s['session_id'],self.s['revision'],'set_context',{'passage_id':'gate'},actor='teacher')
        with self.assertRaises(StoryError):self.p.apply(self.s['session_id'],self.s['revision'],ticket['preparation_id'])
        self.assertEqual(self.c.get(self.s['session_id']),changed)
    def test_late_completion_cannot_replace_new_preparation(self):
        old,_=self.begin()
        self.s=self.c.call(self.s['session_id'],self.s['revision'],'set_context',{'passage_id':'gate'},actor='teacher')
        new,_=self.begin()
        with self.assertRaises(StoryError):self.finish(old)
        self.assertEqual(self.p.entries[self.s['session_id']],new)
    def test_prepared_plan_cannot_invoke_teacher_tool(self):
        ticket,_=self.begin();self.plan['tool']='record_observation'
        with self.assertRaises(ValueError):self.finish(ticket)
        self.assertEqual(self.c.get(self.s['session_id']),self.s)

class WordEmphasisTests(unittest.TestCase):
    def setUp(self):
        self.c=Controller();self.s=self.c.create()
        self.s=self.c.call(self.s['session_id'],0,'set_context',{'passage_id':'rabbit'},actor='teacher')
    def call(self,name,args=None,actor='orchestrator'):
        self.s=self.c.call(self.s['session_id'],self.s['revision'],name,args,actor=actor);return self.s
    def proposal(self,target='rabbit'):
        return self.call('propose_word_emphasis',dict(activity='emphasize',target=target,prompt='Explore rabbit with Peter.',hint='Feel each letter.',reason='Story keyword exposure.'))
    def test_enabled_by_default_and_only_teacher_can_disable(self):
        self.assertIn('propose_word_emphasis',allowed_tools(decision_context(self.s)))
        with self.assertRaises(StoryError):self.call('set_word_emphasis',{'enabled':False})
        self.call('set_word_emphasis',{'enabled':False},'teacher')
        with self.assertRaises(StoryError):self.proposal()
    def test_approved_sequence_is_ordered_and_not_physical(self):
        self.call('set_word_emphasis',{'enabled':True},'teacher')
        self.assertIn('propose_word_emphasis',allowed_tools(decision_context(self.s)))
        self.proposal()
        with self.assertRaises(StoryError):self.call('prepare_word_sequence')
        self.call('approve_activity',actor='teacher');self.call('prepare_word_sequence')
        self.assertEqual(''.join(c['letter'] for c in self.s['braille']['cells']),'rabbit')
        self.assertEqual(self.s['braille']['sequence']['command'],'SPELL rabbit')
        self.assertFalse(self.s['braille']['physical_ready'])
    def test_single_letter_or_unapproved_keyword_rejected(self):
        self.call('set_word_emphasis',{'enabled':True},'teacher')
        for target in ['r','gate','rabbit; CLEAR']:
            with self.assertRaises(StoryError):self.proposal(target)
    def test_disable_clears_proposal_and_prepared_context(self):
        self.call('set_word_emphasis',{'enabled':True},'teacher');self.proposal()
        self.call('set_word_emphasis',{'enabled':False},'teacher')
        self.assertIsNone(self.s['proposal']);self.assertEqual(self.s['phase'],'reading')

class ReviewTests(unittest.TestCase):
    def row(self,outcome='with_help',activity='identify',day=1):
        from uuid import uuid4
        return dict(id=str(uuid4()),target='r',activity=activity,outcome=outcome,source='teacher',
                    hint_used=outcome=='with_help',observed_at=f'2026-01-{day:02d}T12:00:00+00:00',passage_id='rabbit')
    def test_due_schedule_and_task_separation(self):
        from story_mode.review import summarize
        from datetime import datetime,timezone
        rows=[self.row(),self.row('independent','match')]
        summary=summarize(rows,datetime(2026,1,2,13,tzinfo=timezone.utc))
        self.assertEqual(len(summary),2);self.assertTrue(all(r['due'] for r in summary))
        self.assertTrue(next(r for r in summary if r['activity']=='identify')['needs_support'])
        self.assertFalse(next(r for r in summary if r['activity']=='match')['needs_support'])
    def test_skips_dedupe_and_introduction_are_not_mastery(self):
        from story_mode.review import summarize
        row=self.row('independent','introduce')
        summary=summarize([row,row,self.row('try_later')])
        self.assertEqual(len(summary),1);self.assertEqual(summary[0]['observations'],1)
        self.assertIn('recognition not established',summary[0]['reason'])
    def test_repeated_independent_results_space_reviews(self):
        from story_mode.review import summarize
        summary=summarize([self.row('independent',day=1),self.row('independent',day=2)])
        self.assertTrue(summary[0]['review_due_at'].startswith('2026-01-05'))
    def test_history_load_filters_to_current_checkpoint_and_survives_new_session(self):
        c=Controller();s=c.create([self.row()]);s=c.call(s['session_id'],0,'set_context',{'passage_id':'gate'},actor='teacher')
        self.assertEqual(decision_context(s)['review_candidates'],[])
        s=c.call(s['session_id'],s['revision'],'set_context',{'passage_id':'rabbit'},actor='teacher')
        self.assertEqual(decision_context(s)['review_candidates'][0]['target'],'r')
        self.assertEqual(s['observations'],[])
    def test_bad_history_rejected(self):
        row=self.row();row['outcome']='independent'
        with self.assertRaises(ValueError):Controller().create([row])
        with self.assertRaises(ValueError):Controller().create([self.row()]*41)

class CheckpointMapTests(unittest.TestCase):
    def test_authored_anchors_match_bundled_edition(self):
        from story_mode.controller import CHECKPOINT_MAP, CATALOG
        from pathlib import Path
        from zipfile import ZipFile
        import xml.etree.ElementTree as ET
        root=Path(__file__).resolve().parents[1]
        with ZipFile(root/'web/learn/books/the-tale-of-peter-rabbit.epub') as archive:
            tree=ET.fromstring(archive.read(next(n for n in archive.namelist() if n.endswith('_14838-h-0.htm.xhtml'))))
        image_ids=[n.attrib['id'] for n in tree.iter() if n.tag.endswith('}img')]
        pages=CHECKPOINT_MAP['pages']
        self.assertEqual([p['source_image_id'] for p in pages],image_ids)
        self.assertEqual(len({p['id'] for p in pages}),len(pages))
        anchors={p['id']:p['source_image_id'] for p in pages}
        self.assertEqual(anchors[CATALOG['rabbit']['page_id']],'img_images_peter02.gif')
        self.assertEqual(anchors[CATALOG['gate']['page_id']],'img_images_peter19.jpg')
        self.assertEqual(anchors[CATALOG['lettuce']['page_id']],'img_images_peter20.jpg')
        for checkpoint in CATALOG.values():
            self.assertTrue(checkpoint['optional'])
            self.assertEqual(checkpoint['pause_at'],'after_narration')
            self.assertTrue(checkpoint['required_materials'])

class LookaheadTests(unittest.TestCase):
    def setUp(self):
        from story_mode.lookahead import Lookahead
        self.c=Controller();self.s=self.c.create();self.p=Lookahead(self.c)
        self.ticket,_=self.p.begin(self.s['session_id'],0,'rabbit')
        self.plan={'tool':'propose_activity','arguments':{'session_id':self.s['session_id'],'revision':0,
            'activity':'introduce','target':'r','prompt':'Help Peter find r.','hint':'Feel the dots.','reason':'A story connection.'}}
    def move(self,target):
        s=self.c.get(self.s['session_id'])
        return self.c.call(s['session_id'],s['revision'],'set_context',{'passage_id':target},actor='teacher')
    def test_projection_does_not_move_live_page_and_rebases_on_arrival(self):
        self.assertEqual(self.c.get(self.s['session_id']),self.s)
        self.p.finish(self.s['session_id'],self.ticket,self.plan,{'prompt':'cached'})
        s=self.move('rabbit')
        result=self.p.apply(s['session_id'],s['revision'],self.ticket['preparation_id'])
        self.assertEqual(result['state']['proposal']['target'],'r')
        self.assertEqual(result['interaction_audio'],{'prompt':'cached'})
        with self.assertRaises(StoryError):self.p.apply(s['session_id'],s['revision'],self.ticket['preparation_id'])
    def test_wrong_page_and_stale_revision_rejected(self):
        self.p.finish(self.s['session_id'],self.ticket,self.plan,{})
        s=self.move('gate')
        with self.assertRaises(StoryError):self.p.apply(s['session_id'],s['revision'],self.ticket['preparation_id'])
        s=self.move('rabbit')
        with self.assertRaises(StoryError):self.p.apply(s['session_id'],0,self.ticket['preparation_id'])
    def test_changed_evidence_rejects_prepared_plan(self):
        self.p.finish(self.s['session_id'],self.ticket,self.plan,{})
        s=self.move('rabbit')
        self.c.sessions[s['session_id']]['activities_started']+=1
        with self.assertRaises(StoryError):self.p.apply(s['session_id'],s['revision'],self.ticket['preparation_id'])
    def test_navigation_during_generation_allowed_but_new_observation_invalidates(self):
        self.move('rabbit')
        self.p.finish(self.s['session_id'],self.ticket,self.plan,{})
        self.assertEqual(self.p.entries[self.s['session_id']]['status'],'ready')
    def test_intervention_invalidates_inflight_even_after_resuming(self):
        self.move('rabbit')
        state=self.c.get(self.s['session_id'])
        state=self.c.call(state['session_id'],state['revision'],'resume_story',actor='teacher')
        with self.assertRaises(StoryError):self.p.finish(state['session_id'],self.ticket,self.plan,{})
    def test_one_inflight_and_failure_retry(self):
        with self.assertRaises(StoryError):self.p.begin(self.s['session_id'],0,'gate')
        self.p.fail(self.s['session_id'],self.ticket)
        _,needed=self.p.begin(self.s['session_id'],0,'gate');self.assertTrue(needed)
    def test_invalid_target_or_teacher_tool_rejected(self):
        with self.assertRaises(StoryError):self.p.begin(self.s['session_id'],0,'invented')
        self.plan['tool']='record_observation'
        with self.assertRaises(ValueError):self.p.finish(self.s['session_id'],self.ticket,self.plan,{})

if __name__=='__main__':unittest.main()
