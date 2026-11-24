// UI1b: the small pieces shared by the Game Layouts sidebar, the layout tab canvas and App.
// Everything here is view state only; layout files are written exclusively by the engine's
// customlayout.* RPCs (see engine.ts / CustomLayouts.tsx).

/** One tile of a composition, normalised from either render.preview's hosts or render.screen's hosts. */
export interface LayoutTile {
  /** Stable unique identity for React/selection: preview hosts do not all carry a distinct cell_index. */
  key: string
  cell_index: number
  element_id: string
  x: number
  y: number
  w: number
  h: number
  px?: { left: number; top: number; width: number; height: number }
  /** The game's own size limits for this cell. A zero max means unbounded. */
  limits?: { min_w?: number; min_h?: number; max_w?: number; max_h?: number }
}

/** The tile currently selected in Game Layouts mode (in the canvas or in the sidebar hierarchy). */
export interface LayoutSelection {
  composition: string
  tile: LayoutTile
}

/** Tabs are either an editable project file or a Game Layouts canvas. `active` stores this key. */
export const layoutTabId = (name: string) => 'layout:' + name
export const fileTabId = (path: string) => 'file:' + path
