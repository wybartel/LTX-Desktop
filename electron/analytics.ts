import { randomUUID } from 'crypto';
import { app } from 'electron';
import fs from 'fs';
import path from 'path';
import { isDev } from './config';

const ANALYTICS_ENDPOINT = 'https://ltx-desktop.lightricks.com/v2/ingest';
const REQUEST_TIMEOUT_MS = 5000;
const MAX_RETRIES = 3;
const RETRY_DELAYS_MS = [1000, 3000, 10000]

interface AppState {
  analyticsEnabled?: boolean
  installationId?: string
  [key: string]: unknown
}

function getAppStatePath(): string {
  return path.join(app.getPath('userData'), 'app_state.json')
}

function readAppState(): AppState {
  const statePath = getAppStatePath()
  try {
    if (fs.existsSync(statePath)) {
      return JSON.parse(fs.readFileSync(statePath, 'utf-8')) as AppState
    }
  } catch (err) {
    console.warn('[analytics] failed to read app state:', err)
  }
  return {}
}

function writeAppState(state: AppState): void {
  fs.writeFileSync(getAppStatePath(), JSON.stringify(state, null, 2))
}

export function getAnalyticsState(): { analyticsEnabled: boolean; installationId: string } {
  const state = readAppState()
  return {
    analyticsEnabled: state.analyticsEnabled !== false,
    installationId: state.installationId ?? '',
  }
}

export function setAnalyticsEnabled(enabled: boolean): void {
  const state = readAppState()
  state.analyticsEnabled = enabled
  // Generate installationId on first enable; persist forever after
  if (enabled && !state.installationId) {
    state.installationId = randomUUID()
  }
  writeAppState(state)
}

function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function isRetryable(status: number): boolean {
  return status === 429 || status >= 500
}

async function sendWithRetry(
  url: string,
  options: RequestInit,
): Promise<void> {
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
      const response = await fetch(url, { ...options, signal: controller.signal })
      clearTimeout(timeout)

      if (response.ok || !isRetryable(response.status)) return
    } catch (err) {
      console.warn('[analytics] request attempt failed:', err)
    }

    if (attempt < MAX_RETRIES) {
      await delay(RETRY_DELAYS_MS[attempt])
    }
  }
}

export async function sendAnalyticsEvent(
  eventName: string,
  extraDetails?: Record<string, unknown> | null,
): Promise<void> {
  try {
    // Skip analytics in dev builds
    if (isDev) return;

    const state = readAppState()
    if (state.analyticsEnabled === false) return

    // Generate installationId on first send
    if (!state.installationId) {
      state.installationId = randomUUID()
      writeAppState(state)
    }

    const platform = process.platform === 'darwin' ? 'mac' : process.platform === 'win32' ? 'windows' : 'linux'
    const now = Date.now()

    const payload = {
      events: [
        {
          subject: eventName,
          eventId: randomUUID(),
          eventTimestamp: now,
          event: {
            app_version: app.getVersion(),
            device_timestamp: now,
            installation_id: state.installationId,
            platform,
            extra_details: extraDetails ? JSON.stringify(extraDetails) : null,
          },
        },
      ],
    }

    // Fire-and-forget with retries — never throws
    void sendWithRetry(ANALYTICS_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    })
  } catch (err) {
    console.error('[analytics] failed to send event:', err)
  }
}
