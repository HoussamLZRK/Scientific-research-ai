"""V3.1 unit tests, using only simulated data. No local Ollama requests."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import extract_scientific_knowledge_v31 as m

PASSAGE='We evaluate the Retriever model on NaturalQuestions (NQ) using exact-match accuracy.'
ENTITIES=[{'id':'E1','name':'Retriever','type':'MODEL'},
          {'id':'E2','name':'NaturalQuestions','type':'DATASET'}]

class V31Tests(unittest.TestCase):
    def test_dynamic_schema_enums_only_actual_ids(self):
        schema=m.relation_schema(ENTITIES,{'P1':PASSAGE,'P2':'Next window'})
        props=schema['properties']['relations']['items']['properties']
        self.assertEqual(props['subject_id']['enum'],['E1','E2'])
        self.assertEqual(props['evidence_id']['enum'],['P1','P2'])
        self.assertFalse(schema['properties']['relations']['items']['additionalProperties'])

    def test_schema_rejects_empty(self):
        with self.assertRaises(ValueError):
            m.relation_schema([], {'P1':PASSAGE})

    def test_untouched_v3_validator_rejects_invalid_id(self):
        raw={'relations':[{'subject_id':'Retriever','predicate':'EVALUATED_ON',
                            'object_id':'E2','evidence_id':'P1'}]}
        result=m.v3.validate_relations(raw,ENTITIES,{'P1':PASSAGE})
        self.assertEqual(result['relations'],[])
        self.assertEqual(result['rejected_relations'][0]['reason'],'invalid_entity_ids')

    def test_untouched_v3_validator_rejects_wrong_direction(self):
        raw={'relations':[{'subject_id':'E2','predicate':'EVALUATED_ON',
                            'object_id':'E1','evidence_id':'P1'}]}
        result=m.v3.validate_relations(raw,ENTITIES,{'P1':PASSAGE})
        self.assertEqual(result['relations'],[])
        self.assertEqual(result['rejected_relations'][0]['reason'],'invalid_types_or_direction')

    def test_untouched_v3_validator_rejects_cooccurrence(self):
        raw={'relations':[{'subject_id':'E1','predicate':'EVALUATED_ON',
                            'object_id':'E2','evidence_id':'P1'}]}
        passage='Retriever and NaturalQuestions are listed in a paper bibliography.'
        result=m.v3.validate_relations(raw,ENTITIES,{'P1':passage})
        self.assertEqual(result['relations'],[])
        self.assertEqual(result['rejected_relations'][0]['reason'],
                         'no_single_sentence_with_both_entities_and_relation_cue')

    def test_two_stage_schema_is_sent_to_model(self):
        responses=iter([
            {'entities':[{'name':'Retriever','type':'MODEL','evidence_id':'P1'},
                         {'name':'NaturalQuestions','type':'DATASET','evidence_id':'P1'}]},
            {'relations':[{'subject_id':'E1','predicate':'EVALUATED_ON','object_id':'E2','evidence_id':'P1'}]}
        ])
        with patch.object(m.v3,'chat_structured',side_effect=lambda *a:next(responses)) as mock:
            result=m.extract_chunk('http://127.0.0.1:11434','mock',
                                   {'text':PASSAGE,'title':'Test paper'},5)
        self.assertEqual(len(result['relations']),1)
        used_schema=mock.call_args_list[1].args[2]
        enum=used_schema['properties']['relations']['items']['properties']['subject_id']['enum']
        self.assertEqual(enum,['E1','E2'])

    def test_no_model_relations_with_fewer_than_two_validated_entities(self):
        response={'entities':[{'name':'Retriever','type':'MODEL','evidence_id':'P1'}]}
        with patch.object(m.v3,'chat_structured',return_value=response) as mock:
            result=m.extract_chunk('http://127.0.0.1:11434','mock',
                                   {'text':PASSAGE,'title':'Test paper'},5)
        self.assertEqual(mock.call_count,1)
        self.assertEqual(result['relations'],[])

if __name__=='__main__':
    unittest.main()
