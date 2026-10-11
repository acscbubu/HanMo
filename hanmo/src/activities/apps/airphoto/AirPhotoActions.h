#pragma once

namespace airphoto {

enum class Cover { Startup, Sleep, Shutdown };

// Install an independent cover so removing the gallery original cannot break it.
bool setCover(const char* original, Cover cover);
// Remove only the original when another photo shares its derived bitmap stem.
bool deletePhoto(const char* original, const char* view, const char* thumb, bool sharedDerived);

}  // namespace airphoto
