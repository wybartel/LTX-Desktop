export const FORCED_API_VIDEO_RESOLUTIONS = ['1080p', '1440p', '2160p'] as const
export const FORCED_API_VIDEO_DURATIONS = [6, 8, 10] as const
export const FORCED_API_VIDEO_FPS = [25, 50] as const
export const FORCED_API_VIDEO_MODELS = ['fast', 'pro'] as const

export type ForcedApiVideoResolution = (typeof FORCED_API_VIDEO_RESOLUTIONS)[number]
export type ForcedApiVideoDuration = (typeof FORCED_API_VIDEO_DURATIONS)[number]
export type ForcedApiVideoFps = (typeof FORCED_API_VIDEO_FPS)[number]
export type ForcedApiVideoModel = (typeof FORCED_API_VIDEO_MODELS)[number]

type ForcedVideoSettingsShape = {
  model: string
  duration: number
  videoResolution: string
  fps: number
}

function nearestNumber(value: number, candidates: readonly number[]): number {
  let best = candidates[0]
  let minDiff = Math.abs(value - best)
  for (const candidate of candidates.slice(1)) {
    const diff = Math.abs(value - candidate)
    if (diff < minDiff) {
      best = candidate
      minDiff = diff
    }
  }
  return best
}

export function normalizeForcedModel(value: string): ForcedApiVideoModel {
  if (FORCED_API_VIDEO_MODELS.includes(value as ForcedApiVideoModel)) {
    return value as ForcedApiVideoModel
  }
  return 'fast'
}

export function normalizeForcedResolution(value: string): ForcedApiVideoResolution {
  if (FORCED_API_VIDEO_RESOLUTIONS.includes(value as ForcedApiVideoResolution)) {
    return value as ForcedApiVideoResolution
  }
  return '1080p'
}

export function clampForcedDuration(value: number): ForcedApiVideoDuration {
  const rounded = Math.round(value)
  return nearestNumber(rounded, FORCED_API_VIDEO_DURATIONS) as ForcedApiVideoDuration
}

export function normalizeForcedFps(value: number): ForcedApiVideoFps {
  const rounded = Math.round(value)
  return nearestNumber(rounded, FORCED_API_VIDEO_FPS) as ForcedApiVideoFps
}

export function sanitizeForcedApiVideoSettings<T extends ForcedVideoSettingsShape>(
  settings: T,
): T {
  const nextResolution = normalizeForcedResolution(settings.videoResolution)
  const nextDuration = clampForcedDuration(settings.duration)
  const nextFps = normalizeForcedFps(settings.fps)
  const nextModel = normalizeForcedModel(settings.model)

  if (
    nextResolution === settings.videoResolution &&
    nextDuration === settings.duration &&
    nextFps === settings.fps &&
    nextModel === settings.model
  ) {
    return settings
  }

  return {
    ...settings,
    model: nextModel,
    videoResolution: nextResolution,
    duration: nextDuration,
    fps: nextFps,
  }
}
