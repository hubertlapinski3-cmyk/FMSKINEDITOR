# Phase 9 M4 start, offline (2026-11-14)

Goal (plan): images, icons, fonts, placeholders, notice; exit "icons and textures show; data is labelled".

## What the render carries today
On six Squad layouts (Loans, Medical Centre, Tactics, Atmosphere, Training tiles and SquadScreen) the render sees `-unity-font-definition` 140 times (status partial: "a game asset, not loaded"), `background-image` 7 times (partial: "drawn only when the asset resolves") and `-unity-background-image-tint-color` twice (partial: tint not applied). So fonts are the main unresolved asset, images second.

## Mechanism found: how an `asset(F:P)` value resolves
A stylesheet's `asset(F:P)` is a Unity PPtr: file id F is an index into the externals of the bundle that holds the sheet (`externals[F-1]` is an `archive:/CAB-...` name), P is the object's path id inside that file. A CAB name maps to exactly one bundle: 551 CABs across the game's bundles map in 11 s (`workspace/notes/cab-to-bundle-20261114.json`). Worked example, the shared sheets' external 11 + path 5636211117028388537 -> `ui-fonts_assets_production.bundle`, a MonoBehaviour named **ABCSocial-Regular SDF**: the game's UI font is a TextMeshPro SDF font asset (ABC Social), not a TTF. The second sample (Medical Centre `background-image`, file 3) is a layout inline sheet, so its F indexes the externals of the LAYOUT bundle, not the shared-sheets bundle: the resolver must be given the bundle the sheet was read from.

## Plan for the rest of M4 (offline)
1. `render.assets.resolve(source_bundle, F, P)` -> {bundle, type, name} with the CAB map cached; tests on the two worked examples.
2. Images: Texture2D / Sprite targets to PNG data URLs through the existing `images.thumbnail` / `render_icon` paths; icon classes through `images.icon_classes` (atlas sprites).
3. Fonts: the SDF font asset names the family (ABC Social etc.); the stand-in stays an installed font and each text node says which family it should be (the notice already says fonts are approximated).
4. Tint multiplication for `-unity-background-image-tint-color`, with the status flipped from partial only where applied.
5. Labelled data: bound text chips show the delivered text (capture) or the layout sample (`DebugDisplay`), marked as sample; the permanent notice lists what is placeholder.
Exit check: the Loans, Medical Centre and Squad tiles render with their icons and textures, and every placeholder is labelled; compare icon boxes with the captures.