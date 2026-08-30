import { Check, Copy } from 'lucide-react'
import {
  isValidElement,
  useState,
  type ComponentPropsWithoutRef,
  type ReactNode,
} from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'


interface MarkdownMessageProps {
  content: string
}

function extractText(node: ReactNode): string {
  if (typeof node === 'string' || typeof node === 'number') {
    return String(node)
  }

  if (Array.isArray(node)) {
    return node.map(extractText).join('')
  }

  if (isValidElement<{ children?: ReactNode }>(node)) {
    return extractText(node.props.children)
  }

  return ''
}

function CodeBlock({ children, ...props }: ComponentPropsWithoutRef<'pre'>) {
  const [copied, setCopied] = useState(false)

  async function copyCode() {
    await navigator.clipboard.writeText(extractText(children).replace(/\n$/, ''))
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  return (
    <div className="group relative my-4">
      <pre
        {...props}
        className="overflow-x-auto rounded-xl bg-slate-950 p-4 pr-12 text-xs leading-6 text-slate-100 [&_code]:bg-transparent [&_code]:p-0 [&_code]:text-inherit"
      >
        {children}
      </pre>
      <button
        type="button"
        onClick={() => void copyCode()}
        aria-label="复制代码"
        className="absolute top-2 right-2 grid size-8 place-items-center rounded-lg border border-slate-700 bg-slate-900 text-slate-300 opacity-80 transition hover:text-white group-hover:opacity-100"
      >
        {copied ? <Check size={15} /> : <Copy size={15} />}
      </button>
    </div>
  )
}

export function MarkdownMessage({ content }: MarkdownMessageProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: (props) => <h1 className="mt-5 mb-2 text-xl font-bold" {...props} />,
        h2: (props) => <h2 className="mt-5 mb-2 text-lg font-semibold" {...props} />,
        h3: (props) => <h3 className="mt-4 mb-2 font-semibold" {...props} />,
        p: (props) => <p className="my-2 first:mt-0 last:mb-0" {...props} />,
        ul: (props) => <ul className="my-3 list-disc space-y-1 pl-6" {...props} />,
        ol: (props) => <ol className="my-3 list-decimal space-y-1 pl-6" {...props} />,
        blockquote: (props) => (
          <blockquote
            className="my-3 border-l-4 border-indigo-200 bg-indigo-50/60 px-4 py-2 text-slate-600"
            {...props}
          />
        ),
        a: (props) => (
          <a
            className="font-medium text-indigo-600 underline decoration-indigo-200 underline-offset-2 hover:text-indigo-800"
            target="_blank"
            rel="noreferrer"
            {...props}
          />
        ),
        code: (props) => (
          <code
            className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[0.9em] text-slate-800"
            {...props}
          />
        ),
        pre: CodeBlock,
        table: (props) => (
          <div className="my-4 overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs" {...props} />
          </div>
        ),
        th: (props) => (
          <th className="border border-slate-200 bg-slate-50 px-3 py-2 font-semibold" {...props} />
        ),
        td: (props) => <td className="border border-slate-200 px-3 py-2" {...props} />,
        hr: (props) => <hr className="my-5 border-slate-200" {...props} />,
      }}
    >
      {content}
    </ReactMarkdown>
  )
}
