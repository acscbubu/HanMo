#pragma once
class GfxRenderer;
namespace ScreenImage {
bool valid(const char* path);
bool draw(GfxRenderer& renderer, const char* path);
void shutdownDefault(GfxRenderer& renderer);
}  // namespace ScreenImage
