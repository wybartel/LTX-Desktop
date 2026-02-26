import { logger } from './logger'

function toFilesystemPath(pathOrUrl: string): string {
  if (pathOrUrl.startsWith('file://')) {
    let p = decodeURIComponent(pathOrUrl.slice(7))
    if (/^\/[A-Za-z]:/.test(p)) p = p.slice(1)
    return p
  }
  return pathOrUrl
}

/**
 * Copy a generated file to the project's configured asset save folder.
 * Returns the new path + URL if successful, or the originals as fallback.
 */
export async function copyToAssetFolder(
  origPath: string,
  origUrl: string,
  assetSavePath: string | undefined | null,
): Promise<{ path: string; url: string }> {
  if (!assetSavePath || !window.electronAPI) return { path: origPath, url: origUrl }
  try {
    const fsPath = toFilesystemPath(origPath)
    await window.electronAPI.ensureDirectory(assetSavePath)
    const sep = fsPath.includes('\\') ? '\\' : '/'
    const fileName = fsPath.split(sep).pop() || fsPath.split('/').pop() || 'asset'
    const destPath = `${assetSavePath}${sep}${fileName}`
    const result = await window.electronAPI.copyFile(fsPath, destPath)
    if (result.success) {
      const normalized = destPath.replace(/\\/g, '/')
      const fileUrl = normalized.startsWith('/') ? `file://${normalized}` : `file:///${normalized}`
      return { path: destPath, url: fileUrl }
    }
  } catch (e) {
    logger.warn(`Failed to copy asset to project folder: ${e}`)
  }
  return { path: origPath, url: origUrl }
}
