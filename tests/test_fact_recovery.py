"""A correction must pass independent review before anything is rendered."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import content_pipeline as pipeline
from test_automation import sample_content


class FactRecoveryTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {'GITHUB_ACTIONS': 'test', 'GAJEONSO_DURABLE_GIT': '0'})
        env.start()
        self.addCleanup(env.stop)

    def exercise(self, verdicts):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'automation').mkdir()
            (root / 'automation/content_prompt.md').write_text('brand')
            (root / 'log').mkdir()
            (root / 'log/ig-card-news-log.md').write_text('history')
            replies = [sample_content()] + [sample_content() for _ in verdicts[1:]]
            with patch.object(pipeline, 'ROOT', root), \
                 patch.object(pipeline, 'recent_sources', return_value=([], [])), \
                 patch.object(pipeline, 'response', side_effect=replies) as response, \
                 patch.object(pipeline, 'recheck', return_value=[{'text': 'official'}]) as recheck, \
                 patch.object(pipeline, 'review_facts', side_effect=verdicts) as review, \
                 patch.object(pipeline, 'render_content', return_value='rendered') as render:
                if verdicts[-1]['passed']:
                    self.assertEqual(pipeline.prepare_content('20261011'), 'rendered')
                    render.assert_called_once()
                    self.assertEqual(render.call_args.args[2], verdicts[-1])
                else:
                    with self.assertRaisesRegex(ValueError, 'Fact QA rejected'):
                        pipeline.prepare_content('20261011')
                    render.assert_not_called()
                self.assertEqual(recheck.call_count, len(verdicts))
                self.assertEqual(review.call_count, len(verdicts))
                self.assertEqual(response.call_count, len(verdicts))
                feedback = json.loads(response.call_args.args[0][1]['content'])
                self.assertEqual(feedback['issues'], ['적용 모델 확인 필요'])
                self.assertEqual(len(list((root / 'out/20261011').glob('fact-qa-*.json'))), len(verdicts))

    def test_revision_is_rechecked_and_only_passed_draft_is_rendered(self):
        self.exercise([{'passed': False, 'issues': ['적용 모델 확인 필요']},
                       {'passed': True, 'issues': []}])

    def test_three_rejections_stop_without_rendering(self):
        self.exercise([{'passed': False, 'issues': ['적용 모델 확인 필요']}] * 3)

    def test_format_revision_still_requires_fact_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'automation').mkdir()
            (root / 'automation/content_prompt.md').write_text('brand')
            (root / 'log').mkdir()
            (root / 'log/ig-card-news-log.md').write_text('history')
            bad = sample_content()
            bad['deck']['cards'][0]['subtitle'] = '가' * 21
            good = sample_content()
            with patch.object(pipeline, 'ROOT', root), \
                 patch.object(pipeline, 'recent_sources', return_value=([], [])), \
                 patch.object(pipeline, 'response', side_effect=[bad, good]), \
                 patch.object(pipeline, 'recheck', return_value=[]) as recheck, \
                 patch.object(pipeline, 'review_facts', return_value={'passed': True, 'issues': []}) as review, \
                 patch.object(pipeline, 'render_content') as render:
                pipeline.prepare_content('20261011')
                recheck.assert_called_once()
                review.assert_called_once_with(good, [])
                self.assertEqual(render.call_args.args[1], good)
