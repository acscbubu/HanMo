#pragma once
// HanMo: verified TLS using the source-built ESP-IDF mbedTLS SDK.
// Apache-2.0 mbedTLS; Arduino NetworkClientSecure retains its LGPL notice.
#include <NetworkClientSecure.h>
namespace freeink {
class SecureClient : public NetworkClientSecure {
 public:
  SecureClient();
  SecureClient(const SecureClient&) = delete;
  SecureClient& operator=(const SecureClient&) = delete;
  int connect(const char* host, uint16_t port) override;
  int connect(IPAddress ip, uint16_t port) override;
  void setCACert(const char* pem);
  void useDefaultTrust();
  static bool tls13Available();
 private:
  // HanMo has no opt-out from peer verification.
  using NetworkClientSecure::setInsecure;
};
}
