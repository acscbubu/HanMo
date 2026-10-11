"""Guard the X4 Pro render task against the captured Games stack-canary panic."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class RenderTaskStackBudgetTest(unittest.TestCase):
    def test_x4pro_has_more_render_stack_than_panic_frame(self):
        source = (ROOT / 'src/activities/ActivityManager.cpp').read_text()
        setup = source.split('void ActivityManager::begin() {', 1)[1].split('xTaskCreatePinnedToCore(', 1)[0]
        x4pro = re.search(r'#elif FREEINK_DEVICE_X4PRO\s+constexpr uint32_t kRenderTaskStackBytes = (\d+);', setup)
        self.assertIsNotNone(x4pro, 'the X4 Pro needs a board-specific render budget')
        self.assertGreaterEqual(int(x4pro.group(1)), 12288)
        self.assertIn('kRenderTaskStackBytes,  // Stack size', setup + source)

    def test_other_board_stack_budgets_are_unchanged(self):
        source = (ROOT / 'src/activities/ActivityManager.cpp').read_text()
        self.assertRegex(source, r'#if FREEINK_DEVICE_EEGO_A4\s+constexpr uint32_t kRenderTaskStackBytes = 16384;')
        self.assertRegex(source, r'#else\s+constexpr uint32_t kRenderTaskStackBytes = 8192;')


if __name__ == '__main__':
    unittest.main()
