import {useEffect,useRef} from 'react';
import {Button} from '../../components/ui/button';

export function SettingsConfirmDialog({description,cancelLabel,confirmLabel,onCancel,onConfirm}:{description:string;cancelLabel:string;confirmLabel:string;onCancel:()=>void;onConfirm:()=>void}) {
 const ref=useRef<HTMLDialogElement>(null);
 useEffect(()=>{const dialog=ref.current!;dialog.showModal();return()=>{if(dialog.open)dialog.close();};},[]);
 return <dialog ref={ref} role="alertdialog" aria-labelledby="settings-confirm-title" aria-describedby="settings-confirm-description" onCancel={event=>{event.preventDefault();onCancel();}} className="m-auto w-[calc(100%-2rem)] max-w-lg rounded-panel border border-border bg-white p-6 shadow-xl backdrop:bg-black/30">
  <h2 id="settings-confirm-title" className="text-lg font-semibold">Есть несохранённые изменения</h2>
  <p id="settings-confirm-description" className="my-4">{description}</p>
  <div className="flex flex-wrap gap-3"><Button autoFocus onClick={onCancel}>{cancelLabel}</Button><Button variant="outline" onClick={onConfirm}>{confirmLabel}</Button></div>
 </dialog>;
}
