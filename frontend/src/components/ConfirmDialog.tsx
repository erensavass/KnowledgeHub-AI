import { useEffect, useRef } from 'react'

export function ConfirmDialog({ open, title, description, onConfirm, onClose }: {
  open: boolean; title: string; description: string; onConfirm(): void; onClose(): void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const cancelRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) { dialog.showModal(); cancelRef.current?.focus() }
    if (!open && dialog.open) dialog.close()
  }, [open])
  return <dialog ref={ref} onCancel={onClose} onClose={onClose} className="w-[min(28rem,calc(100%-2rem))] rounded-xl bg-white p-0 text-slate-900 shadow-xl backdrop:bg-black/50 dark:bg-slate-900 dark:text-white">
    <div className="p-6"><h2 className="text-lg font-semibold">{title}</h2><p className="mt-2 text-sm text-slate-500">{description}</p>
      <div className="mt-6 flex justify-end gap-3"><button ref={cancelRef} autoFocus className="rounded-lg border px-4 py-2" onClick={onClose}>Cancel</button><button className="rounded-lg bg-red-600 px-4 py-2 text-white" onClick={onConfirm}>Delete</button></div>
    </div>
  </dialog>
}
