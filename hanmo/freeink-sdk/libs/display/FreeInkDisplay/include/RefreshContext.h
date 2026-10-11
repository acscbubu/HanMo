#pragma once
#include <stdint.h>

namespace freeink {
// Applies only to this refresh. A synchronized grayscale baseline may be reused
// between reading pages; transitions to other content retain physical cleanup.
enum class RefreshContext : uint8_t { Normal, ContinuousReading };
}  // namespace freeink
