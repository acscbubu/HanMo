"""Configuration guard for the verified mbedTLS backend; runtime policy in tools/test-tls-transport.py."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[2]
class MbedTlsConfigTest(unittest.TestCase):
 def test_no_wolf_dependency(self):
  ini=(R/'platformio.ini').read_text()
  self.assertNotIn('WOLFSSL',ini);self.assertNotIn('Arduino-wolfSSL',ini)
  self.assertIn('-DFREEINK_NET_MBEDTLS=1',ini)
 def test_no_verification_opt_out(self):
  for rel in ['src/network/HttpDownloader.cpp','lib/KOReaderSync/KOReaderSyncClient.cpp','lib/WeReadWebApi/src/WeReadHttpClient.cpp','src/apps_local/bridge/BridgeHttp.cpp']:
   self.assertNotIn('.setInsecure(', (R/rel).read_text(),rel)
 def test_sdk_required(self):
  s=(R/'freeink-sdk/libs/network/SecureNet/src/SecureClient.cpp').read_text()
  self.assertIn('CONFIG_MBEDTLS_HAVE_TIME_DATE',s);self.assertIn('CONFIG_MBEDTLS_SSL_PROTO_TLS1_3',s)
if __name__=='__main__':unittest.main()
