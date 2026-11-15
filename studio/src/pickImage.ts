/** The file picker for a replacement picture: the desktop dialog in the app, a typed path in a browser (development). Shared by Images (Advanced) and Pictures (Simple). */
export const pickImage = async (): Promise<string | undefined> => {
  if (!('__TAURI_INTERNALS__' in window)) return prompt('Path of the replacement image (png, jpg, webp or svg):')?.trim() || undefined
  const { open } = await import('@tauri-apps/plugin-dialog')
  const r = await open({ multiple: false, directory: false, title: 'Pick the replacement image', filters: [{ name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'webp', 'svg'] }] })
  return typeof r === 'string' ? r : undefined
}
