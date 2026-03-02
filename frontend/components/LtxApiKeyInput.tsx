import React, { forwardRef } from 'react'
import { ExternalLink, KeyRound } from 'lucide-react'

interface LtxApiKeyInputProps {
  value: string
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  placeholder?: string
  id?: string
  stopPropagation?: boolean
  className?: string
}

export const LtxApiKeyInput = forwardRef<HTMLInputElement, LtxApiKeyInputProps>(
  ({ value, onChange, placeholder = 'Paste your API key', id, stopPropagation, className }, ref) => {
    return (
      <div className={`relative ${className ?? ''}`}>
        <KeyRound className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <input
          ref={ref}
          id={id}
          type="password"
          value={value}
          onChange={onChange}
          onClick={stopPropagation ? (e) => e.stopPropagation() : undefined}
          placeholder={placeholder}
          autoComplete="off"
          className="w-full rounded-lg border border-zinc-700 bg-zinc-900 py-2.5 pl-9 pr-3 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
    )
  },
)
LtxApiKeyInput.displayName = 'LtxApiKeyInput'

interface LtxApiKeyHelperRowProps {
  stopPropagation?: boolean
}

export function LtxApiKeyHelperRow({ stopPropagation }: LtxApiKeyHelperRowProps) {
  return (
    <div className="mt-2 flex items-center justify-between gap-3">
      <span className="text-xs text-zinc-500">Your key stays in your local app settings.</span>
      <button
        type="button"
        onClick={(e) => {
          if (stopPropagation) e.stopPropagation()
          window.electronAPI.openLtxApiKeyPage()
        }}
        className="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
      >
        Get API key
        <ExternalLink className="h-3 w-3" />
      </button>
    </div>
  )
}
