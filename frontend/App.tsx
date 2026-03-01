import { useCallback, useEffect, useRef, useState } from 'react'
import { Loader2, AlertCircle, Settings, FileText } from 'lucide-react'
import { ProjectProvider, useProjects } from './contexts/ProjectContext'
import { KeyboardShortcutsProvider } from './contexts/KeyboardShortcutsContext'
import { AppSettingsProvider, useAppSettings } from './contexts/AppSettingsContext'
import { KeyboardShortcutsModal } from './components/KeyboardShortcutsModal'
import { useBackend } from './hooks/use-backend'
import { logger } from './lib/logger'
import { Home } from './views/Home'
import { Project } from './views/Project'
import { Playground } from './views/Playground'
import { FirstRunSetup } from './components/FirstRunSetup'
import { PythonSetup } from './components/PythonSetup'
import { SettingsModal, type SettingsTabId } from './components/SettingsModal'
import { LogViewer } from './components/LogViewer'
import { ApiUpsellModal, buildProApiUpsellCopy } from './components/ApiUpsellModal'
import { Button } from './components/ui/button'

type SetupState = 'loading' | { needsSetup: boolean; needsLicense: boolean }

function AppContent() {
  const { currentView } = useProjects()
  const { status, processStatus, isLoading: backendLoading, error: backendError } = useBackend()
  const { settings, saveLtxApiKey, forceApiGenerations, isLoaded } = useAppSettings()

  const [pythonReady, setPythonReady] = useState<boolean | null>(null)
  const [backendStarted, setBackendStarted] = useState(false)
  const [setupState, setSetupState] = useState<SetupState>('loading')
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [settingsInitialTab, setSettingsInitialTab] = useState<SettingsTabId | undefined>(undefined)
  const [isLogViewerOpen, setIsLogViewerOpen] = useState(false)
  const [isFinalizingFirstRun, setIsFinalizingFirstRun] = useState(false)
  const [firstRunFinalizeError, setFirstRunFinalizeError] = useState<string | null>(null)
  const setupCompletionInFlightRef = useRef<Promise<void> | null>(null)

  const baseUpsellCopy = buildProApiUpsellCopy()
  const forcedApiUpsellCopy = {
    ...baseUpsellCopy,
    title: 'Connect LTX API',
    description: 'This app is configured for API-only generation. Add your API key to continue.',
    primaryActionLabel: 'Save API key',
    secondaryActionLabel: undefined,
  }

  const isBackendRestarting = processStatus === 'restarting'
  const isBackendDead = processStatus === 'dead'

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail
      if (detail?.tab) setSettingsInitialTab(detail.tab)
      setIsSettingsOpen(true)
    }
    window.addEventListener('open-settings', handler)
    return () => window.removeEventListener('open-settings', handler)
  }, [])

  useEffect(() => {
    const check = async () => {
      try {
        const result = await window.electronAPI.checkPythonReady()
        setPythonReady(result.ready)
      } catch (e) {
        logger.error(`Failed to check Python readiness: ${e}`)
        setPythonReady(true)
      }
    }
    void check()
  }, [])

  useEffect(() => {
    if (pythonReady !== true || backendStarted) return
    setBackendStarted(true)
    const start = async () => {
      try {
        logger.info('Starting Python backend...')
        await window.electronAPI.startPythonBackend()
        logger.info('Python backend started successfully')
      } catch (e) {
        logger.error(`Failed to start Python backend: ${e}`)
      }
    }
    void start()
  }, [pythonReady, backendStarted])

  useEffect(() => {
    const checkFirstRun = async () => {
      try {
        const next = await window.electronAPI.checkFirstRun()
        setSetupState(next)
      } catch (e) {
        logger.error(`Failed to check first run: ${e}`)
        setSetupState({ needsSetup: false, needsLicense: false })
      }
    }
    void checkFirstRun()
  }, [])

  const handleFirstRunComplete = useCallback(async () => {
    if (setupCompletionInFlightRef.current) {
      return setupCompletionInFlightRef.current
    }

    setFirstRunFinalizeError(null)
    setIsFinalizingFirstRun(true)

    const inFlightPromise = (async () => {
      const ok = await window.electronAPI.completeSetup()
      if (!ok) {
        throw new Error('Failed to complete setup.')
      }
      setSetupState({ needsSetup: false, needsLicense: false })
    })()

    setupCompletionInFlightRef.current = inFlightPromise

    try {
      await inFlightPromise
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to finalize setup.'
      setFirstRunFinalizeError(message)
      throw e
    } finally {
      setupCompletionInFlightRef.current = null
      setIsFinalizingFirstRun(false)
    }
  }, [])

  const handleAcceptLicense = useCallback(async () => {
    const ok = await window.electronAPI.acceptLicense()
    if (!ok) {
      throw new Error('Failed to save license acceptance.')
    }
    setSetupState((prev) => {
      if (prev === 'loading') return prev
      return { ...prev, needsLicense: false }
    })
  }, [])

  const saveApiKeyForFirstRun = useCallback(
    async (apiKey: string) => {
      const trimmed = apiKey.trim()
      if (!trimmed) {
        throw new Error('Please enter a valid LTX API key.')
      }

      await saveLtxApiKey(trimmed)
      setFirstRunFinalizeError(null)
    },
    [saveLtxApiKey],
  )

  const isForcedFirstRun =
    setupState !== 'loading' && setupState.needsSetup && !setupState.needsLicense && forceApiGenerations

  const shouldAutoFinalizeForcedFirstRun =
    isForcedFirstRun && isLoaded && settings.hasLtxApiKey && !isFinalizingFirstRun && !firstRunFinalizeError

  useEffect(() => {
    if (!shouldAutoFinalizeForcedFirstRun) return
    void handleFirstRunComplete().catch(() => {
      // Error state is handled via firstRunFinalizeError.
    })
  }, [shouldAutoFinalizeForcedFirstRun, handleFirstRunComplete])

  const restartingOverlay = isBackendRestarting ? (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="rounded-lg border border-zinc-700 bg-zinc-900/95 px-6 py-4 text-center shadow-xl">
        <div className="flex items-center justify-center gap-2 text-zinc-100">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="font-medium">Reconnecting...</span>
        </div>
        <p className="mt-2 text-sm text-zinc-400">The backend process stopped unexpectedly. Attempting to restart...</p>
      </div>
    </div>
  ) : null

  if (pythonReady === null) {
    return (
      <div className="h-screen bg-background flex items-center justify-center">
        <Loader2 className="h-8 w-8 text-primary animate-spin" />
      </div>
    )
  }

  if (pythonReady === false) {
    return <PythonSetup onReady={() => setPythonReady(true)} />
  }

  if (isBackendDead) {
    return (
      <div className="h-screen bg-background flex items-center justify-center p-6">
        <div className="w-full max-w-5xl rounded-xl border border-zinc-700 bg-zinc-900/80 p-6 shadow-2xl">
          <div className="text-center">
            <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-foreground mb-2">The backend process crashed and could not be restarted</h2>
            <p className="text-muted-foreground mb-4">Review the logs below and restart the application.</p>
          </div>
          <div className="h-[50vh]">
            <LogViewer isOpen={true} onClose={() => {}} embedded={true} />
          </div>
          <div className="mt-4 flex justify-center">
            <Button onClick={() => window.location.reload()}>Restart Application</Button>
          </div>
        </div>
      </div>
    )
  }

  if (backendLoading || setupState === 'loading') {
    return (
      <div className="relative h-screen w-screen">
        <div className="h-screen bg-background flex items-center justify-center">
          <div className="text-center">
            <Loader2 className="h-12 w-12 text-primary animate-spin mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-foreground mb-2">Starting LTX Desktop...</h2>
            <p className="text-muted-foreground">Initializing the inference engine</p>
          </div>
        </div>
        {restartingOverlay}
      </div>
    )
  }

  if (backendError && !status.connected) {
    return (
      <div className="h-screen bg-background flex items-center justify-center">
        <div className="text-center max-w-md">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-foreground mb-2">Connection Failed</h2>
          <p className="text-muted-foreground mb-4">{backendError}</p>
          <Button onClick={() => window.location.reload()}>Retry</Button>
        </div>
      </div>
    )
  }

  if (setupState.needsLicense) {
    const licenseOnly = forceApiGenerations || !setupState.needsSetup
    return (
      <FirstRunSetup
        showLicenseStep
        licenseOnly={licenseOnly}
        onAcceptLicense={handleAcceptLicense}
        onComplete={
          licenseOnly
            ? async () => {
                setSetupState((prev) => {
                  if (prev === 'loading') return prev
                  return { ...prev, needsLicense: false }
                })
              }
            : handleFirstRunComplete
        }
      />
    )
  }

  if (setupState.needsSetup && !forceApiGenerations) {
    return <FirstRunSetup showLicenseStep={false} onComplete={handleFirstRunComplete} />
  }

  const showGlobalControls = currentView !== 'home' && status.connected && !setupState.needsSetup
  const shouldBlockUntilSettingsLoaded = forceApiGenerations && !isLoaded
  const shouldShowForcedFirstRunUpsell = isForcedFirstRun && isLoaded && !settings.hasLtxApiKey
  const shouldShowGlobalForcedUpsell = forceApiGenerations && !setupState.needsSetup && isLoaded && !settings.hasLtxApiKey
  const shouldBlockForApiKey = shouldShowForcedFirstRunUpsell || shouldShowGlobalForcedUpsell

  const renderView = () => {
    switch (currentView) {
      case 'home':
        return <Home />
      case 'project':
        return <Project />
      case 'playground':
        return <Playground />
      default:
        return <Home />
    }
  }

  return (
    <div className="relative h-screen w-screen">
      {renderView()}

      {showGlobalControls && (
        <div className="fixed top-[18px] right-3 z-50 flex items-center gap-1">
          <button
            onClick={() => setIsLogViewerOpen(true)}
            className="h-8 w-8 flex items-center justify-center rounded-md text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
            title="View Backend Logs"
          >
            <FileText className="h-4 w-4" />
          </button>
          <button
            onClick={() => setIsSettingsOpen(true)}
            className="h-8 w-8 flex items-center justify-center rounded-md text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
            title="Settings"
          >
            <Settings className="h-4 w-4" />
          </button>
        </div>
      )}

      <LogViewer isOpen={isLogViewerOpen} onClose={() => setIsLogViewerOpen(false)} />
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => {
          setIsSettingsOpen(false)
          setSettingsInitialTab(undefined)
        }}
        initialTab={settingsInitialTab}
      />
      <ApiUpsellModal
        isOpen={shouldBlockForApiKey}
        blocking
        onClose={() => {
          // Blocking mode intentionally does not allow close.
        }}
        onSaveApiKey={async (apiKey) => {
          if (isForcedFirstRun) {
            await saveApiKeyForFirstRun(apiKey)
            return
          }
          await saveLtxApiKey(apiKey)
        }}
        copy={forcedApiUpsellCopy}
      />

      {shouldBlockUntilSettingsLoaded && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="flex items-center gap-2 text-sm text-zinc-200">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading settings...
          </div>
        </div>
      )}

      {isForcedFirstRun && isLoaded && settings.hasLtxApiKey && isFinalizingFirstRun && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="flex items-center gap-2 text-sm text-zinc-200">
            <Loader2 className="h-4 w-4 animate-spin" />
            Finalizing setup...
          </div>
        </div>
      )}

      {isForcedFirstRun && firstRunFinalizeError && (
        <div className="fixed inset-0 z-[61] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-xl border border-zinc-700 bg-zinc-900 p-5 text-zinc-100">
            <h3 className="text-base font-semibold">Setup finalization failed</h3>
            <p className="mt-2 text-sm text-zinc-300">{firstRunFinalizeError}</p>
            <div className="mt-4 flex justify-end">
              <Button
                onClick={() => {
                  void handleFirstRunComplete().catch(() => {
                    // Error state is already captured.
                  })
                }}
              >
                Retry
              </Button>
            </div>
          </div>
        </div>
      )}

      {restartingOverlay}
    </div>
  )
}

export default function App() {
  return (
    <ProjectProvider>
      <KeyboardShortcutsProvider>
        <AppSettingsProvider>
          <AppContent />
          <KeyboardShortcutsModal />
        </AppSettingsProvider>
      </KeyboardShortcutsProvider>
    </ProjectProvider>
  )
}
