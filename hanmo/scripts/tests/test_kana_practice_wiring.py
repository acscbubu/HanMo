"""Guard firmware UI wiring; behavioral storage tests and simulator QA run separately."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'src/activities/apps/japanese/KanaActivity.cpp'
HEADER = ROOT / 'src/activities/apps/japanese/KanaActivity.h'


class KanaPracticeWiringTests(unittest.TestCase):
    def test_example_reading_tracks_show_hide_control(self):
        text = SOURCE.read_text()
        self.assertRegex(text, r'state_\.roman\s*\?\s*card\.exampleRomaji')
        self.assertIn('card.example', text)
        self.assertIn('card.meaning', text)

    def test_storage_io_is_serialized_on_hardware(self):
        source = SOURCE.read_text()
        self.assertIn('#if defined(ARDUINO_ARCH_ESP32)\n    HalStorage::StorageLock lock;', source)
        self.assertIn('#if defined(ARDUINO_ARCH_ESP32)\n        HalStorage::StorageLock storageLock;', source)

    def test_staging_is_verified_before_sd_rename(self):
        store = (ROOT / 'src/activities/apps/japanese/KanaPracticeStore.h').read_text()
        self.assertIn('decodePractice(readback, decoded)', store)
        self.assertIn('decoded.marks != value.marks', store)
        self.assertLess(store.index('decodePractice(readback, decoded)'), store.index('AirNoteStore::replace'))

    def test_group_counter_keeps_value_in_the_list_band(self):
        source = SOURCE.read_text()
        self.assertIn('rows_[i].value = progressLabels_[i].data()', source)
        self.assertIn('rows_[1].subtitle', source)
        self.assertIn('std::snprintf(progressLabels_[i].data()', source)

    def test_sd_lock_is_only_compiled_for_real_esp32_hardware(self):
        text = SOURCE.read_text()
        self.assertEqual(text.count('HalStorage::StorageLock'), 3)
        self.assertIn('#if defined(ARDUINO_ARCH_ESP32)\n    HalStorage::StorageLock lock;', text)
        self.assertIn('#if defined(ARDUINO_ARCH_ESP32)\n        HalStorage::StorageLock storageLock;', text)

    def test_marks_use_absolute_card_id_persist_then_update_ui(self):
        source = SOURCE.read_text()
        header = HEADER.read_text()
        self.assertIn('KanaPracticeStore.h', source)
        self.assertIn('kana::Practice practice_', header)
        self.assertRegex(source, r'toggle\(state_\.current\(\),\s*value\s*-\s*10\)')
        self.assertIn('savePractice(Storage, candidate, &practice_)', source)
        self.assertIn('practice_ = candidate', source)
        self.assertIn('for (int marker = 0; marker < 7; ++marker)', source)
        self.assertIn('p.minTouchSize = 44', source)
        self.assertIn('doneCount(', source)
        self.assertIn('rows_[i].value', source)
        self.assertIn('STR_KANA_SAVE_FAILED', source)


if __name__ == '__main__':
    unittest.main()
