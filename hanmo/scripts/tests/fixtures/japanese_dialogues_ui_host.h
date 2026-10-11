// Hardware-only host seam; FreeInkUI renderer adapter remains production.
#pragma once
#include <EpdFontFamily.h>
#include <FreeInkApp.h>
#include <Utf8.h>
#include <builtinFonts/notosans_8_regular.h>
#include <builtinFonts/hanmo_ui_maruko_10.h>
#include <builtinFonts/hanmo_ui_maruko_12.h>
#include <builtinFonts/hanmo_ui_maruko_8.h>
#include <builtinFonts/ubuntu_10_medium.h>
#include <builtinFonts/ubuntu_12_medium.h>
#include <fontIds.h>
#include <builtinFonts/notosans_cjk_12.h>

#include <algorithm>
#include <array>
#include <cassert>
#include <cstring>
#include <map>
#include <string>
#include <vector>

enum class Color { White, LightGray, DarkGray, Black, Clear };
struct Draw {
  int font, x, y, width, height;
  std::string text;
  int color = int(freeink::ui::Color::Black);
};
struct Box {
  freeink::ui::Rect rect;
  freeink::ui::Paint paint;
};
struct Rect {
  int x, y, width, height;
};
class GfxRenderer {
 public:
  enum class Orientation { Portrait, LandscapeClockwise, PortraitInverted, LandscapeCounterClockwise };
  mutable std::vector<Draw> draws;
  mutable std::vector<Box> boxes;
  std::map<int, EpdFontFamily> fonts;
  Orientation orientation = Orientation::LandscapeClockwise;
  int width = 480, height = 800, displays = 0;
  GfxRenderer() {
    static const EpdFont ui10(&hanmo_ui_maruko_10), ui12(&hanmo_ui_maruko_12), small(&hanmo_ui_maruko_8);
    static const EpdFont cjk8(&hanmo_ui_maruko_8), cjk10(&hanmo_ui_maruko_10), cjk12(&hanmo_ui_maruko_12);
    fonts.emplace(UI_10_FONT_ID, EpdFontFamily(&ui10));
    fonts.emplace(UI_12_FONT_ID, EpdFontFamily(&ui12));
    fonts.emplace(SMALL_FONT_ID, EpdFontFamily(&small));
    fonts.emplace(8, EpdFontFamily(&cjk8));
    fonts.emplace(10, EpdFontFamily(&cjk10));
    fonts.emplace(12, EpdFontFamily(&cjk12));
    static const EpdFont reader(&notosans_cjk_12);
    fonts.emplace(1, EpdFontFamily(&reader));  // unchanged-reader canary only
  }
  Orientation getOrientation() const { return orientation; }
  void setOrientation(Orientation o) { orientation = o; }
  int getScreenWidth() const { return width; }
  int getScreenHeight() const { return height; }
  void getOrientedViewableTRBL(int* t, int* r, int* b, int* l) const { *t = *r = *b = *l = 0; }
  const auto& getFontMap() const { return fonts; }
  void insertFont(int id, const EpdFontFamily& f) { fonts.emplace(id, f); }
  void removeFont(int id) { fonts.erase(id); }
  int resolvedFont(int id, const char* text, EpdFontFamily::Style style = EpdFontFamily::REGULAR) const {
    const int fallback = id == UI_10_FONT_ID ? 10 : id == UI_12_FONT_ID ? 12 : id == SMALL_FONT_ID ? 8 : 0;
    if (!fallback) return id;
    const auto* p = reinterpret_cast<const uint8_t*>(text);
    uint32_t cp;
    while ((cp = utf8NextCodepoint(&p)))
      if (utf8IsCjkCodepoint(cp) && !fonts.at(id).hasCodepoint(cp, style) && fonts.at(fallback).hasCodepoint(cp, style))
        return fallback;
    return id;
  }
  mutable size_t widthCalls = 0;
  int getTextWidth(int id, const char* text, EpdFontFamily::Style style = EpdFontFamily::REGULAR) const {
    ++widthCalls;
    const auto& f = fonts.at(resolvedFont(id, text, style));
    int w = 0, h = 0;
    f.getTextDimensions(text, &w, &h, style);
    int advance = 0;
    uint32_t cp, prev = 0;
    const auto* p = reinterpret_cast<const uint8_t*>(text);
    while ((cp = utf8NextCodepoint(&p))) {
      const auto* g = f.getGlyph(cp, style);
      if (!g) continue;
      advance += fp4::toPixel(g->advanceX + (prev ? f.getKerning(prev, cp, style) : 0));
      prev = cp;
    }
    return std::max(w, advance);
  }
  int getLineHeight(int id) const { return fonts.at(id).getData()->advanceY; }
  void drawText(int id, int x, int y, const char* text, bool = true,
                EpdFontFamily::Style style = EpdFontFamily::REGULAR) const {
    if (text && *text) draws.push_back({id, x, y, getTextWidth(id, text, style), getLineHeight(id), text});
  }
  void drawTextDither(int id, int x, int y, const char* text, Color c, EpdFontFamily::Style style) const {
    drawText(id, x, y, text, true, style);
    if (!draws.empty())
      draws.back().color = c == Color::LightGray ? int(freeink::ui::Color::LightGray) : int(freeink::ui::Color::Black);
  }
  void drawTextRotated90CW(int id, int x, int y, const char* text, bool b, EpdFontFamily::Style s) const {
    drawText(id, x, y, text, b, s);
  }
  std::string truncatedText(int id, const char* value, int width,
                            EpdFontFamily::Style s = EpdFontFamily::REGULAR) const {
    std::string line;
    const auto* p = reinterpret_cast<const uint8_t*>(value);
    while (*p) {
      const auto* start = p;
      utf8NextCodepoint(&p);
      auto next = line + std::string(reinterpret_cast<const char*>(start), p - start);
      if (getTextWidth(id, next.c_str(), s) > width) break;
      line = next;
    }
    return line;
  }
  std::vector<std::string> wrappedText(int id, const char* value, int width, int maximum,
                                       EpdFontFamily::Style s = EpdFontFamily::REGULAR) const {
    std::vector<std::string> lines;
    std::string line;
    const auto* p = reinterpret_cast<const uint8_t*>(value);
    while (*p) {
      const auto* start = p;
      utf8NextCodepoint(&p);
      std::string cp(reinterpret_cast<const char*>(start), p - start);
      if (!line.empty() && getTextWidth(id, (line + cp).c_str(), s) > width) {
        lines.push_back(line);
        line.clear();
      }
      line += cp;
    }
    if (!line.empty()) lines.push_back(line);
    if (int(lines.size()) > maximum) lines.resize(maximum);
    return lines;
  }
  void filled(int x, int y, int w, int h, freeink::ui::Color c) const {
    boxes.push_back({{int16_t(x), int16_t(y), int16_t(w), int16_t(h)}, freeink::ui::Paint::solid(c)});
  }
  void fillRect(int x, int y, int w, int h, bool black) const {
    filled(x, y, w, h, black ? freeink::ui::Color::Black : freeink::ui::Color::White);
  }
  void fillRectDither(int x, int y, int w, int h, Color) const { filled(x, y, w, h, freeink::ui::Color::LightGray); }
  void fillRoundedRect(int x, int y, int w, int h, int, Color) const { filled(x, y, w, h, freeink::ui::Color::White); }
  void fillRoundedRect(int x, int y, int w, int h, int, bool, bool, bool, bool, Color c) const {
    fillRoundedRect(x, y, w, h, 0, c);
  }
  void drawRoundedRect(int, int, int, int, int, int, bool) const {}
  void drawRoundedRect(int, int, int, int, int, int, bool, bool, bool, bool, bool) const {}
  void drawRect(int, int, int, int, int, bool) const {}
  void drawLine(int, int, int, int, int, bool) const {}
  void fillPolygon(const int*, const int*, int, bool) const {}
  void drawPixel(int, int, bool) const {}
  void clearScreen() {
    draws.clear();
    boxes.clear();
  }
  void displayBuffer() { ++displays; }
};
class MappedInputManager {
 public:
  enum class Button { Back, Confirm, Left, Right, Up, Down };
  std::array<bool, 6> released{}, held{};
  freeink::ui::InputSnapshot touch{};
  bool wasReleased(Button b) const { return released[int(b)]; }
  bool isPressed(Button b) const { return held[int(b)]; }
  void clear() {
    released.fill(false);
    held.fill(false);
    touch = {};
  }
};
class Activity;
inline int renderDepth = 0;
struct RenderLock {
  explicit RenderLock(Activity&) { ++renderDepth; }
  ~RenderLock() { --renderDepth; }
};
class Activity {
 protected:
  GfxRenderer& renderer;
  MappedInputManager& mappedInput;

 public:
  int updates = 0, finishes = 0, entries = 0, exits = 0;
  Activity(const char*, GfxRenderer& r, MappedInputManager& m) : renderer(r), mappedInput(m) {}
  virtual ~Activity() = default;
  virtual void onEnter() { ++entries; }
  virtual void onExit() { ++exits; }
  virtual void loop() {}
  virtual void render(RenderLock&&) {}
  virtual void requestUpdate(bool = false) { ++updates; }
  void finish() { ++finishes; }
};
