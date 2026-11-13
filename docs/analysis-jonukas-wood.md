# Analysis: Jonukas Skin - Wood (`C:\Users\Admin\Downloads\jonukas-wood`)

Read-only analysis, 2026-11-13. Numbers come from the editor's Compare tab (`skin_editor/skins.py`) and from reading the sheets.

## What it is

- **A native FM27 skin, not a mod.** It replaces no game files. FM27 loads USS skins from the user folder: put `skin.json` in `Documents\Sports Interactive\Football Manager 27\skins\<name>\` (macOS: `~/Library/Application Support/Sports Interactive/Football Manager 27/skins/`), then pick the skin in Preferences, next to "Reload Skin". Sources: the skin's `LIESMICH - README.txt` and the FM Dugout Template's INSTALL.md.
- **Design:** a printed club magazine ("Vereinsheft"). Tiles become paper sheets lying on a desk. It comes in four looks: wood, paper, dark and dark paper, each a sibling folder of 31 to 39 MB.
- **Not installed here.** The FM27 user folder on this machine has no `skins` folder.

## Structure (58 files, 39.4 MB)

`skin.json` lists 10 sheets in load order. Later sheets win ties.

| Sheet | :root tokens | Rules | Role |
|---|---|---|---|
| heft-symbole.uss | 46 | 2 | image tokens `--bild-*` (38 PNGs) and font tokens; recolours every `.game-concepts-*` icon to ink |
| heft-symbolfarben.uss | 0 | 324 | puts SI's own icon colours back over that (state colours, checkmarks) |
| heft-farben.uss | 1,334 | 0 | the palette: vanilla colour tokens overridden |
| heft-regeln.uss | 0 | 687 | component rules (surfaces, borders, text colours) |
| heft-schrift.uss | 2 | 2 | thematic and condensed font families |
| heft-papier.uss | 0 | 24 | tiles and blocks as 9-sliced paper sheets |
| heft-kulisse.uss | 0 | 12 | the desk behind everything; hides SI's club-coloured backdrops |
| heft-form.uss | 16 | 1 | radii (0 or 3 px), translucent paper surfaces, the tooltip as a sheet |
| heft-taktik.uss | 16 | 26 | tactics colours in paper and khaki tones |
| heft-feinschliff.uss | 38 | 872 | final pass: fonts, ink text outlines, per-screen fixes |

**Totals**
- **1,950 rules.** Most used properties: background-color 701, `-unity-background-image-tint-color` 589, color 305, border-color 228, background-image 194, `-unity-text-outline-width` 136, 9-slice properties about 100 each, `-unity-font-definition` 110.
- **1,084 vanilla tokens changed**, 1,040 of them colours. The palette moves from SI's dark navy and purple to ink `#1C1A16`, paper `#FFFDF8` / `#DAD7D0`, and blue accents (`#1396EC`, `#0B5788`).
- **46 own tokens:** 38 images (`--bild-*`) and 8 fonts (`--schrift-*`).
- **47 assets, all present and all used:**
  - 9 TTF fonts (the Heft family);
  - large photos: the desk `tisch` at 7.5 MB, the loading and start-screen pictures at about 5–6 MB each, the floodlit pitch;
  - paper textures (`blatt`, `hochblatt`, `haengeblatt`, `flachblatt`, `karton`);
  - small markers, star ratings and a red line.

## Techniques worth learning from

1. **Images through USS, not bundles.**
   - `background-image: var(--bild-tisch)` with `url("tisch-….png")`, plus `-unity-background-scale-mode: scale-and-crop` and positioned offsets so the strips line up as one desk.
   - Paper is a 9-slice (`-unity-slice-* 40`, `tiled`, scale 0.5–1). That keeps the torn edge, and the centre tiles the paper fibre (602 slice declarations).
2. **Killing the club colours without code.** The report-page wallpaper (`#Card-frame`, which we found is bound in code) is made invisible with `--unity-image-tint-color: #00000000`. Its children reset it to white, because custom properties inherit. The desk is then drawn on `#Card-frame > #Header` and `#GridSafeArea`. 44 uses of this tint trick.
3. **Every icon recoloured by class.** `.game-concepts-*_large/_medium/_small { -unity-background-image-tint-color; --unity-image-tint-color }` turns the game's atlas icons to ink. Light club bars (`#MainNav.nav-on-light`) get their own branch. This confirms that icons can be restyled per class from USS without touching the atlas.
4. **Text as ink.** FM paints club and player names white in code (a `<color>` tag in the text). The skin puts a 1–1.3 px ink outline on all `SIText`, and uses thinned fonts so that white names print as ink (136 outline-width declarations).
5. **Layout touches:**
   - the crest as a sticker (`#ClubBadgeStyleSetter { rotate: -6deg; border 3px }`);
   - 7 rotations, 5 scales and 13 translations;
   - 12 `display: none` (SI tool backgrounds, the secondary nav texture).
6. **Careful versioning.** Hashed asset names (`tisch-f3afa8b1.png`) and comments that date in-game findings and the author's checks. The notes describe a build script (`heft_test.py --release`) that writes the hashed file names.

## Compared with what our editor does

| | Jonukas (native USS skin) | FM27 Skin Editor (bundle patch) |
|---|---|---|
| Install | copy a folder, pick it in Preferences | patch game bundles, backup, gate |
| Survives game updates | yes (USS keeps working; spots can drift) | no (Steam restores the bundles; rebuild needed) |
| Colours and rules | yes | yes |
| Images, icons, fonts | through `url()` in USS, per class | texture, atlas and SVG swaps inside bundles |
| Can change code-bound things | only hide or tint them | the same limits (bundles hold no code) |
| Risk | none to game files | game files changed (with backup and checks) |

## Recommendations

1. **Add an "Export as native skin" option to the editor.** It would write `skins\<project>\skin.json` and one USS sheet:
   - token overrides as `:root`;
   - scoped rules as rules;
   - the club-colour option as these USS rules;
   - icon and wallpaper swaps as `background-image: url()` rules on the classes that draw them, with the PNGs beside the sheet.

   This needs no bundle writes and survives updates. The bundle route would stay for things USS cannot reach. One part needs research: mapping each icon to its USS class (e.g. `win_small` -> `.game-concepts-win_small`).
2. **The Compare tab already shows this skin against vanilla.** "Preview its colours" shows its palette on the measured screens. It can't show its images, fonts or outlines: those need the game.
3. **Use it in game:** install the folder under `Documents\Sports Interactive\Football Manager 27\skins\` and pick it in Preferences. If our bundle skin "Mine" is installed at the same time, both apply. The USS skin loads on top, so its rules usually win.
