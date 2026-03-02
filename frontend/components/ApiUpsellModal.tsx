import { useEffect, useMemo, useState } from 'react'
import { Sparkles, X } from 'lucide-react'
import { LtxApiKeyInput, LtxApiKeyHelperRow } from './LtxApiKeyInput'

export interface ApiUpsellCopy {
  title: string
  description: string
  primaryActionLabel: string
  secondaryActionLabel?: string
}

export interface ApiUpsellModalProps {
  isOpen: boolean
  onClose: () => void
  onSaveApiKey: (apiKey: string) => Promise<void> | void
  copy: ApiUpsellCopy
  blocking?: boolean
}

export function buildProApiUpsellCopy(): ApiUpsellCopy {
  return {
    title: 'Enable Pro Generation',
    description:
      'Pro generation runs through the LTX API for higher quality output. Add your API key to continue with Pro.',
    primaryActionLabel: 'Save key and continue',
    secondaryActionLabel: 'Keep using Fast',
  }
}

export function ApiUpsellModal({
  isOpen,
  onClose,
  onSaveApiKey,
  copy,
  blocking = false,
}: ApiUpsellModalProps) {
  const [apiKey, setApiKey] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return
    setApiKey('')
    setError(null)
    setIsSaving(false)
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !isSaving && !blocking) {
        onClose()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [blocking, isOpen, isSaving, onClose])

  const canSubmit = useMemo(() => apiKey.trim().length > 0 && !isSaving, [apiKey, isSaving])

  const handleSave = async () => {
    const trimmedKey = apiKey.trim()
    if (!trimmedKey) {
      setError('Please enter a valid LTX API key.')
      return
    }

    setIsSaving(true)
    setError(null)
    try {
      await onSaveApiKey(trimmedKey)
      onClose()
    } catch (err) {
      if (err instanceof Error && err.message.trim()) {
        setError(err.message)
      } else {
        setError('Failed to save API key.')
      }
    } finally {
      setIsSaving(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-[560px] rounded-xl border border-zinc-700 bg-zinc-900 shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/15 text-blue-300">
              <Sparkles className="h-4 w-4" />
            </div>
            <h2 className="text-base font-semibold text-zinc-100">{copy.title}</h2>
          </div>
          {!blocking && (
            <button
              onClick={onClose}
              disabled={isSaving}
              className="rounded-lg p-1.5 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300 disabled:cursor-not-allowed disabled:opacity-50"
              aria-label="Close API upsell modal"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        <div className="space-y-4 px-5 py-5">
          <p className="text-sm leading-relaxed text-zinc-300">{copy.description}</p>

          <div>
            <label htmlFor="ltx-api-key-input" className="mb-2 block text-sm font-medium text-zinc-200">
              LTX API Key
            </label>
            <LtxApiKeyInput
              id="ltx-api-key-input"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder="Paste your API key"
            />
            <LtxApiKeyHelperRow />
          </div>

          {error && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
              {error}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-zinc-800 px-5 py-4">
          {!blocking && (
            <button
              onClick={onClose}
              disabled={isSaving}
              className="rounded-lg border border-zinc-700 px-3.5 py-2 text-sm font-medium text-zinc-300 transition-colors hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {copy.secondaryActionLabel ?? 'Not now'}
            </button>
          )}
          <button
            onClick={handleSave}
            disabled={!canSubmit}
            className="rounded-lg bg-blue-600 px-3.5 py-2 text-sm font-semibold text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-500"
          >
            {isSaving ? 'Saving...' : copy.primaryActionLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
