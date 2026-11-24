"""Project option "club colours: remove". The game paints club (and nation / competition) colours in code: gradients bound to
the club's colours (useCustomStyles false, so colour rules lose), the club wallpaper, entity textures, and the top-left kit strip.
These rules are the ones proven in game for flat neutral-bar themes (the same
rules the crimson preset carries): a code-bound gradient is never recoloured, it stops drawing (opacity 0, or visibility hidden
when it is the parent of real content, whose children are set visible again), and the flat bar behind it takes one neutral colour.

`rules(colour)` returns the scoped rules (for AlwaysAppliedStyleSheet) with every surface set to `colour`.
Not covered: header-sweep rules for extra club-bound headers, and headers kept club-coloured (staff profile, club / continent site headers)."""
from . import colour as colour_mod

SHEET = "AlwaysAppliedStyleSheet"
# the game adds nav-on-light / nav-on-dark to the nav bars by the club colour's brightness; their 74 rules (TransferDeadlineDay and
# others) set dark text and icon tints for light club colours. Renamed to dead classes the bar text stays the default light text on
# the flat bar, identical for every club (Crimson skin, token-map.md).
RENAMES = {"nav-on-light": "skin-off-navlight0", "nav-on-dark": "skin-off-navdark0"}
TRANSPARENT = {"rgb": "#000000", "a": 0.0}

GWB = "#panel_root.align-items-stretch.justify-content-space-between"
CF_BOUND = ["#SpeakToVariables SIImage#Card-frame",
            "#SpeakToSideRemapper SIImage#Card-frame",
            "#ElementBindingRoot > ComponentElement > BaseCardTemplateImpl#CardController > ComponentElement"
            " > #layout-tool-default-default > #layout-tool-default-default > SIImage#Card-frame"]
CF_PARENTS = ["#SpeakToVariables.height-100-percent > SIStyleSetter.flex-grow-class > VisualElement.flex-grow-class > #BindingVariables.flex-grow-class",
              "#SpeakToVariables #layout-report-default-default--unpacked > #layout-report-default-default",
              "#card-variables > #layout-report-default-default > #layout-report-default-default",
              "#SpeakToVariables #layout-tool-default-default > #layout-tool-default-default",
              "#SpeakToSideRemapper #layout-tool-default-default",
              "#ElementBindingRoot > ComponentElement > BaseCardTemplateImpl#CardController > ComponentElement"
              " > #layout-tool-default-default > #layout-tool-default-default"]
NEWS = ["BindingExpect#BindingExpect.flex-grow-class > SIImage.flex-grow-class",
        "BindingExpect#BindingExpect.flex-grow-class > BindingRemapper.flex-grow-class > SIImage.flex-grow-class"]

# preview: elements the game paints with club colours (label = Type#name.classes as the inspector reports it)
PREVIEW_NAMES = ("Club", "ClubSIGradient_LeftToRight", "ClubGradientTdd", "EntityTextureClub", "DynamicBackgroundImage_Club",
                 "PlayerReportHeaderGradient", "PlayerGradient", "HomeColour", "AwayColour")
PREVIEW_CLASSES = ("clubcolours-border", "navigation-core-clubname-kit")      # fm-club-primary-color alone (e.g. pitch shirt numbers) is not covered by the rules


def rules(col):
    """Scoped rules (project format) that remove the club colours. col: canonical colour object for the flat surfaces."""
    colour_mod.from_obj(col)
    c, t = dict(col), dict(TRANSPARENT)
    why = "club colours removed (project option); proven in the Crimson skin"
    out = []

    def rule(sel, props, note=""):
        out.append({"sheet": SHEET, "selector": sel, "props": props, "why": why + (": " + note if note else "")})

    # navigation bars: the club gradient / texture stops drawing, the bar is flat
    rule(".navigation-header-gradient", {"background-color": c})
    rule(".navigation-header-gradient SIGradient, .navigation-header-gradient SIImage", {"opacity": "0"})
    rule("#EntityGradient", {"background-color": c})
    rule("#EntityGradient SIGradient, #EntityGradient SIImage, #EntityGradient #ClubGradientTdd", {"opacity": "0"})
    # profile / entity headers: colour where custom props win, otherwise hide the gradient and keep its content
    rule("SIGradient#PlayerGradient, SIGradient#Club", {"--start-colour": c, "--end-colour": c}, "colour, not opacity: the header holds photo + name")
    rule("#PlayerReportHeaderRemapper.entity-background-header", {"background-color": c})
    rule("SIGradient#PlayerReportHeaderGradient", {"visibility": "hidden"}, "bound in code: custom props lose")
    rule("SIGradient#PlayerReportHeaderGradient > #PlayerReportHeaderSetter", {"visibility": "visible"})
    rule("#EntityTextureClub, #EntityTextureNation, #GradientsAdditional SIGradient, #DynamicBackgroundImage_Club", {"opacity": "0"})
    rule("#ClubSIGradient_LeftToRight", {"--start-colour": c, "--end-colour": c})
    # club wallpaper (GameWorldBackground) and the report / tool frames bound to it
    rule(GWB, {"background-color": c}, "GameWorldBackground root")
    rule(f"{GWB} > BindableSwitchElement > #background_image, {GWB} > BindableSwitchElement > SIRenderTextureImage, {GWB} SIGradient",
         {"opacity": "0"}, "club wallpaper: 2D image + 3D render texture")
    rule(", ".join(CF_BOUND), {"visibility": "hidden"}, "club wallpaper in the 10 bound card frames")
    rule(", ".join(s + " > *" for s in CF_BOUND), {"visibility": "visible"})
    rule(", ".join(CF_PARENTS), {"background-color": c}, "opaque page behind the hidden frame")
    # news header bands (club / competition / nation colour bound in code)
    rule(", ".join(f"{n}, {n} > SIGradient.flex-grow-class" for n in NEWS), {"visibility": "hidden"})
    rule(", ".join(f"{n} > SIGradient.flex-grow-class > *" for n in NEWS), {"visibility": "visible", "background-color": c})
    # top-left kit strip (club primary / secondary colour) and its outline
    rule("#ClubColoursStyleSetter.navigation-core-clubname-kit, #NationColoursStyleSetter.navigation-core-clubname-kit", {"background-color": c})
    rule(".navigation-core-clubname-kit Image", {"opacity": "0"})
    rule(".clubcolours-border", {"border-color": t})
    return out


def is_club_region(region):
    """Preview: does the game paint this measured region with club colours?"""
    label = region.get("label", "")
    name = label.split("#", 1)[1].split(".", 1)[0] if "#" in label else ""
    return name in PREVIEW_NAMES or any(c in PREVIEW_CLASSES for c in region.get("classes") or [])
