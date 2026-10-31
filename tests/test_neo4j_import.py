import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'import_neo4j_from_spark.py'
spec = importlib.util.spec_from_file_location('import_neo4j_from_spark', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / 'data'
        self.data.mkdir()
        rows = {
            'publications.csv': [{'canonical_id':'doi:10.1234/x','title':'Example','year':'2024','doi':'10.1234/x','abstract':'A','pdf_url':''}],
            'publication_authors.csv': [{'author_occurrence_id':'hash1','canonical_id':'doi:10.1234/x','author_order':'0','author_name':'Doe'}],
            'chunks.csv': [{'chunk_id':'x_p1_c1','document_id':'doc_1','page_number':'1','text':'Scientific text'}],
        }
        for name, values in rows.items():
            self.write_csv(name,values)
        self.report = self.root/'report.json'
        self.report.write_text(json.dumps({'status':'OK','publications':{'output_rows':1},'chunks':{'output_rows':1},'outputs':{'publication_author_mentions':1}}),encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def write_csv(self,name,rows):
        with (self.data/name).open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=mod.EXPECTED[name]);w.writeheader();w.writerows(rows)

    def test_valid(self):
        result = mod.validated_tables(self.data,self.report)
        self.assertEqual(len(result['chunks.csv']),1)

    def test_spark_escaped_quotes_and_multiline_text(self):
        # Spark ecrit les guillemets comme \" et peut conserver des retours a la ligne.
        path = self.data/'chunks.csv'
        path.write_text(
            'chunk_id,document_id,page_number,text\n'
            'c1,doc_1,1,"A \\"quoted\\" term, a comma,\nand a second line"\n',
            encoding='utf-8',
        )
        rows = mod.validated_tables(self.data, self.report)['chunks.csv']
        self.assertEqual(len(rows), 1)
        self.assertIn('"quoted"', rows[0]['text'])
        self.assertIn('second line', rows[0]['text'])
        self.assertNotIn(None, rows[0])

    def test_reject_extra_csv_columns_before_db(self):
        path = self.data/'chunks.csv'
        path.write_text(
            'chunk_id,document_id,page_number,text\n'
            'c1,doc_1,1,hello,EXTRA\n', encoding='utf-8'
        )
        with self.assertRaisesRegex(ValueError, 'mal decoupe'):
            mod.validated_tables(self.data, self.report)

    def test_reject_missing_csv_cell_before_db(self):
        path = self.data/'chunks.csv'
        path.write_text(
            'chunk_id,document_id,page_number,text\n'
            'c1,doc_1,1\n', encoding='utf-8'
        )
        with self.assertRaisesRegex(ValueError, 'incomplet'):
            mod.validated_tables(self.data, self.report)

    def test_missing_csv(self):
        (self.data/'chunks.csv').unlink()
        with self.assertRaisesRegex(ValueError,'manquant'):
            mod.validated_tables(self.data,self.report)

    def test_duplicate_publication(self):
        row={'canonical_id':'doi:10.1234/x','title':'Example','year':'2024','doi':'10.1234/x','abstract':'A','pdf_url':''}
        self.write_csv('publications.csv',[row,row])
        with self.assertRaisesRegex(ValueError,'dupliques'):
            mod.validated_tables(self.data,self.report)

    def test_orphan_author(self):
        self.write_csv('publication_authors.csv',[{'author_occurrence_id':'hash1','canonical_id':'missing','author_order':'0','author_name':'Doe'}])
        with self.assertRaisesRegex(ValueError,'orphelin'):
            mod.validated_tables(self.data,self.report)

    def test_bad_page(self):
        self.write_csv('chunks.csv',[{'chunk_id':'x','document_id':'doc','page_number':'0','text':'hi'}])
        with self.assertRaisesRegex(ValueError,'page'):
            mod.validated_tables(self.data,self.report)

    def test_status_required(self):
        self.report.write_text(json.dumps({'status':'FAILED'}),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'status'):
            mod.validated_tables(self.data,self.report)

    def test_report_counts(self):
        self.report.write_text(json.dumps({'status':'OK','publications':{'output_rows':9},'chunks':{'output_rows':1},'outputs':{'publication_author_mentions':1}}),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'volumes'):
            mod.validated_tables(self.data,self.report)

    def test_batches(self):
        self.assertEqual(list(mod.chunks_of([1,2,3,4,5],2)),[[1,2],[3,4],[5]])

if __name__=='__main__': unittest.main()
