#include "SecureClient.h"
#include <time.h>
#include <psa/crypto.h>
#include <mbedtls/build_info.h>

#if !defined(CONFIG_MBEDTLS_SSL_PROTO_TLS1_3) || !defined(CONFIG_MBEDTLS_HAVE_TIME_DATE)
#error HanMo requires the delivered TLS 1.3 SDK with certificate date validation.
#endif

namespace freeink {
SecureClient::SecureClient() { useDefaultTrust(); }
void SecureClient::useDefaultTrust() {
  stop();
  NetworkClientSecure::setCACert(nullptr);
  _use_insecure = false;
  // Attach ESP-IDF's embedded Mozilla bundle, without replacing global trust.
  attach_ssl_certificate_bundle(sslclient.get(), true);
  _use_ca_bundle = true;
}
void SecureClient::setCACert(const char* pem) {
  stop();
  if (!pem) { useDefaultTrust(); return; }
  _use_insecure = false;
  _use_ca_bundle = false;
  NetworkClientSecure::setCACert(pem);
}
int SecureClient::connect(const char* host, uint16_t port) {
  stop();
  // A missing clock must fail closed, rather than bypass certificate dates.
  if (!host || !*host || time(nullptr) < 1704067200 || psa_crypto_init() != PSA_SUCCESS) {
    log_e("TLS requires a valid clock and initialized cryptography");
    return 0;
  }
  // Arduino stop() clears this callback; restore it on EVERY connection.
  if (_use_ca_bundle) attach_ssl_certificate_bundle(sslclient.get(), true);
  const unsigned long timeoutMs = getTimeout();
  setHandshakeTimeout(timeoutMs / 1000 + (timeoutMs % 1000 != 0));
  // Arduino sets SNI AND the expected certificate hostname; errors do not
  // trigger an insecure connection or a TLS-version downgrade retry.
  return NetworkClientSecure::connect(host, port);
}
int SecureClient::connect(IPAddress ip, uint16_t port) { return connect(ip.toString().c_str(), port); }
bool SecureClient::tls13Available() { return true; }
}
