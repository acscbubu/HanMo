#include "ReaderActivity.h"

#include <FsHelpers.h>
#include <HalStorage.h>
#include <HalFrontlight.h>
#include "ReaderFontSizes.h"
#include "ReaderGesturePolicy.h"
#include "components/UITheme.h"
#include <Memory.h>

#include <algorithm>

#include "CrossPointSettings.h"
#include "CrossPointState.h"
#include "EpubReaderActivity.h"
#include "ReaderUtils.h"
#include "RecentBooksStore.h"
#include "SdCardFontSystem.h"
#include "TxtReaderActivity.h"
#include "XtcReaderActivity.h"

ReaderActivity::ReaderActivity(const char* name, GfxRenderer& renderer, MappedInputManager& mappedInput,
                               std::string bookPath, const bool allowFastInitialRefresh)
    : Activity(name, renderer, mappedInput), bookPath(std::move(bookPath)) {
  if (allowFastInitialRefresh) {
    const int refreshFrequency = SETTINGS.getRefreshFrequency();
    pagesUntilFullRefresh = refreshFrequency > 1 ? refreshFrequency : 2;
  }
}

std::unique_ptr<ReaderActivity> ReaderActivity::create(GfxRenderer& renderer, MappedInputManager& mappedInput,
                                                       std::string path, const bool allowFastInitialRefresh) {
  // ActivityManager requires heap ownership; each branch allocates exactly one screen-lifetime object.
  std::unique_ptr<ReaderActivity> activity;
  if (FsHelpers::hasXtcExtension(path)) {
    activity = makeUniqueNoThrow<XtcReaderActivity>(renderer, mappedInput, std::move(path), allowFastInitialRefresh);
  } else if (FsHelpers::hasTxtExtension(path) || FsHelpers::hasMarkdownExtension(path)) {
    activity = makeUniqueNoThrow<TxtReaderActivity>(renderer, mappedInput, std::move(path), allowFastInitialRefresh);
  } else {
    activity = makeUniqueNoThrow<EpubReaderActivity>(renderer, mappedInput, std::move(path), allowFastInitialRefresh);
  }

  if (!activity) {
    LOG_ERR("READER", "OOM: reader activity");
  }
  return activity;
}

void ReaderActivity::applyInitialOrientation() { ReaderUtils::applyOrientation(renderer, SETTINGS.orientation); }

void ReaderActivity::disableFastInitialRefresh() { pagesUntilFullRefresh = 0; }

void ReaderActivity::onEnter() {
  Activity::onEnter();
  gestureWaitForRelease=mappedInput.gestureContactCount()>0;

  if (!Storage.exists(bookPath.c_str())) {
    LOG_ERR("READER", "File does not exist: %s", bookPath.c_str());
    finish();
    return;
  }

  sdFontSystem.ensureLoaded(renderer);
  applyInitialOrientation();

  if (!loadBook()) {
    finish();
    return;
  }

  APP_STATE.openEpubPath = bookPath;
  APP_STATE.saveToFile();
  RECENT_BOOKS.addBook(bookPath, getBookTitle(), getBookAuthor(), getBookThumbBmpPath());
  requestUpdate();
}

void ReaderActivity::onExit() {
  Activity::onExit();

  renderer.setOrientation(GfxRenderer::Orientation::Portrait);
  APP_STATE.readerActivityLoadCount = 0;
  APP_STATE.saveToFile();

  endOfBookOptions.reset();
  endOfBookOptionsReady.store(false, std::memory_order_release);
}

bool ReaderActivity::handleBackNavigation() {
  return ReaderUtils::handleBackNavigation(mappedInput, activityManager, bookPath.c_str(),
                                           {this, [](void* ctx) { static_cast<ReaderActivity*>(ctx)->onGoHome(); }});
}

void ReaderActivity::clearEndOfBookOptionsIfNeeded() {
  if (isAtEndOfBook() || !endOfBookOptionsReady.load(std::memory_order_acquire)) return;

  RenderLock lock(*this);
  endOfBookOptionsReady.store(false, std::memory_order_release);
  endOfBookOptions.reset();
}

bool ReaderActivity::endOfBookMenuActive() const {
  return isAtEndOfBook() && endOfBookOptionsReady.load(std::memory_order_acquire) && endOfBookOptions->menuActive();
}

