"""Meaningful unattended-publication checks. No model calls or book text exports."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import daily
import engine


class PublishingChecks(unittest.TestCase):
    def setUp(self):
        self.history=engine.read_json(engine.AUTO/'history.json')
        self.saved=self.history[-1]
        self.post=copy.deepcopy(self.saved)
        self.sources=[{**s,'text':'Context. '+s['quote']+' More context.'} for s in self.post.pop('sources')]
        self.post['quotes']=[{'source_index':i,'text':s['quote']} for i,s in enumerate(self.sources)]

    def test_real_post_passes_deterministic_checks(self):
        daily.validate(self.post,self.sources,[])

    def test_fabricated_quote_is_blocked(self):
        self.post['quotes'][0]['text']='These invented words do not appear in the original book.'
        with self.assertRaisesRegex(ValueError,'verbatim'):
            daily.validate(self.post,self.sources,[])

    def test_quote_assigned_to_wrong_book_is_blocked(self):
        self.post['quotes'][0]['source_index']=1
        self.post['quotes'][1]['source_index']=0
        with self.assertRaisesRegex(ValueError,'verbatim'):
            daily.validate(self.post,self.sources,[])

    def test_overlong_quote_is_blocked(self):
        self.post['quotes'][0]['text']=' '.join(['word']*21)
        self.sources[0]['text']=self.post['quotes'][0]['text']
        with self.assertRaisesRegex(ValueError,'6-20'):
            daily.validate(self.post,self.sources,[])

    def test_recycled_quote_is_blocked(self):
        previous=copy.deepcopy(self.saved)
        previous['title']='Different title'
        previous['topic']='Different topic'
        with self.assertRaisesRegex(ValueError,'Previously published quotation'):
            daily.validate(self.post,self.sources,[previous])

    def test_clinical_instructions_are_blocked(self):
        self.post['paragraphs'][0]+=' Change your medication dosage.'
        with self.assertRaisesRegex(ValueError,'Clinical advice'):
            daily.validate(self.post,self.sources,[])

    def test_render_escapes_model_text(self):
        self.saved['title']='<script>alert(1)</script>'
        rendered=daily.render_post(self.saved)
        self.assertNotIn('<script>alert(1)</script>',rendered)
        self.assertIn('&lt;script&gt;',rendered)

    def test_failed_render_restores_previous_pages_and_history(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'posts').mkdir()
            auto=root/'.automation'
            auto.mkdir()
            for name in ['index.html','archive.html','about.html','sources.html','feed.xml']:
                (root/name).write_text('previous version',encoding='utf-8')
            with patch.object(daily,'ROOT',root),patch.object(daily,'AUTO',auto),patch.object(daily,'render_site',side_effect=ValueError('failed render')):
                with self.assertRaisesRegex(ValueError,'failed render'):
                    daily.save_post(self.saved,[])
            self.assertEqual(list((root/'posts').iterdir()),[])
            self.assertFalse((auto/'history.json').exists())
            self.assertEqual((root/'index.html').read_text(),'previous version')


if __name__=='__main__':
    unittest.main()
