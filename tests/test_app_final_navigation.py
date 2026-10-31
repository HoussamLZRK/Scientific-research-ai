from pathlib import Path
import ast
import unittest

APP = Path(__file__).resolve().parents[1]/'app_final.py'

class NavigationTests(unittest.TestCase):
 def test_01_final_app_is_valid_python(self):
  ast.parse(APP.read_text(encoding='utf-8'))
 def test_02_assistant_in_main_navigation(self):
  text=APP.read_text(encoding='utf-8')
  self.assertIn("st.selectbox('Choisir une page de l’application'",text)
  self.assertIn("key='srai_main_navigation'",text)
  self.assertIn("'Assistant scientifique'",text)
 def test_03_sidebar_not_required_for_navigation(self):
  text=APP.read_text(encoding='utf-8')
  self.assertNotIn("page=sidebar()",text)
 def test_04_evaluation_reads_real_report(self):
  text=APP.read_text(encoding='utf-8')
  self.assertIn("evaluation_phase8.json",text)
  self.assertIn('Aucune annotation de pertinence validée',text)

if __name__=='__main__':unittest.main()