bool ReaderActivity::handleEndOfBookMenu(const bool suppressConfirmRelease) {
  if (suppressConfirmRelease || !endOfBookMenuActive()) {
    return false;
  }

  std::string openPath;
  switch (endOfBookOptions->handleMenuInput(mappedInput, &openPath)) {
    case EndOfBookOptions::Action::OpenBook:
      activityManager.goToReader(openPath);
      return true;
    case EndOfBookOptions::Action::GoHome:
      onGoHome();
      return true;
    case EndOfBookOptions::Action::LastPage:
      onReturnFromEndOfBook();
      requestUpdate();
      return true;
    case EndOfBookOptions::Action::Redraw:
      requestUpdate();
      return true;
    case EndOfBookOptions::Action::None:
      return false;
  }

  return false;
}

bool ReaderActivity::handleEndOfBookPageTurn(const bool prevTriggered, const bool nextTriggered) {
  if (!isAtEndOfBook()) return false;

  if (endOfBookOptionsReady.load(std::memory_order_acquire) && endOfBookOptions->menuActive()) {
    return true;
  }
  if (nextTriggered) {
    onGoHome();
  } else if (prevTriggered) {
    onReturnFromEndOfBook();
    requestUpdate();
  }
  return true;
}

void ReaderActivity::loop() {
  clearEndOfBookOptionsIfNeeded();
  if (handleEndOfBookMenu()) return;
  if (handleReadingGestures()) return;
  if (handleFormatInput()) return;
  if (handleBackNavigation()) return;

  const auto touch = ReaderUtils::detectTouchPageTurn(renderer, mappedInput);
  auto [prevTriggered, nextTriggered, fromTilt] = ReaderUtils::detectPageTurn(mappedInput);
  prevTriggered = prevTriggered || touch.prev;
  nextTriggered = nextTriggered || touch.next;
  if (!prevTriggered && !nextTriggered) return;
  if (handleEndOfBookPageTurn(prevTriggered, nextTriggered)) return;

  const unsigned long heldMs = (touch.prev || touch.next) ? touch.heldMs : mappedInput.getHeldTime();
  const bool skip =
      !fromTilt && SETTINGS.longPressButtonBehavior == SETTINGS.CHAPTER_SKIP && heldMs >= ReaderUtils::SKIP_HOLD_MS;

  if (prevTriggered) {
    if (skip) {
      skipPages(-10);
    } else {
      pageTurn(false);
    }
  } else {
    if (skip) {
      skipPages(10);
    } else {
      pageTurn(true);
    }
  }
  requestUpdate();
}

void ReaderActivity::render(RenderLock&&) {
  if (isAtEndOfBook()) {
    if (!endOfBookOptions) {
      endOfBookOptions = makeUniqueNoThrow<EndOfBookOptions>(renderer);
      if (!endOfBookOptions) LOG_ERR("READER", "OOM: EndOfBookOptions");
    }
    renderer.clearScreen();
    if (endOfBookOptions) {
      endOfBookOptions->loadOnce(bookPath);
      // Release-publish AFTER loadOnce() so the main task's acquire load can't
      // observe an object whose names/selector are still being populated.
      endOfBookOptionsReady.store(true, std::memory_order_release);
      endOfBookOptions->render(renderer, mappedInput);
    }
    renderer.displayBuffer();
    onEndOfBookRendered();
    return;
  }

  renderBook();
}

bool ReaderActivity::handleForcedRefresh() {
  {
    RenderLock lock(*this);
    pagesUntilFullRefresh = 1;
    forcedRefreshPending = true;
  }
  requestUpdate();
  return true;
}

