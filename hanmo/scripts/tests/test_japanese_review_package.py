"""Private daily-review app-only deliverable gate (not prior release tests)."""
import hashlib
import json
from pathlib import Path
import os
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[2]
OUTER=Path(os.environ.get('HANMO_WORKSPACE','/mnt/c/Users/angus/OneDrive/文件/ChatGPT/XTEINK UI'))
ID='hanmo-japanese-review-test-20261008'
VERSION='1.5.8-hanmo-japanese-review-20261008'
BUILD=OUTER/'XTEINK-Firmware'/('build-'+ID)
EVIDENCE=OUTER/'migration/japanese-review-20261008'

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
    return h.hexdigest()

class JapaneseReviewPackageTests(unittest.TestCase):
    def test_app_new_identity_capacity_no_factory_and_mirrors(self):
        self.assertTrue((BUILD/'verification.json').is_file(),'New private review candidate not packaged')
        v=json.loads((BUILD/'verification.json').read_text())
        self.assertEqual((v['id'],v['version']),(ID,VERSION))
        for k in ('published','hardwareFlashed','hardwareValidated'):self.assertIs(v[k],False,k)
        self.assertEqual(v['packageMode'],'app-only')
        app=BUILD/'crossmux-app0.bin'; data=app.read_bytes()
        self.assertEqual(data[0],0xe9)
        self.assertIn(VERSION.encode(),data)
        self.assertIn(b'/.crosspoint/japanese-review-v1.bin',data)
        self.assertLessEqual(len(data),0x7f0000)
        self.assertEqual(v['images']['crossmux-app0.bin']['sha256'],sha(app))
        self.assertEqual(v['images']['crossmux-app0.bin']['bytes'],len(data))
        names={p.name for p in BUILD.iterdir() if p.is_file()}
        self.assertFalse(any('FULL' in n or 'factory' in n.lower() or 'bootloader' in n for n in names))
        for mirror in ('build-x4pro-custom','flasher/firmware'):
            folder=OUTER/'XTEINK-Firmware'/mirror/'prototypes'/ID
            self.assertEqual({p.name for p in folder.iterdir() if p.is_file()},names)
            for name in names:self.assertEqual(sha(BUILD/name),sha(folder/name),str(folder/name))

    def test_zip_crc_and_source_index_are_new_exact_deliverables(self):
        bundle=OUTER/'XTEINK-Firmware/releases'/(ID+'-update.zip')
        self.assertTrue(bundle.is_file(),'New private review ZIP missing')
        with zipfile.ZipFile(bundle) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(set(z.namelist()),{'crossmux-app0.bin','README.txt','HanMoKana/LICENSE.txt','HanMoKana/COPYRIGHT.txt','HanMoKana/UPSTREAM-README.md'})
            self.assertEqual(z.read('crossmux-app0.bin'),(BUILD/'crossmux-app0.bin').read_bytes())
            self.assertIn('app-only',z.read('README.txt').decode())
        index=json.loads((BUILD/'source-index.json').read_text())
        for name in ('JapaneseReview.h','JapaneseReviewStore.h','JapaneseReviewActivity.h','JapaneseReviewActivity.cpp'):
            rel='src/activities/apps/japanese/'+name
            self.assertIn(rel,index)
            self.assertEqual(index[rel]['sha256'],sha(ROOT/rel))
        for rel in index:
            self.assertFalse(any(s in ('.pio','.cache','.font-tools','__pycache__') for s in Path(rel).parts),rel)
            self.assertFalse(Path(rel).suffix.lower() in ('.key','.p12','.pfx','.pem'),rel)
        v=json.loads((BUILD/'verification.json').read_text())
        self.assertEqual(v['source']['count'],len(index))
        self.assertEqual(v['source']['sha256'],sha(OUTER/v['source']['path']))

    def test_previous_candidate_stable_roots_and_pin_protected(self):
        self.assertTrue((EVIDENCE/'protected-before.json').is_file())
        baseline=json.loads((EVIDENCE/'protected-before.json').read_text())
        for rel,v in baseline['files'].items():
            self.assertEqual((OUTER/rel).stat().st_size,v['size'],rel)
            self.assertEqual(sha(OUTER/rel),v['sha256'],rel)
        self.assertEqual(sha(OUTER/'XTEINK-Firmware/flasher/release-config.json'),baseline['releaseConfigSha256'])

if __name__=='__main__':unittest.main()
