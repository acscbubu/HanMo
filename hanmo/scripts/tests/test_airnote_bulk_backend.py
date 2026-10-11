"""Backend route and bounded JSON contract; the C++ helper is host-executed separately."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class BulkBackendTest(unittest.TestCase):
    def test_device_bulk_order_route_and_handler_contract(self):
        header = (ROOT / 'src/network/CrossPointWebServer.h').read_text()
        source = (ROOT / 'src/network/CrossPointWebServer.cpp').read_text()
        self.assertIn('void handleBulkOrderAirNote();', header)
        self.assertIn('server->on("/api/airnote/order/bulk", HTTP_PUT, [this] { handleBulkOrderAirNote(); });', source)
        handler = source.split('void CrossPointWebServer::handleBulkOrderAirNote() {', 1)[1].split('\nvoid CrossPointWebServer::', 1)[0]
        for required in ('hasArg("plain")', 'deserializeJson(', 'doc["names"]',
                         'doc["before"]', 'doc["orderRevision"]',
                         'AirNoteOrdering::moveManyBefore(', 'recoverAirNotes()'):
            self.assertIn(required, handler)
        self.assertIn('body.length() > 4096', handler)
        self.assertIn('isUnbound()', handler)  # absent before is not explicit null
        self.assertIn('value.is<const char*>()', handler)
        self.assertIn('AirNotePolicy::validFileName(name)', handler)
        # Bad identities/revisions are 400 even when storage is unavailable.
        self.assertIn('AirNoteOrdering::validBulkRequest(', handler)
        self.assertLess(handler.index('AirNoteOrdering::validBulkRequest('),
                        handler.index('recoverAirNotes()'))
        self.assertRegex(handler, r'names\.size\(\)\s*>\s*32|array\.size\(\)\s*>\s*32')
        self.assertRegex(handler, r'Result::Invalid\s*\?\s*400')
        self.assertRegex(handler, r'Result::Conflict\s*\?\s*409')
        self.assertRegex(handler, r'Result::Missing\s*\?\s*404')
        self.assertRegex(handler, r'\b507\b')
        self.assertIn('{\\"ok\\":true}', handler)


if __name__ == '__main__':
    unittest.main()
