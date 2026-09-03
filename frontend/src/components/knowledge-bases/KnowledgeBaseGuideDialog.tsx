import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'

interface KnowledgeBaseGuideDialogProps {
  open: boolean
  onClose: () => void
  onCreate: () => void
}

const steps = [
  ['创建知识库', '为同一主题的资料创建一个知识库，并填写便于辨认的名称。'],
  ['上传并处理文件', '进入知识库上传资料，再选择本地处理或 MinerU 解析。只有处理完成的文件才能用于问答；失败时可查看原因并重试。'],
  ['新建对话提问', '在当前知识库中新建会话，围绕资料提问，也可以继续追问。'],
  ['查看回答来源', '展开回答的来源，核对引用的文档和片段。资料不足时，补充相关文档后再提问。'],
]

export function KnowledgeBaseGuideDialog({ open, onClose, onCreate }: KnowledgeBaseGuideDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = dialogRef.current
    if (open && !dialog?.open) dialog?.showModal()
    if (!open && dialog?.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="knowledge-base-guide-title"
      onCancel={(event) => {
        event.preventDefault()
        onClose()
      }}
      onClose={onClose}
      className="fixed inset-0 m-auto max-h-[85dvh] w-[calc(100%-2rem)] max-w-lg overflow-y-auto rounded-3xl border border-slate-200 bg-white p-6 text-slate-900 shadow-2xl backdrop:bg-slate-950/35 backdrop:backdrop-blur-sm md:p-7"
    >
      <div className="flex items-start justify-between gap-4">
        <h2 id="knowledge-base-guide-title" className="text-xl font-semibold">知识库使用指南</h2>
        <button type="button" onClick={onClose} aria-label="关闭使用指南" className="rounded-lg p-2 text-slate-500 hover:bg-slate-100">
          <X size={20} />
        </button>
      </div>
      <ol className="mt-6 space-y-5">
        {steps.map(([title, description], index) => (
          <li key={title} className="flex gap-3">
            <span aria-hidden="true" className="grid size-7 shrink-0 place-items-center rounded-full bg-indigo-50 text-sm font-semibold text-indigo-600">{index + 1}</span>
            <div>
              <h3 className="font-semibold">{title}</h3>
              <p className="mt-1 text-sm leading-6 text-slate-500">{description}</p>
            </div>
          </li>
        ))}
      </ol>
      <div className="mt-7 flex justify-end gap-3">
        <button type="button" onClick={onClose} className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold hover:bg-slate-50">我知道了</button>
        <button type="button" onClick={onCreate} className="rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700">开始创建</button>
      </div>
    </dialog>
  )
}
