#pragma once
#include <I18n.h>
#include "CrossPointSettings.h"
#include "ReaderGesturePolicy.h"
namespace ReaderGestureBindings {
using Field=uint8_t CrossPointSettings::*;
inline constexpr Field fields[]={&CrossPointSettings::gestureNextPage,&CrossPointSettings::gesturePreviousPage,
 &CrossPointSettings::gesturePinchFont,&CrossPointSettings::gestureRotation,&CrossPointSettings::gestureStatusBar,
 &CrossPointSettings::gestureSwipeUp,&CrossPointSettings::gestureSwipeDown,&CrossPointSettings::gestureSwipeLeft,&CrossPointSettings::gestureSwipeRight};
inline constexpr const char* keys[]={"gestureNextPage","gesturePreviousPage","gesturePinchFont","gestureRotation","gestureStatusBar","gestureSwipeUp","gestureSwipeDown","gestureSwipeLeft","gestureSwipeRight"};
inline constexpr StrId labels[]={StrId::STR_GESTURE_NEXT,StrId::STR_GESTURE_PREVIOUS,StrId::STR_GESTURE_PINCH,StrId::STR_GESTURE_ROTATION,StrId::STR_GESTURE_STATUS,StrId::STR_GESTURE_UP,StrId::STR_GESTURE_DOWN,StrId::STR_GESTURE_LEFT,StrId::STR_GESTURE_RIGHT};
inline constexpr StrId modes[]={StrId::STR_GESTURE_INHERIT,StrId::STR_GESTURE_TAP_SWIPE,StrId::STR_STATE_TAP,StrId::STR_STATE_SWIPE,StrId::STR_STATE_INVERTED_TAP,StrId::STR_DISABLED};
inline constexpr StrId actions[]={StrId::STR_DISABLED,StrId::STR_GESTURE_BRIGHTER,StrId::STR_GESTURE_DIMMER,StrId::STR_GESTURE_WARMER,StrId::STR_GESTURE_COOLER,StrId::STR_GESTURE_NEXT_CHAPTER,StrId::STR_GESTURE_PREV_CHAPTER,StrId::STR_GESTURE_LARGER,StrId::STR_GESTURE_SMALLER};
inline constexpr StrId toggles[]={StrId::STR_STATE_OFF,StrId::STR_STATE_ON};
inline bool owns(Field field){for(auto f:fields)if(f==field)return true;return false;}
inline int count(int row){return row<2?6:row<5?2:9;}
inline const StrId* options(int row){return row<2?modes:row<5?toggles:actions;}
} // namespace ReaderGestureBindings
