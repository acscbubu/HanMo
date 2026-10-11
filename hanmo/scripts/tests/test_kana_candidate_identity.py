from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
class KanaCandidateIdentityTests(unittest.TestCase):
 def test_private_candidate_has_own_version_identity(self):
  p=(ROOT/'platformio.ini').read_text()
  self.assertIn('version = 1.5.8',p)
  self.assertIn('${crosspoint.version}-hanmo-japanese-lessons-20261008',p)
  self.assertNotIn('${crosspoint.version}-hanmo-kana-stroke-sound-hint-20261007',p)
  self.assertNotIn('${crosspoint.version}-hanmo-kana-stroke-layout-v2-20261007',p)
  self.assertNotIn('${crosspoint.version}-hanmo-kana-stroke-layout-20261007',p)
  self.assertNotIn('${crosspoint.version}-hanmo-kana-similar-strokes-20261007',p)
  self.assertNotIn('${crosspoint.version}-hanmo-kana-sound-20261006',p)
if __name__=='__main__':unittest.main()
