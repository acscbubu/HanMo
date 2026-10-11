"""Regression contracts from 480x800 simulator screenshots for kana lessons."""
from pathlib import Path
import json,re,unittest

R=Path(__file__).resolve().parents[2]
J=R/'src/activities/apps/japanese'

class KanaScreenVisualContracts(unittest.TestCase):
 def test_stroke_glyph_label_uses_kana_font_not_chinese_body_fallback(self):
  source=(J/'KanaStrokeActivity.cpp').read_text()
  self.assertIn('hanmo_kana_52.h',source)
  self.assertIn('renderer.insertFont(kBigFontId, kBigFamily)',source)
  self.assertIn('renderer.drawText(kBigFontId, a.x + 12, layout.glyphY, glyph.glyph)',source)
  self.assertIn('drawGlyph(glyph, layout.artX, layout.artY, layout.artSide)',source)
  self.assertNotIn('renderer.drawCenteredText(kBigFontId, artY - 30, glyph.glyph)',source)
  self.assertNotIn('label(glyph.glyph,',source)

 def test_stroke_button_labels_fit_the_480px_bottom_row(self):
  trans=(R/'lib/I18n/translations/english.yaml').read_text()
  for key in ('STR_KANA_STROKE_PREV','STR_KANA_STROKE_RESTART','STR_KANA_STROKE_NEXT'):
   line=next(x for x in trans.splitlines() if x.startswith(key+': '))
   self.assertLessEqual(len(json.loads(line.split(': ',1)[1])),11)

 def test_kana_sources_use_active_language_and_pair_hint_rows(self):
  for name in ('KanaActivity.cpp','KanaQuizActivity.cpp','KanaSimilarActivity.cpp','KanaStrokeActivity.cpp','JapaneseLearningActivity.cpp'):
   source=(J/name).read_text()
   self.assertNotIn('I18N.get(id, Language::ZH_TW)',source,name)
   self.assertIn('I18N.get(id)',source,name)
  source=(J/'KanaSimilarActivity.cpp').read_text()
  self.assertIn('const char* KanaSimilarActivity::hintLine(int line)',source)
  self.assertIn('hintLine(0)',source)
  self.assertIn('hintLine(1)',source)

 def test_comparison_hints_are_two_separately_rendered_lines(self):
  source=(J/'KanaSimilarActivity.cpp').read_text()
  self.assertIn('const char* KanaSimilarActivity::hintLine(int line)',source)
  compare=source.split('void KanaSimilarActivity::drawCompare(',1)[1].split('void KanaSimilarActivity::drawTestPrompt(',1)[0]
  answer=source.split('void KanaSimilarActivity::drawTestAnswer(',1)[1].split('void KanaSimilarActivity::drawChoiceGlyph(',1)[0]
  for block in (compare,answer):
   self.assertIn('hintLine(0)',block)
   self.assertIn('hintLine(1)',block)
   self.assertNotIn('hintText()',block)

 def test_hint_line_keys_are_short_and_cjk_fallback_safe(self):
  for locale in ('english','chinese','chinese-traditional'):
   trans=(R/'lib/I18n/translations'/f'{locale}.yaml').read_text()
   for key in ('SHI_HINT','TSU_HINT','SO_HINT','N_HINT'):
    line=next(x for x in trans.splitlines() if x.startswith('STR_KANA_SIMILAR_'+key+': '))
    value=json.loads(line.split(': ',1)[1])
    self.assertNotRegex(value,r'[\u3040-\u30ff]')
    self.assertLessEqual(len(value),31 if locale=='english' else 18)

 def test_wrong_answer_highlights_correct_choice_and_selected_choice(self):
  source=(J/'KanaSimilarActivity.cpp').read_text()
  block=source.split('const auto choiceState =',1)[1].split('addButton(s, nullptr, 4',1)[0]
  self.assertIn('lesson_.targetCardId()',block)
  self.assertIn('fui::StateSelected',block)
  self.assertIn('fui::StateFocused',block)

 def test_feedback_glyph_does_not_overlap_hint(self):
  source=(J/'KanaSimilarActivity.cpp').read_text()
  answer=source.split('void KanaSimilarActivity::drawTestAnswer(',1)[1].split('void KanaSimilarActivity::drawChoiceGlyph(',1)[0]
  self.assertNotIn('card.katakana', answer)
  rows=[(int(y),int(h)) for y,h in re.findall(r'Rect\{a\.x, int16_t\(a\.y \+ (\d+)\), a\.width, (\d+)\}, hintLine\([01]\)',answer)]
  self.assertEqual(len(rows),2)
  self.assertGreaterEqual(rows[0][0]-(392+48),6)
  self.assertGreaterEqual(rows[1][0]-(rows[0][0]+rows[0][1]),6)
  self.assertLessEqual(58+rows[1][0]+rows[1][1]+6,800-12-52)

if __name__=='__main__': unittest.main()
