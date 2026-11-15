/** The file picker for a replacement picture: the desktop dialog in the app, a typed path in a browser (development). Shared by Images (Advanced) and Pictures (Simple). */
export const pickImage = async (): Promise<string | undefined> => {
  if (!('__TAURI_INTERNALS__' in window)) return prompt('Path of the replacement image (png, jpg, webp or svg):')?.trim() || undefined
  const { open } = await import('@tauri-apps/plugin-dialog')
  const r = await open({ multiple: false, directory: false, title: 'Pick the replacement image', filters: [{ name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'webp', 'svg'] }] })
  return typeof r === 'string' ? r : undefined
}

/** A PNG screenshot of the game to keep in the workspace (Advanced tile organiser backdrop). */
export const pickScreenshot = async (): Promise<string | undefined> => {
  if (!('__TAURI_INTERNALS__' in window)) return prompt('Path of a PNG screenshot of the game:')?.trim() || undefined
  const { open } = await import('@tauri-apps/plugin-dialog')
  const r = await open({ multiple: false, directory: false, title: 'Pick a screenshot of the game (PNG)', filters: [{ name: 'PNG', extensions: ['png'] }] })
  return typeof r === 'string' ? r : undefined
}
