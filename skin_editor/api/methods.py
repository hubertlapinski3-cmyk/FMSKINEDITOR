"""The API's method table: one named, schema-checked method per engine operation. Each entry also records the HTTP route of the
first server, so the two surfaces can be proven equal (tests/test_api.py).

Kinds: "call" returns JSON; "job" queues work and returns {"job": id} (follow it with jobs.get / jobs.wait or the event stream);
"binary" returns {"content_type", "base64", "filename"?}; a method with a "data" parameter of type bytes takes it as base64."""
import base64

from .schema import describe, validate


class Method:
    def __init__(self, name, route, schema, attr, kind="call", doc="", body=None):
        self.name, self.route, self.schema, self.attr, self.kind, self.doc, self.body = name, route, schema, attr, kind, doc, body

    def info(self):
        return {"name": self.name, "kind": self.kind, "doc": self.doc, "params": describe(self.schema),
                "http": "%s %s" % self.route if self.route else None}


def _q(params):
    """Parameters as the string map the engine's handlers read (the query string of the first server)."""
    out = {}
    for k, v in params.items():
        if isinstance(v, bool):
            out[k] = "1" if v else "0"
        elif isinstance(v, list):
            out[k] = ",".join(str(x) for x in v)
        elif isinstance(v, (str, int, float)):
            out[k] = str(v)
    return out


def call(engine, method, params):
    """Validate and run one method. Returns the JSON-able result. Every project change the method makes is held and raised as ONE `render.invalidate` event per project
    when the call ends (skin_editor/changes.py)."""
    from .. import changes
    with changes.batch():
        return _call(engine, method, params)


def _call(engine, method, params):
    p = validate(method.schema, params)
    if method.attr is None:
        return NATIVE[method.name](engine, p)
    fn = getattr(engine, method.attr)
    if method.body == "data":
        res = fn(_q({k: v for k, v in p.items() if k != "data"}), bytes(p["data"]))
    elif method.body:
        res = fn(_q({k: v for k, v in p.items() if k != method.body}), p[method.body])
    else:
        res = fn(_q(p), p)
    if method.kind == "job":
        return {"job": res["id"], "label": res["label"]}
    if method.kind == "binary":
        out = {"content_type": res[1], "base64": base64.b64encode(res[0]).decode("ascii")}
        if len(res) == 3:
            out["filename"] = res[2]
        return out
    return res


def _jobs_wait(engine, p):
    return engine.jobs.wait(p["id"], p.get("timeout", 600)).view()


NATIVE = {
    "api.methods": lambda e, p: [m.info() for m in methods().values()],
    "jobs.list": lambda e, p: e.jobs.list(),
    "jobs.get": lambda e, p: e.jobs.get(p["id"]).view(),
    "jobs.wait": _jobs_wait,
    "jobs.cancel": lambda e, p: {"cancelled": e.jobs.cancel(p["id"])},
    "jobs.latest": lambda e, p: e.job,
}

