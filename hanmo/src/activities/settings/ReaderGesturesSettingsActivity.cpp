#include "ReaderGesturesSettingsActivity.h"
#include "ReaderGestureBindings.h"
#include "components/SubpageLayout.h"
#include "components/UITheme.h"
namespace fui=freeink::ui;
void ReaderGesturesSettingsActivity::onEnter(){refreshRows();UiListActivity::onEnter();}
void ReaderGesturesSettingsActivity::refreshRows(){
 for(int i=0;i<9;++i){
  auto& row=rows_[i];row={};row.actionValue=i;row.label=I18N.get(ReaderGestureBindings::labels[i]);
  const auto value=SETTINGS.*ReaderGestureBindings::fields[i];
  row.subtitle=I18N.get(ReaderGestureBindings::options(i)[value<ReaderGestureBindings::count(i)?value:0]);
  if((i==2 || i==3 || i>=5) && !mappedInput.supportsMultiTouch()){row.enabled=false;row.subtitle=tr(STR_GESTURE_UNSUPPORTED);}
 }
}
void ReaderGesturesSettingsActivity::activateIndex(int index){
 if(index<0 || index>=9 || !rows_[index].enabled)return;
 const auto field=ReaderGestureBindings::fields[index];const int count=ReaderGestureBindings::count(index);
 popup_.show(ReaderGestureBindings::labels[index],ReaderGestureBindings::options(index),count,SETTINGS.*field,[this,field,count](int value){
  if(value<0 || value>=count)return;
  const uint8_t old=SETTINGS.*field;SETTINGS.*field=value;
  if(!SETTINGS.saveToFile()){SETTINGS.*field=old;failed_=true;}
  refreshRows();requestUpdate();
 });requestUpdate();
}
bool ReaderGesturesSettingsActivity::handleCustomInput(){
 const bool handled=popup_.handleInput(mappedInput,[this]{requestUpdate();});
 if(failed_){failed_=false;constexpr StrId ok[]={StrId::STR_OK_BUTTON};popup_.show(StrId::STR_SETTINGS_SAVE_FAILED,ok,1,0,[](int){});requestUpdate();}
 return handled;
}
void ReaderGesturesSettingsActivity::render(RenderLock&& lock){if(popup_.processRender(renderer,mappedInput))return;UiListActivity::render(std::move(lock));}
void ReaderGesturesSettingsActivity::buildScreen(UiScreen& screen){
 const auto& metrics=UITheme::getInstance().getMetrics();const auto safe=UITheme::getInstance().getScreenSafeArea(renderer,true,false);
 const auto body=SubpageLayout::contentRect(safe,metrics);
 screen.setContentMarginFromScreen(fui::Insets{static_cast<int16_t>(body.y),static_cast<int16_t>(renderer.getScreenWidth()-body.x-body.width),static_cast<int16_t>(renderer.getScreenHeight()-body.y-body.height),static_cast<int16_t>(body.x)});
 fui::ListProps props;props.items=rows_.data();props.count=9;props.action=ACTION_ROW;props.inputMask=fui::InputTouch;
 props.labelText=screen.theme().smallText;props.labelText.maxLines=2;syncListViewport(screen,props,true);screen.list(props);
}
