#pragma once
#include <cstdint>
namespace ReaderGesturePolicy {
enum Mode : uint8_t { Inherit, TapSwipe, Tap, Swipe, InvertedTap, Disabled, ModeCount };
enum Action : uint8_t { None, Brighter, Dimmer, Warmer, Cooler, NextChapter, PreviousChapter, LargerFont, SmallerFont, ActionCount };
inline uint8_t effective(uint8_t mode,uint8_t legacy) {
  if(mode && mode<ModeCount)return mode;
  return legacy==0?Disabled:legacy==2?Swipe:legacy==3?InvertedTap:Tap;
}
inline bool page(bool forward,uint8_t mode,bool tapped,int x,int width,int swipe) {
  if(mode==Disabled || width<3)return false;
  if((mode==Swipe || mode==TapSwipe) && swipe==(forward?-1:1))return true;
  if(!tapped || (mode!=Tap && mode!=TapSwipe && mode!=InvertedTap))return false;
  const bool right=forward!=(mode==InvertedTap);
  return right ? x>=width-width/3 && x<width : x>=0 && x<width/3;
}
inline uint8_t rotated(uint8_t orientation,bool clockwise){return (orientation+(clockwise?1:3))%4;}
} // namespace ReaderGesturePolicy
