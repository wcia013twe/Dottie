import sys
import json
from unittest.mock import patch
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from learning_bridge import LearningError, validate_batch, validate_profile, validate_attempts, ingest_attempts


def event(profile=None):
    profile = profile or str(uuid4())
    return {
        'schema_version': '2.0', 'event_id': str(uuid4()), 'profile_id': profile,
        'session_id': str(uuid4()), 'occurred_at': '2026-10-11T12:00:00Z',
        'event_type': 'response_recorded', 'activity_id': 'tuesday_pear',
        'target': 'P', 'outcome': 'incorrect', 'client_sequence': 0,
        'metadata': {'source': 'browser'},
    }


class LearningBridgeTests(unittest.TestCase):
    def test_accepts_batch_for_one_profile(self):
        payload = {'schema_version': '2.0', 'events': [event()]}
        self.assertIs(validate_batch(payload), payload)

    def test_rejects_mixed_profiles(self):
        first = event()
        with self.assertRaises(LearningError):
            validate_batch({'schema_version': '2.0', 'events': [first, event(str(uuid4()))]})

    def test_rejects_unknown_metadata(self):
        value = event()
        value['metadata'] = {'source': 'browser', 'raw_text': 'not allowed'}
        with self.assertRaises(LearningError):
            validate_batch({'schema_version': '2.0', 'events': [value]})

    def test_validates_profile_consent_and_preferences(self):
        profile = {'schema_version': '2.0', 'profile_id': str(uuid4()), 'consent': 'granted', 'preferences': {'audio_enabled': False}}
        self.assertIs(validate_profile(profile), profile)
        profile['preferences']['unexpected'] = True
        with self.assertRaises(LearningError):
            validate_profile(profile)

    def test_attempts_use_the_same_validator_as_the_cloud(self):
        payload = json.loads((ROOT / 'databricks/contracts/v3/examples/rabbit-session.json').read_text())
        self.assertIs(validate_attempts(payload), payload)
        payload['attempts'][0]['raw_audio'] = 'not collected'
        with self.assertRaises(LearningError):
            validate_attempts(payload)

    def test_mismatched_ack_is_not_forwarded(self):
        payload = json.loads((ROOT / 'databricks/contracts/v3/examples/rabbit-session.json').read_text())
        with patch('learning_bridge._invoke', return_value={'schema_version':'3.0','profile_id':payload['profile_id'],'session_id':str(uuid4()),'attempt_ids':[payload['attempts'][0]['attempt_id']]}):
            with self.assertRaises(LearningError):
                ingest_attempts(payload)


if __name__ == '__main__':
    unittest.main()