G, P = "GET", "POST"
PROJ = {"project": "str", "bundle": "str", "path_id": "id"}
_TABLE = [
    # name, route, schema, engine attribute, kind, doc, body
    ("api.methods", None, {}, None, "call", "This table: every method with its parameters."),
    ("jobs.list", None, {}, None, "call", "All known jobs, oldest first."),
    ("jobs.get", None, {"id": "str"}, None, "call", "One job: state, progress, result or error."),
    ("jobs.wait", None, {"id": "str", "timeout": "num?"}, None, "call", "Block until the job finishes (or the timeout, seconds), then return it."),
    ("jobs.cancel", None, {"id": "str"}, None, "call", "Cancel a job that has not started."),
    ("jobs.latest", (G, "/api/job"), {}, None, "call", "The most recent job in the first frontend's shape."),

    ("app.state", (G, "/api/state"), {}, "state", "call", "Install, snapshot, index, tamper and project state."),
    ("app.quit", (P, "/api/quit"), {}, "quit", "call", "Stop the server."),
    ("game.detect", (P, "/api/detect"), {}, "do_detect", "call", "Search the store libraries for FM installs."),
    ("game.select", (P, "/api/config"), {"game_dir": "str"}, "set_game", "call", "Use this game folder."),
    ("snapshot.take", (P, "/api/snapshot"), {"force": "bool?"}, "snapshot", "call", "Copy the stock style bundles (game closed, stock files)."),
    ("snapshot.record_reference", (P, "/api/reference-hashes"), {"force": "bool?"}, "reference_hashes", "call", "Record catalog and UI bundle hashes for an older snapshot."),
    ("index.build", (P, "/api/index"), {}, "do_index", "job", "Decode the snapshot's stylesheets into the style index."),

    ("tokens.list", (G, "/api/tokens"), {"q": "str?", "colours": "bool?"}, "tokens", "call", "Tokens by name, value or hex code."),
    ("tokens.get", (G, "/api/token"), {"name": "str"}, "token", "call", "One token: definitions per sheet, alias chain, reach."),
    ("literals.list", (G, "/api/literals"), {}, "literals", "call", "Colour literals with hit counts."),
    ("literals.get", (G, "/api/literal"), {"rgb": "str", "a": "num"}, "literal", "call", "Rules using one RGBA, and every alpha of its RGB."),

    ("project.list", (G, "/api/projects"), {}, "projects", "call", "Project names."),
    ("project.get", (G, "/api/project"), {"name": "str"}, "get_project", "call", "Load a project (a new one when it does not exist)."),
    ("project.save", (P, "/api/project"), {"project": "obj"}, "save_project", "call", "Validate and store a project.", "project"),
    ("project.files", None, {"project": "str"}, "pf_tree", "call", "Files of a folder project (path, kind, bytes); empty for a legacy project."),
    ("project.read_file", None, {"project": "str", "path": "str"}, "pf_read", "call", "One text file of a folder project."),
    ("project.write_file", None, {"project": "str", "path": "str", "text": "str"}, "pf_write", "call", "Store a text file exactly as given; returns the project's problems."),
    ("project.delete_file", None, {"project": "str", "path": "str"}, "pf_delete", "call", "Delete a file of a folder project (not the core files)."),
    ("project.problems", None, {"project": "str"}, "pf_problems", "call", "Compile a folder project and list problems (file, line, message)."),
    ("uss.diagnostics", None, {"text": "str", "sheet": "str?"}, "uss_diagnostics", "call", "Diagnostics of USS text: syntax, unknown property or token, bad colour, unit, unused class (with quick-fix suggestions)."),
    ("game.sheets", None, {}, "game_sheets", "call", "The game's stylesheets (name, bundle, rule count)."),
    ("game.sheet", None, {"name": "str", "bundle": "str?"}, "game_sheet", "call", "One vanilla sheet printed as USS."),
    ("build.plan", None, {"project": "str", "target": ("opt", ("enum", ["native", "bundles"]))}, "build_plan", "call", "What a build would do and drop for a target, without writing anything."),
    ("project.import_native", None, {"path": "str", "name": "str"}, "pf_import_native", "call", "A native USS skin folder (skin.json + sheets + assets) as a project; the source is only read."),
    ("docs.checklist", None, {}, "docs_checklist", "call", "The in-game checklist (docs/INGAME-CHECKLIST.md) and its results block."),
    ("builds.list", None, {"project": "str?", "limit": "int?"}, "builds_list", "call", "Prepared packages: every build with a package.json (project, id, gate result, files with hashes, plan digest); `latest` marks what Install build would install."),
    ("layout.export_index", None, {"index": "str?", "game_build": "str?", "areas": "str?"}, "layout_export", "call", "Build the fmlayout-index/2 dump from the FM27_LayoutMCP sqlite index plus the game's composition bundles (cross-checked cell by cell against the bundles) and import it."),
    ("render.layouts", None, {"q": "str?", "limit": "int?"}, "render_layouts", "call", "The game's layouts (VisualTreeAssets) for the render browser: name, bundle, path id, element count, filtered by name; `total` is the number that match."),
    ("render.layout", None, {"bundle": "str?", "path_id": "id?", "name": "str?", "depth": "int?", "project": "str?", "skin": "bool?", "max_nodes": "int?", "open": ("opt", ("list", "str"))}, "render_layout", "call", "Offline render of one layout (an approximation, never the game's renderer): its element tree with template includes resolved by GUID, the matched rules per element in cascade order and the computed declarations, each flagged mapped, partial, unmapped or unknown; plus the sheet order, the named gaps and timings. Large layouts are cut to `max_nodes` nodes (default 1000, 0 = all): a collapsed node carries `collapsed`, its path in `open` expands it, and `truncated` says what was cut."),
        ("render.rule", None, {"sheet": "str", "rule": "int", "project": "str?", "skin": "bool?"}, "render_rule", "call", "One rule of the render's cascade as USS text and where it lives: a game rule is read-only, a project rule gives its file and line."),
    ("render.table", None, {"path_id": "id", "project": "str?", "skin": "bool?", "breakpoint": "int?"}, "render_table", "call", "A table view as a labelled placeholder table: its header row is the column order; with project (and skin not false) the project's column edits are applied."),
    ("render.screen", None, {"composition": "str", "width": "num", "height": "num", "reserved_right": "int?", "padding": "int?", "project": "str?", "skin": "bool?"}, "render_screen", "call", "A composition's cells placed on a grid container of width x height px, with measured pitch, tile layouts and flags; with project (and skin not false) the project's tile moves apply."),
    ("tables.list", None, {"q": "str?", "limit": "int?"}, "tables_list", "call", "The game's table views (ui-tableviews): name, path id, column count."),
    ("tables.view", None, {"path_id": "id", "project": "str?"}, "tables_view", "call", "One table view: its columns in order with width and flags, what each column's row cell draws (factory, default width, cell layout), the columns the factory could add; with a project, its patch file."),
    ("tables.usage", None, {"index": "str?"}, "tables_usage", "call", "Where table views are used: decode the view GUIDs from the layouts' InitFunction arguments in the FM27_LayoutMCP index (read-only) and store the map in the workspace; `tables.view` then returns `used_by` (layout, tile, compositions) and `used_by_summary`."),
    ("tables.edit", None, {"project": "str", "name": "str", "path_id": "id", "op": "obj"}, "tables_edit", "call", "Add a column edit (set-width, hide-column, show-column, move-column) to the project's patch file of a table view. Bundle target only."),
    ("tables.unedit", None, {"project": "str", "name": "str"}, "tables_unedit", "call", "Remove the patch file of a table view from the project."),
    ("layouts.list", None, {"q": "str?", "bundle": "str?", "limit": "int?"}, "layouts_list", "call", "The game's UXML layouts (VisualTreeAssets): bundle, name, path id, element count; filtered by name."),
    ("layouts.tree", None, {"bundle": "str", "path_id": "id", "project": "str?"}, "layouts_tree", "call", "One layout as an element tree (type, name, classes, attributes, inline style, bindings read-only), templates resolved one level; with a project, its patch file for that layout."),
    ("layouts.class_usage", None, {"class": "str"}, "layouts_class_usage", "call", "Where a USS class is used: layouts with elements carrying it, and the style rules that mention it."),
    ("layouts.edit", None, {"project": "str", "bundle": "str", "name": "str", "path_id": "id", "op": "obj"}, "layouts_edit", "call", "Add an edit (set-classes, set-inline, set-attr; addressed by element id plus a type/name guard) to the project's patch file of a layout. Bundle target only."),
    ("layouts.unedit", None, {"project": "str", "bundle": "str", "name": "str", "id": "int", "op": "str?"}, "layouts_unedit", "call", "Remove the edits of one element (or one op kind) from a layout's patch file."),
    ("font.tokens", None, {}, "font_tokens", "call", "The game's font-family tokens, the targets of a font swap."),
    ("font.set", None, {"project": "str", "token": "str", "path": "str"}, "font_set", "call", "Assign a .ttf/.otf file to a font token (native target: the export copies the font and writes the url() rule)."),
    ("font.remove", None, {"project": "str", "token": "str"}, "font_remove", "call", "Remove a font assignment."),
    ("inspector.status", None, {}, "inspector_status", "call", "Is the FM27 inspector pipe answering? {online, game, scene} or {online: false, reason}."),
    ("preview.live", None, {"project": "str"}, "preview_live", "call", "Live preview: write the project as a native skin skins/<name>-preview, ask the game to reload skins, screenshot it through the inspector. mode static + reason when the pipe is unavailable. Never touches bundles."),
    ("preview.live_image", None, {"path": "str"}, "preview_live_image", "binary", "A screenshot taken by preview.live."),
    ("update.status", None, {}, "update_status", "call", "Live game against the active version profile: same, catalog_changed (guided flow), tamper (bundle installs blocked) or no profile; plus the stored profiles."),
    ("update.profiles", None, {}, "update_profiles", "call", "Stored version profiles (id, build, catalog hash, counts)."),
    ("update.scan", None, {"build": "str?"}, "update_scan", "call", "Scan the vanilla snapshot into a version profile (tokens, sheets, rules, icon classes, hashes) stored under profiles/."),
    ("update.import_profile", None, {"path": "str", "build": "str?", "catalog_hash": "str?", "note": "str?"}, "update_import_profile", "call", "Scan a folder of stock style bundles of another game build (read-only) into a profile for diffing."),
    ("update.diff", None, {"old": "str", "new": "str", "project": "str?"}, "update_diff", "call", "Diff two profiles: tokens added/removed/changed/renamed, rules whose selector vanished or moved, sheets, icons, layouts; with a project, a state for each of its items (ok, target moved, target gone, vanilla value changed)."),
    ("update.autofix", None, {"project": "str", "old": "str", "new": "str"}, "update_autofix", "call", "Apply the auto-fixable (target moved) items to a project: token renames, rules moved to the sheet that now holds the game's rule, repointed images."),
    ("project.new_sheet", None, {"project": "str", "sheet": "str"}, "pf_new_sheet", "call", "Add an empty rule sheet styles/<sheet>.uss for a game stylesheet to a folder project."),
    ("project.delete", None, {"project": "str"}, "pf_remove", "call", "Remove a project from the list: the folder is moved to <workspace>/trash, not erased."),
    ("project.search", None, {"project": "str", "q": "str", "regex": "bool?", "case": "bool?"}, "pf_search", "call", "Find text in a folder project's text files."),
    ("project.create_folder", None, {"name": "str", "target": ("opt", ("enum", ["native", "bundles"])), "preset": "str?", "keep_club_colours": "bool?"}, "pf_create", "call",
     "New folder project: empty, or from a preset (written as a folder project with the chosen output from the start). keep_club_colours false turns the club-colour removal on."),
    ("native.preflight", None, {"project": "str"}, "native_preflight", "call", "What 'Put it in the game' would do, without doing it: the skin's name, what it carries (empty = nothing changed yet), the skins folder, first time or not."),
    ("native.put", None, {"project": "str"}, "native_put", "job", "Put the project in the game as a native skin (job; progress messages are plain words). Refuses a project that changes nothing."),
    ("native.remove", None, {"project": "str", "confirm": "bool?"}, "native_remove", "call", "Take a skin this editor wrote out of the skins folder (only a folder with the editor's marker; confirm must be true)."),
    ("theme.generate", None, {"background": "str", "accent": "str", "text": "str", "mode": ("opt", ("enum", ["dark", "light"]))}, "theme_generate", "call", "A theme from three colours, not written: what it writes and keeps, and the contrast check."),
    ("theme.create", None, {"name": "str", "background": "str", "accent": "str", "text": "str", "mode": ("opt", ("enum", ["dark", "light"])), "keep_club_colours": "bool?"}, "theme_create", "call", "Write a generated theme as a native folder project; refused when it fails the contrast check."),
    ("theme.gallery", None, {}, "theme_gallery", "call", "The gallery themes (inputs only, made by the same generator) with their contrast results."),
    ("simple.token_screens", None, {"token": "str"}, "simple_token_screens", "call", "On how many of the measured screens the shipped models hold an area this token paints: {screens, of, names}. Counts only."),
    ("simple.literal_info", None, {"rgb": "str", "a": "num?"}, "simple_literal_info", "call", "What a literal colour swap copies into a native skin: {uses, selectors, copied_rules, limit, offered}."),
    ("tokens.browse", None, {"used_only": "bool?"}, "browse_colours", "call", "Every colour token the game's rules use (all with used_only false): name, colour, number of rule paths it paints."),
    ("app.explain", None, {"message": "str"}, "explain", "call", "An engine message in plain words: {plain, details}."),
    ("project.migrate", None, {"project": "str"}, "pf_migrate", "call", "Convert a legacy <name>.skin.json into a project folder (verified round trip; the old file is kept as .migrated)."),
    ("project.create", (P, "/api/preset"), {"name": "str", "preset": "str?"}, "preset", "call", "New project, blank or from a preset."),

    ("build.bundles", (P, "/api/build"), {"name": "str"}, "build", "job", "Patch fresh copies of the snapshot; gate; write packages."),
    ("build.reach", (P, "/api/reach"), {"name": "str"}, "reach", "job", "Check scoped-rule selectors against the game layouts."),
    ("install.bundles", (P, "/api/install"), {"name": "str", "force": "bool?"}, "do_install", "call", "Install the latest build with backup and verification."),
    ("backup.list", (G, "/api/backups"), {}, "backups", "call", "Backup sets."),
    ("backup.restore", (P, "/api/restore"), {"backup": "str"}, "restore", "call", "Restore a backup set, or 'vanilla'."),
    ("native.info", (G, "/api/native/info"), {}, "native_info", "call", "The user skins folder, installed skins, wallpaper places."),
    ("native.export", (P, "/api/native/export"), {"project": "str", "id": "str?", "display": "str?", "dest": "str?"}, "native_export", "call", "Write the project as a native skin folder."),
    ("launcher.create", (P, "/api/launcher"), {"confirm": "bool?", "target_dir": "str?"}, "make_launcher", "call", "Plan or create the macOS launcher."),
    ("shell.open_folder", (P, "/api/open-folder"), {"path": "str"}, "open_folder", "call", "Open an export or skin folder in the file manager."),

    ("layout.state", (G, "/api/layout/state"), {}, "layout_state", "call", "The imported layout dump and its staleness."),
    ("layout.import", (P, "/api/layout/import"), {"data": "bytes", "name": "str?"}, "layout_import", "call", "Import a layout dump (fmlayout-index/2).", "data"),
    ("layout.screens", (G, "/api/layout/screens"), {"area": "str?", "q": "str?"}, "view_screens", "call", "Screens (panels) with areas."),
    ("layout.screen", (G, "/api/layout/screen"), {"panel": "str"}, "view_screen", "call", "One screen: layouts, compositions, cells."),
    ("layout.outline", (G, "/api/layout/outline"), {"layout": "int", "anc": ("opt", ("list", "int")), "q": "str?"}, "view_outline", "call", "Element outline of one layout."),
    ("where.token", (G, "/api/where/token"), {"name": "str"}, "where_token", "call", "Screens and areas a token paints."),
    ("where.literal", (G, "/api/where/literal"), {"rgb": "str", "a": "num"}, "where_literal", "call", "Screens and areas a literal paints."),
    ("where.search", (G, "/api/where/search"), {"q": "str?"}, "where_search", "call", "Where a class or selector is used."),
    ("placement.list", (G, "/api/placement/list"), {"project": "str"}, "placement_list", "call", "Stored placement edits."),
    ("placement.check", (P, "/api/placement/check"), {"project": "str", "edit": "obj"}, "placement_check", "call", "Validate one placement edit."),
    ("placement.add", (P, "/api/placement/add"), {"project": "str", "edit": "obj", "confirm": "bool?"}, "placement_add", "call", "Store a placement edit."),
    ("placement.remove", (P, "/api/placement/remove"), {"project": "str", "id": "str"}, "placement_remove", "call", "Remove a stored placement edit."),

    ("preview.model_names", (G, "/api/models"), {}, "models", "call", "Names of the measured screens."),
    ("preview.models", (G, "/api/preview/models"), {}, "preview_models", "call", "Measured screens with region counts."),
    ("preview.evaluate", (G, "/api/preview/model"), {"name": "str", "project": "str?"}, "preview_model", "call", "A screen's regions with vanilla and skin colours."),
    ("preview.image", (G, "/api/preview/image"), {"name": "str"}, "preview_image", "binary", "A measured screen's screenshot."),
    ("preview.suggest", (G, "/api/preview/suggest"), {"name": "str", "rgb": "str"}, "preview_suggest", "call", "Nearest tokens painting a screen."),
    ("verify.screenshot", (P, "/api/verify"), {"model": "str", "project": "str?", "data": "bytes"}, "do_verify", "call", "Compare an in-game screenshot with the expected colours.", "data"),

    ("images.catalog", (G, "/api/images/catalog"), {"refresh": "bool?"}, "images_catalog", "call", "Every texture, icon and SVG in the UI bundles."),
    ("images.thumb", (G, "/api/images/thumb"), {"bundle": "str", "path_id": "id"}, "images_thumb", "binary", "Thumbnail of one image."),
    ("images.source", (G, "/api/images/source"), {"project": "str", "file": "str"}, "images_source", "binary", "A project's stored replacement."),
    ("images.swap", (P, "/api/images/swap"), dict(PROJ, kind=("enum", ["texture", "svg", "icon"]), name="str?", fit=("opt", ("enum", ["cover", "contain", "stretch"])), data="bytes"), "images_swap", "call", "Store a replacement image for one slot.", "data"),
    ("images.swap_file", None, dict(PROJ, kind=("enum", ["texture", "svg", "icon"]), name="str?", fit=("opt", ("enum", ["cover", "contain", "stretch"])), path="str"), "images_swap_file", "call", "Like images.swap, reading the replacement from a local file path."),
    ("images.commit", None, dict(PROJ, kind=("enum", ["texture", "svg", "icon"]), name="str?", fit=("opt", ("enum", ["cover", "contain", "stretch"])), where=("opt", ("list", "str")), path="str?"), "images_commit", "call", "Commit the staged edit of one slot in a single write: replacement file (path; omit to keep the stored one), fit and where. Returns the project."),
    ("images.preview_file", None, {"path": "str"}, "images_preview_file", "binary", "A local image file as a PNG preview (for a staged, not yet stored replacement)."),
    ("images.fit", None, dict(PROJ, fit=("enum", ["cover", "contain", "stretch"])), "images_fit", "call", "Change how a stored replacement is fitted."),
    ("assets.conflicts", None, {"project": "str", "target": ("opt", ("enum", ["native", "bundles"]))}, "assets_conflicts", "call", "Conflict report of a project's image swaps: missing files, aspect and size problems, slots the game no longer has, wallpapers on the same place, icons a native skin cannot place."),
    ("images.remove", (P, "/api/images/remove"), dict(PROJ), "images_remove", "call", "Remove a swap."),
    ("images.where", (P, "/api/images/where"), dict(PROJ, where=("list", "str")), "images_where", "call", "Native skins: where a wallpaper swap is shown."),
    ("images.export", (G, "/api/images/export"), {"bundle": "str", "path_id": "id"}, "images_export", "binary", "One original at true size (PNG or zip)."),
    ("images.export_all", (P, "/api/images/export-all"), {"group": "str?", "kind": "str?", "q": "str?", "big": "bool?"}, "images_export_all", "job", "Export every image matching a filter."),

    ("compare.load", (P, "/api/compare/load"), {"path": "str"}, "compare_load", "call", "Load another skin (USS folder or bundles) for comparison."),
    ("compare.state", (G, "/api/compare/state"), {}, "compare_state", "call", "The loaded comparison."),
    ("compare.asset", (G, "/api/compare/asset"), {"file": "str"}, "compare_asset", "binary", "An image of the loaded USS skin."),
    ("compare.thumb", (G, "/api/compare/thumb"), {"side": ("enum", ["vanilla", "theirs"]), "bundle": "str", "path_id": "id"}, "compare_thumb", "binary", "Thumbnail of a differing image."),
    ("compare.import", (P, "/api/compare/import"), {"name": "str"}, "compare_import", "call", "New project from the comparison's colours."),
]
def _build():
    return {row[0]: Method(row[0], row[1], dict(row[2]), row[3], row[4], row[5], row[6] if len(row) > 6 else None) for row in _TABLE}


METHODS = None


def methods():
    global METHODS
    if METHODS is None:
        METHODS = _build()
    return METHODS
