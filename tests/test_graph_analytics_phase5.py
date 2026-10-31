import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from graph_analytics_phase5 import calculate_metrics


def fixture():
    pubs=[{'canonical_id':'p1','title':'First','year':2024,'doi':'x'}, {'canonical_id':'p2','title':'Second','year':2025,'doi':''}]
    authors=[{'author_occurrence_id':'a1'}, {'author_occurrence_id':'a2'}]
    docs=[{'document_id':'d1'}]
    chunks=[{'chunk_id':'c1','document_id':'d1','page_number':2,'text':'ab'},
            {'chunk_id':'c2','document_id':'d1','page_number':2,'text':'abcd'}]
    author_links=[('p1','a1'),('p1','a2')]
    chunk_links=[('d1','c1'),('d1','c2')]
    return pubs,authors,docs,chunks,author_links,chunk_links

class TestGraphAnalytics(unittest.TestCase):
    def test_counts(self):
        x=calculate_metrics(*fixture())['summary']
        self.assertEqual(x['total_nodes'],7)
        self.assertEqual(x['total_relations'],4)
    def test_components(self):
        x=calculate_metrics(*fixture())['summary']
        self.assertEqual(x['components'],3)
        self.assertEqual(x['isolated_nodes'],1)
    def test_author_ranking(self):
        x=calculate_metrics(*fixture())
        self.assertEqual(x['publications'][0]['author_mentions'],2)
    def test_page_stats(self):
        x=calculate_metrics(*fixture())
        self.assertEqual(x['documents'][0]['pages_represented'],1)
        self.assertEqual(x['documents'][0]['avg_chunk_chars'],3)
    def test_no_duplicate_nodes(self):
        d=list(fixture());d[0].append(dict(d[0][0]))
        with self.assertRaises(ValueError):calculate_metrics(*d)
    def test_orphan_author_link(self):
        d=list(fixture());d[4].append(('p9','a2'))
        with self.assertRaises(ValueError):calculate_metrics(*d)
    def test_no_duplicate_links(self):
        d=list(fixture());d[5].append(('d1','c1'))
        with self.assertRaises(ValueError):calculate_metrics(*d)
    def test_chunk_provenance(self):
        d=list(fixture());d[3][0]['document_id']='d2'
        with self.assertRaises(ValueError):calculate_metrics(*d)
    def test_orphan_chunk(self):
        d=list(fixture());d[5].pop()
        with self.assertRaises(ValueError):calculate_metrics(*d)
    def test_no_fake_community_claim(self):
        x=calculate_metrics(*fixture())['summary']['interpretation']
        self.assertIn('ne mesure',x)

if __name__=='__main__':unittest.main()
