# FM27 image map (2D images in the UI bundles)

Read-only survey of the Windows install (`fm_Data\StreamingAssets\aa\StandaloneWindows64`, build 27.0.1.2503222), 2026-11-13.
Full list: `docs/image-map.json` (every image: bundle, name, size, format, path id). Regenerate with `python tools/map_images.py` (3 s).
Thumbnails of every full-screen image: `%LOCALAPPDATA%\FM27SkinEditor\image-map\index.html` (open in a browser).

## Where the images are

- **7,471 images** in the 67 `ui-*` bundles: 1,488 textures (bitmaps), 5,697 sprites (pieces of icon atlases) and 286 SVGs (Unity VectorImage).
- **3.3 GB of `art-*` bundles** hold 3D assets: characters, hair, skies, stadiums, trophies. They are not 2D UI images and are left out (`--all` scans them).

| Bundle | What | Count |
|---|---|---|
| `ui-backgrounds_assets_.bundle` (32 MB) | league / competition wallpapers, `fm27_skin_*`, 3840x2160 | 45 textures |
| `ui-backgrounds_assets_common.bundle` (62 MB) | competition wallpapers (named "Bundesliga", "UEFA Champions League", ...), rooms, general scenes | 65 textures |
| `ui-backgrounds_assets_1x..4x` | per-UI-scale variants: VAR decision screens, premier-league, uefa-* | 9-10 each |
| `ui-prematch-backgrounds_assets_common.bundle` | pre-match lineup backgrounds | 6 |
| `ui-textures_assets_all.bundle` | `*BackgroundImage` per competition, World Cup, injury body map, start screen, misc | 315 textures + 3 SVGs |
| `ui-mainmenu-assets_assets_all.bundle` | start screen art, "what's new" images | 18 |
| `ui-icons_assets_1x..4x` | icons as sprites (about 1,420 per scale) | 5,688 sprites |
| `ui-icons_assets_common.bundle` | icons as SVG (attributes, game concepts, stats) | 281 SVGs |
| `ui-iconspriteatlases_assets_1x..4x` | the icon atlases (`sactx-*`, Crunch-compressed) | 22 |
| `ui-fonts_*` | font atlases (not images to swap) | |

## Full-screen backgrounds (195, thumbnails in the contact sheet)

**League and competition wallpapers (104).** Each competition has several copies across generations and scales, so a swap must cover every copy the game actually draws:
- `fm27_skin_<competition>` in `ui-backgrounds_assets_.bundle`, 3840x2160. Examples: bundesliga, 3-liga, dfb-frauenbundesliga, epl, efl-championship / league-one / league-two, carabao-cup, uefa-ucl / uel / uecl / supercup / womens-champions league, eredivisie, keuken-kampioen, serie-b, serie-b-cup, danish-superliga, saudiproleague, uae-pl, nwsl, wsl, wsl2, NIFL (3), fr-premiere-division.
- `*_fm26` copies, e.g. `bundesliga_fm26` and `uefa-europa_league_skin_fm26`.
- `fm-*-skin-min`, 4096x2304: bundesliga, europa, conference, super-cup.
- Display-named copies in `common`: "Bundesliga", "Premier League", "UEFA Champions League", "Carabao Cup".
- `<Competition>BackgroundImage` in `ui-textures`.
- VAR and per-scale variants (`*_2x/_3x/_4x`).

**Default wallpapers.** `fm27_skin_default`, `fm27_skin_blended`, `fm27-background-texture` and `fm-skin-v2`.

**Rooms (23).** Boardroom, Changing Room, Interview Area, Press Conference, Team Meeting and Media Room (Basic / Standard / HighEnd / StateOfTheArt).

**Pre-match (7)** and **main menu (5)**.

## How the game picks a background

The wallpaper is not chosen by the stylesheets. `#background_image` on the GameWorldBackground panel, and the `SIImage#Card-frame` of report and tool pages, are bound in code to `game.BackgroundImage.BackgroundImage`. The game selects the image for your club's competition, in the same way it paints the top bar in the club colour. Source: the Crimson skin notes, make_crimson_json.py rounds 1-2.

What a skin can do:
1. **Hide it.** This is proven in game in the Crimson skin. The editor's project option "Remove club colours" already includes these rules: wallpaper image and 3D render at opacity 0, the 10 bound card frames hidden, and a flat colour behind them.
2. **Replace the image.** Overwrite the texture inside its bundle so the game's own choice shows your picture. This is not built and not yet verified. What it needs:
   - **Which copy is drawn.** For a given competition, find out which of the copies is actually shown. The inspector can read the texture name on the live screen.
   - **Same size and a supported format.** Wallpapers are DXT5 or DXT1, sometimes Crunched (DXT5Crunched / DXT1Crunched). UnityPy can write DXT1/DXT5 or uncompressed RGBA32, but it cannot write Crunch. A Crunched texture would have to change format, which is a bigger file and an untested risk.
   - **The same safety line as the style bundles.** The `ui-backgrounds` bundles (about 100 MB) would join the vanilla snapshot, the build, the gate (untouched objects identical to vanilla) and the install with backup. The tamper check and reference hashes already cover every `ui-*` bundle.
   - **An in-game check** that the game accepts a re-encoded texture. A no-op re-save of a bundle was accepted in the placement spike.

Texture formats seen: DXT5 1,107, RGBA32 166, DXT1 129, Alpha8 47, DXT5Crunched 28, DXT1Crunched 11.
