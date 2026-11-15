// An error as a sentence a person can act on, plus the engine's own text as the details (skin_editor/plain.py makes the sentence; this only reads it).
import { RpcError, rpc } from './engine'

export interface Said { plain: string; details: string }
export const GENERIC = "Something went wrong that this screen can't explain. Open Advanced mode to see the details."

export function sayOf(e: unknown): Said {
  if (e instanceof RpcError) {
    const plain = typeof e.data?.plain === 'string' && e.data.plain ? e.data.plain : GENERIC
    return { plain, details: `${e.message} (code ${e.code})` }
  }
  const text = e instanceof Error ? e.message : String(e)
  if (/not connected|engine answered|Failed to fetch|NetworkError/i.test(text)) return { plain: "The Studio can't reach its engine. Close the Studio and open it again.", details: text }
  return { plain: GENERIC, details: text }
}

/** A job's failure text (the engine gives jobs a plain string) as a sentence, through the engine's own table. */
export async function sayOfJobError(message: string): Promise<Said> {
  try { return await rpc<Said>('app.explain', { message: message.replace(/^[A-Za-z]+Error: /, '') }) } catch { return { plain: GENERIC, details: message } }
}
