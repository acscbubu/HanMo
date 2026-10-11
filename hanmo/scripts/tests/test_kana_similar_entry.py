"""Ensure Japanese category 4 opens the comparison lesson and others survive."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
ACT=ROOT/'src/activities/apps/japanese/JapaneseLearningActivity.cpp'

class KanaSimilarEntryTests(unittest.TestCase):
    def test_similar_row_routes_to_standalone_lesson(self):
        text=ACT.read_text(encoding='utf-8')
        self.assertIn('#include "KanaSimilarActivity.h"', text)
        self.assertRegex(text,r'category_\s*<\s*0\s*&&\s*index\s*==\s*4')
        self.assertIn('startActivityForResultWith<KanaSimilarActivity>',text)
        for earlier in ('KanaStrokeActivity','KanaQuizActivity','KanaGroupsActivity'):
            self.assertIn('startActivityForResultWith<'+earlier+'>',text)

    def test_labels_exist_in_all_locales(self):
        keys=('COMPARE','TEST','CHOOSE','CORRECT','TRY_AGAIN','NEXT','RESTART','SHI_HINT','TSU_HINT','SO_HINT','N_HINT')
        for locale in ('english','chinese','chinese-traditional'):
            data=(ROOT/'lib/I18n/translations'/f'{locale}.yaml').read_text(encoding='utf-8')
            for k in keys: self.assertIn('STR_KANA_SIMILAR_'+k+':',data)

if __name__=='__main__':unittest.main()