bool ReaderActivity::stepGestureFont(bool larger) {
  if(!supportsGestureText())return false;
  // Reuse the existing bounded installed-size list (a few bytes per font
  // size), rather than allocating any font or page buffer in the input path.
  const auto sizes=readerFontPointSizes(&sdFontSystem.registry(),SETTINGS.sdFontFamilyName);
  const uint8_t current=snapToNearestPointSize(sizes,SETTINGS.fontPointSize);
  const auto found=std::find(sizes.begin(),sizes.end(),current);
  if(found==sizes.end() || (larger?found+1==sizes.end():found==sizes.begin()))return false;
  const auto oldSize=SETTINGS.fontPointSize,oldPreload=SETTINGS.sdFontFlashPreload;
  SETTINGS.fontPointSize=*(larger?found+1:found-1);SETTINGS.sdFontFlashPreload=0;
  if(!SETTINGS.saveToFile()){SETTINGS.fontPointSize=oldSize;SETTINGS.sdFontFlashPreload=oldPreload;return false;}
  gestureFontChanged();requestUpdate();return true;
}
bool ReaderActivity::handleReadingGestures() {
  if(!mappedInput.hasTouch())return false;
  const uint8_t contacts=mappedInput.gestureContactCount();
  if(gestureWaitForRelease) {if(!contacts)gestureWaitForRelease=false;return true;}
  if(isAtEndOfBook()) {pinchGesture.reset();gestureMultiSequence=false;return false;}
  bool clockwise=false;
  const bool rotation=mappedInput.twoFingerRotation(clockwise);
  const auto swipe=mappedInput.twoFingerSwipe();
  const bool hasCompletion=rotation || swipe!=MappedInputManager::SwipeDir::None;
  if(contacts>=2 && !hasCompletion) {
    gestureMultiSequence=true;
    if(contacts!=2){gestureInvalid=true;pinchGesture.reset();return true;}
    if(!gestureConsumed && !gestureInvalid && SETTINGS.touchReaderControls && SETTINGS.gesturePinchFont && supportsGestureText()) {
      int x1=0,y1=0,x2=0,y2=0;
      if(mappedInput.getTwoFingerTouch(x1,y1,x2,y2)) {
        const auto action=pinchGesture.update(x1,y1,x2,y2);
        if(action!=ReaderPinchGesture::Action::None) {
          gestureConsumed=true;
          stepGestureFont(action==ReaderPinchGesture::Action::Increase);
          mappedInput.swallowCurrentTouch();
        }
      }
    }
    return true;
  }
  if(gestureMultiSequence && contacts && !hasCompletion)return true;
  const bool completed=gestureMultiSequence || rotation || swipe!=MappedInputManager::SwipeDir::None;
  const bool canAct=!gestureConsumed && !gestureInvalid && SETTINGS.touchReaderControls;
  gestureMultiSequence=false;gestureConsumed=false;gestureInvalid=false;pinchGesture.reset();
  if(completed) {
    // The SDK completes when the first tracked finger leaves. Own any
    // remaining contact through release rather than losing this event.
    gestureWaitForRelease=contacts>0;
    if(canAct && rotation && SETTINGS.gestureRotation && supportsGestureText()) {
      gestureRotate(clockwise);requestUpdate();
    } else if(canAct && !rotation) {
      using namespace ReaderGesturePolicy;
      uint8_t action=ReaderGesturePolicy::None;
      switch(swipe) {
        case MappedInputManager::SwipeDir::Up:action=SETTINGS.gestureSwipeUp;break;
        case MappedInputManager::SwipeDir::Down:action=SETTINGS.gestureSwipeDown;break;
        case MappedInputManager::SwipeDir::Left:action=SETTINGS.gestureSwipeLeft;break;
        case MappedInputManager::SwipeDir::Right:action=SETTINGS.gestureSwipeRight;break;
        default:break;
      }
      if(action==LargerFont || action==SmallerFont)stepGestureFont(action==LargerFont);
      else if(action==NextChapter || action==PreviousChapter){gestureChapter(action==NextChapter);requestUpdate();}
      else if((action==Brighter || action==Dimmer) && Frontlight.present()) {
        const auto old=SETTINGS.frontlightBrightness,oldOn=SETTINGS.frontlightOn;
        SETTINGS.frontlightBrightness=static_cast<uint8_t>(std::clamp(static_cast<int>(old)+(action==Brighter?10:-10),0,100));
        SETTINGS.frontlightOn=SETTINGS.frontlightBrightness>0;
        if(SETTINGS.saveToFile()){Frontlight.setBrightness(SETTINGS.frontlightBrightness);Frontlight.setOn(SETTINGS.frontlightOn);}
        else{SETTINGS.frontlightBrightness=old;SETTINGS.frontlightOn=oldOn;}
      } else if((action==Warmer || action==Cooler) && Frontlight.hasColorTemperature()) {
        const auto old=SETTINGS.frontlightWarmth;
        SETTINGS.frontlightWarmth=static_cast<uint8_t>(std::clamp(static_cast<int>(old)+(action==Warmer?10:-10),0,100));
        if(SETTINGS.saveToFile())Frontlight.setWarmth(SETTINGS.frontlightWarmth);else SETTINGS.frontlightWarmth=old;
      }
    }
    return true; // No completed multi-touch gesture may become a page turn.
  }
  if(SETTINGS.touchReaderControls && SETTINGS.gestureStatusBar && supportsGestureText()) {
    int x=0,y=0;
    const int band=UITheme::getInstance().getStatusBarHeight();
    if(band>0 && mappedInput.wasScreenTapped(x,y) && y>=renderer.getScreenHeight()-band) {
      {RenderLock lock(*this);gestureStatusHidden=!gestureStatusHidden;}
      requestUpdate();return true;
    }
  }
  return false;
}
