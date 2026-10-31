"""Focused V3.2 checks: evidence enums, scientific safeguards, model-isolated paths."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import extract_scientific_knowledge_v32 as m

PASSAGE='We evaluated Retriever on NaturalQuestions using exact match.'

class V32Tests(unittest.TestCase):
    def test_entity_schema_restricts_provenance_ids(self):
        schema=m.entity_schema({'P1':PASSAGE,'P2':'other'})
        props=schema['properties']['entities']['items']['properties']
        self.assertEqual(props['evidence_id']['enum'],['P1','P2'])
        self.assertIn('DATASET',props['type']['enum'])
        self.assertFalse(schema['properties']['entities']['items']['additionalProperties'])

    def test_entity_schema_rejects_empty_windows(self):
        with self.assertRaises(ValueError):m.entity_schema({})

    def test_constrain_both_extraction_stages(self):
        replies=iter([
            {'entities':[{'name':'Retriever','type':'MODEL','evidence_id':'P1'},
                         {'name':'NaturalQuestions','type':'DATASET','evidence_id':'P1'}]},
            {'relations':[{'subject_id':'E1','object_id':'E2','predicate':'EVALUATED_ON','evidence_id':'P1'}]}
        ])
        schemas=[]
        def respond(base,model,schema,prompt,timeout):
            schemas.append(schema)
            return next(replies)
        with patch.object(m.v3,'chat_structured',side_effect=respond):
            result=m.extract_chunk('http://127.0.0.1:11434','mock', {'text':PASSAGE,'title':'P'},5)
        self.assertEqual(len(result['entities']),2)
        self.assertEqual(len(result['relations']),1)
        ids=schemas[0]['properties']['entities']['items']['properties']['evidence_id']['enum']
        self.assertEqual(ids,['P1'])
        rids=schemas[1]['properties']['relations']['items']['properties']['subject_id']['enum']
        self.assertEqual(rids,['E1','E2'])

    def test_invalid_evidence_still_rejected_by_validator(self):
        result=m.v3.validate_entities({'entities':[{'name':'Retriever','type':'MODEL','evidence_id':'P999'}]}, {'P1':PASSAGE})
        self.assertEqual(result['rejected_entities'][0]['reason'],'unknown_evidence_id')

    def test_invalid_type_and_cooccurrence_still_rejected(self):
        e=[{'id':'E1','name':'NaturalQuestions','type':'DATASET'}, {'id':'E2','name':'Retriever','type':'MODEL'}]
        r=m.v3.validate_relations({'relations':[{'subject_id':'E1','object_id':'E2','predicate':'EVALUATED_ON','evidence_id':'P1'}]},e,{'P1':PASSAGE})
        self.assertEqual(r['rejected_relations'][0]['reason'],'invalid_types_or_direction')

    def test_output_paths_distinct(self):
        p3=m.output_paths('qwen2.5:3b')
        p7=m.output_paths('qwen2.5:7b')
        self.assertEqual(len(p7),3)
        self.assertTrue(all(a != b for a,b in zip(p3,p7)))
        self.assertIn('qwen2_5_7b',str(p7[0]))

if __name__=='__main__': unittest.main()
