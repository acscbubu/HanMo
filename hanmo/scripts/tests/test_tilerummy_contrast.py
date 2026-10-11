"""Real Screen/Activity labels must contrast with Toybox black button fills."""
import pathlib
import subprocess
import tempfile
import unittest
from scripts.tests import test_tilerummy_ui as ui

class TileRummyContrastTest(unittest.TestCase):
    def run_contrast(self, mutation=None):
        renderer = ui.RENDERER_BOUNDARY
        activity = ui.ACTIVITY_BOUNDARY
        harness = ui.ACTIVITY_HARNESS
        try:
            ui.ACTIVITY_BOUNDARY = activity.replace(
                'struct TextCall { fui::Rect box; std::string value; };',
                'struct TextCall { fui::Rect box; std::string value; fui::Color color; };')
            assert ui.ACTIVITY_BOUNDARY != activity
            ui.RENDERER_BOUNDARY = renderer.replace(
                'void text(Rect box, const char* value, TextStyle) override {',
                'void text(Rect box, const char* value, TextStyle style) override {').replace(
                'renderer_.texts.push_back({box, value ? value : ""});',
                'renderer_.texts.push_back({box, value ? value : "", style.color});')
            assert ui.RENDERER_BOUNDARY != renderer
            anchor = 'for(const auto& t:r.texts) if(t.value==value) return true; return false;'
            replacement = '''for(const auto& t:r.texts) {
  if(t.value=="START" || t.value=="MENU" || t.value=="ADD" ||
     t.value=="TABLE" || t.value=="LOOSE" || t.value=="READY" ||
     t.value=="PLAY" || t.value=="DRAW")
    assert(t.color==fui::Color::White && "button label must contrast with black fill");
  if(t.value=="NEW GROUP" || t.value=="PASS EMPTY")
    assert(t.box.width>=88 && "long control caption requires readable width");
}
for(const auto& t:r.texts) if(t.value==value) return true;
return false;'''
            assert anchor in harness
            ui.ACTIVITY_HARNESS = harness.replace(anchor, replacement)
            with tempfile.TemporaryDirectory() as folder:
                exe = ui.compile_activity(folder, mutation)
                return subprocess.run([str(exe), 'playable'], capture_output=True, text=True, timeout=20)
        finally:
            ui.RENDERER_BOUNDARY = renderer
            ui.ACTIVITY_BOUNDARY = activity
            ui.ACTIVITY_HARNESS = harness

    def test_actual_menu_editor_handoff_control_contrast(self):
        result = self.run_contrast()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_black_on_black_mutation_is_runtime_failure(self):
        result = self.run_contrast(('label(s, r, text, true, fui::Color::White);',
                                    'label(s, r, text, true, fui::Color::Black);'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('button label must contrast', result.stderr)

if __name__ == '__main__':
    unittest.main()
