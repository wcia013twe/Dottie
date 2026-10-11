import copy
import unittest
from magneto_research.evidence import (extracted_findings, guidance_v1, prepared_chunks,
                                      recommendation, source_metadata)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.parsed = {'document': {'pages': [{'id': 0}, {'id': 1}]}, 'error_status': []}
        self.prepared = {'document': {'contents': [{'chunk_to_retrieve': 'Participants completed task A.',
            'chunk_to_embed': 'Context: example\nParticipants completed task A.',
            'pages': [{'page_id': 1}]}]}}
        self.finding = {'statement': 'Task A was completed.', 'quote': 'completed task A',
                        'context': 'Participants; other context not reported.', 'limitations': 'No comparator.'}
        self.rec = {'text': 'Consider task A.', 'finding_ids': ['finding-1'],
                    'rationale': 'A proposal, not a tested individual benefit.', 'limitations': 'Indirect evidence.',
                    'target_letters': ['A'], 'difficulty_tags': ['recognition']}

    def test_search_enrichment_is_not_citation_text(self):
        chunk = prepared_chunks(self.parsed, self.prepared)[0]
        self.assertNotEqual(chunk['text'], chunk['embedding_text'])
        self.assertEqual(chunk['locator'], 'PDF page(s) 2')

    def test_partial_parse_cannot_be_published(self):
        self.parsed['error_status'] = [{'page_id': 1, 'error_message': 'unreadable'}]
        with self.assertRaises(ValueError): prepared_chunks(self.parsed, self.prepared)

    def test_missing_or_invented_pages_fail(self):
        for pages in ([], [{'page_id': 30}], [{'page_id': True}]):
            self.prepared['document']['contents'][0]['pages'] = pages
            with self.assertRaises(ValueError): prepared_chunks(self.parsed, self.prepared)

    def test_invented_quote_fails(self):
        with self.assertRaises(ValueError):
            extracted_findings({'response': {'findings': [self.finding]}}, 'Different source')

    def test_valid_quote_and_no_findings_are_distinct_from_failure(self):
        self.assertEqual(len(extracted_findings({'response': {'findings': [self.finding]}},
                                                'Participants completed task A.')), 1)
        self.assertEqual(extracted_findings({'response': {'findings': []}}, 'No evidence'), [])
        with self.assertRaises(ValueError): extracted_findings({'error_message': 'failed'}, 'No evidence')

    def test_model_cannot_add_approval(self):
        self.finding['approved'] = True
        with self.assertRaises(ValueError):
            extracted_findings({'response': {'findings': [self.finding]}}, 'Participants completed task A.')

    def test_wrapped_quote_is_resolved_to_original_bytes(self):
        self.finding['quote'] = "students' knowledge improved"
        original = 'The students’ knowledge\nimproved during the task.'
        result = extracted_findings({'response': {'findings': [self.finding]}}, original)
        self.assertEqual(result[0]['quote'], 'students’ knowledge\nimproved')
        self.assertIn(result[0]['quote'], original)

    def test_guidance_projection_preserves_contract(self):
        item = {'id': 'rec-1', 'collection': 'teaching', 'body': self.rec}
        source = {'source_id': 'paper', 'title': 'Paper', 'uri': 'https://example.org/paper'}
        guidance = guidance_v1(item, [source], ['PDF page(s) 2'])
        self.assertEqual(set(guidance), {'schema_version', 'guidance_id', 'text', 'target_letters',
            'difficulty_tags', 'source_id', 'citation', 'approved'})
        self.assertEqual(guidance['citation']['locator'], 'PDF page(s) 2')
        for collection, sources in [('industry', [source]), ('teaching', [source, source])]:
            item['collection'] = collection
            with self.assertRaises(ValueError): guidance_v1(item, sources, ['page 2'])

    def test_untargeted_recommendation_stays_internal(self):
        self.rec['target_letters'] = []
        recommendation(self.rec)
        with self.assertRaises(ValueError):
            guidance_v1({'id': 'r', 'collection': 'teaching', 'body': self.rec}, [], [])

    def test_duplicate_evidence_and_invalid_tags_rejected(self):
        for field, value in [('finding_ids', ['a', 'a']), ('target_letters', ['AB']),
                             ('difficulty_tags', ['diagnosis'])]:
            data = copy.deepcopy(self.rec)
            data[field] = value
            with self.assertRaises(ValueError): recommendation(data)

    def test_synthetic_sources_cannot_enter_cloud(self):
        meta = {'source_id': 'synthetic', 'collection': 'teaching', 'title': 'Synthetic',
                'publisher': 'Test', 'uri': 'fixture', 'rights_basis': 'test',
                'publication_date': None, 'acquired_date': '2026-10-11',
                'valid_until': None, 'synthetic': True}
        with self.assertRaises(ValueError): source_metadata(meta)


if __name__ == '__main__': unittest.main()
