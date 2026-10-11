#pragma once

// The device report, which this firmware does not send.
//
// In the fork the imported apps come from, an opt-in settings toggle attaches
// three headers to requests bound for that project's own hosts, and records
// what came back. The endpoint is theirs, the toggle is theirs, and the
// screen that explains it is theirs; none of that was part of porting the
// apps, and a firmware that quietly reported to somebody else's collector
// would be a worse outcome than a firmware that reports to nobody.
//
// So headersFor() writes nothing and delivered() records nothing. Kept as a
// header rather than edited out of the call sites so those files stay
// byte-identical to upstream and the next import is a copy, not a merge.
// Same reasoning as src/DevMode.h.

namespace devreport {

struct Header {
  const char* name;
  const char* value;
};

constexpr int kHeaderCount = 3;

// No headers to add. The caller loops to the returned count, so zero is the
// whole of the answer.
inline int headersFor(const char*, Header[kHeaderCount]) { return 0; }

// Nowhere to record the outcome.
inline void delivered(const char*, int) {}

}  // namespace devreport
