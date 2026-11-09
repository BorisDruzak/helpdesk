import {useEffect, useContext} from 'react';
import {UNSAFE_DataRouterContext, useBlocker} from 'react-router-dom';
import {SettingsConfirmDialog} from './settings-confirm-dialog';

function RouterDraftGuard({dirty}:{dirty:boolean}) {
 const blocker=useBlocker(dirty);
 return blocker.state==='blocked'?<SettingsConfirmDialog description="Остаться и продолжить редактирование или уйти без сохранения?" cancelLabel="Остаться" confirmLabel="Уйти без сохранения" onCancel={()=>blocker.reset()} onConfirm={()=>blocker.proceed()}/>:null;
}

export function SettingsDraftGuard({dirty}:{dirty:boolean}) {
 const router=useContext(UNSAFE_DataRouterContext);
 useEffect(()=>{
  if(!dirty)return;
  const warn=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue='';};
  window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn);
 },[dirty]);
 return router?<RouterDraftGuard dirty={dirty}/>:null;
}
