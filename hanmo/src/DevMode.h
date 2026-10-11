#pragma once

// Developer Mode, which this firmware does not have.
//
// The imported apps guard their Wi-Fi teardown with holdsRadio() and bracket
// exclusive radio work with pause()/resume(), because in the fork they come
// from a Developer Mode server can be holding the radio for flashing and
// debugging over Wi-Fi. That is a whole feature -- a pairing screen, a
// settings row, an OTA endpoint -- and porting it was not the job; porting
// the games was.
//
// So the answers are the ones that are true here: nothing else is holding the
// radio, and there is nothing to pause. Kept as a header rather than edited
// out of six call sites so those files stay byte-identical to upstream and
// the next import is a copy rather than a merge.

namespace devmode {

// Is something other than the calling app keeping the radio up? Never here,
// so an app that brought Wi-Fi up is always the one that owes the teardown.
inline bool holdsRadio() { return false; }

// Stand down / pick back up around an exclusive use of the radio.
inline void pause() {}
inline void resume() {}

}  // namespace devmode
