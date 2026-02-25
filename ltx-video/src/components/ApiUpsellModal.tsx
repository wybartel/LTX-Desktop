import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, ExternalLink, KeyRound, Sparkles, X } from 'lucide-react'

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
  initialApiKey?: string
  getApiKeyUrl?: string
  getApiKeyLabel?: string
}

const DEFAULT_API_KEY_URL = 'https://console.ltx.video/api-keys/'

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
  initialApiKey = '',
  getApiKeyUrl = DEFAULT_API_KEY_URL,
  getApiKeyLabel = 'Get API key',
}: ApiUpsellModalProps) {
  const [apiKey, setApiKey] = useState(initialApiKey)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return
    setApiKey(initialApiKey)
    setError(null)
    setIsSaving(false)
  }, [isOpen, initialApiKey])

  useEffect(() => {
    if (!isOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !isSaving) {
        onClose()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [isOpen, isSaving, onClose])

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
          <button
            onClick={onClose}
            disabled={isSaving}
            className="rounded-lg p-1.5 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300 disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Close API upsell modal"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 px-5 py-5">
          <p className="text-sm leading-relaxed text-zinc-300">{copy.description}</p>

          <div className="rounded-lg border border-zinc-700 bg-zinc-800/40 p-3">
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-zinc-400">
              <CheckCircle2 className="h-3.5 w-3.5 text-green-400" />
              LTX API Benefits
            </div>
            <ul className="space-y-1.5 text-sm text-zinc-300">
              <li className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-zinc-500" />
                Faster generation turnaround
              </li>
              <li className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-zinc-500" />
                No local model warmup required
              </li>
            </ul>
          </div>

          <div>
            <label htmlFor="ltx-api-key-input" className="mb-2 block text-sm font-medium text-zinc-200">
              LTX API Key
            </label>
            <div className="relative">
              <KeyRound className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
              <input
                id="ltx-api-key-input"
                type="password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                placeholder="Paste your API key"
                autoComplete="off"
                className="w-full rounded-lg border border-zinc-700 bg-zinc-900 py-2.5 pl-9 pr-3 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="mt-2 flex items-center justify-between gap-3">
              <span className="text-xs text-zinc-500">Your key stays in your local app settings.</span>
              <a
                href={getApiKeyUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
              >
                {getApiKeyLabel}
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          </div>

          {error && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
              {error}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-zinc-800 px-5 py-4">
          <button
            onClick={onClose}
            disabled={isSaving}
            className="rounded-lg border border-zinc-700 px-3.5 py-2 text-sm font-medium text-zinc-300 transition-colors hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {copy.secondaryActionLabel ?? 'Not now'}
          </button>
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
