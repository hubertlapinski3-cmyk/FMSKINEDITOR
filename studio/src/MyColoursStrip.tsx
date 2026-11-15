// My colours as one-click choices beside a colour picker (Colours view, the recolour panel of Look at it). It only offers; saving and removing are explicit elsewhere.
/** My colours as one-click choices: each swatch applies its colour where the picker it sits beside is used. Nothing here adds or removes an entry (that is explicit, in the My colours section). */
export default function Strip({ mine, onPick, label }: { mine: string[]; onPick: (rgb: string) => void; label: string }) {
  if (!mine.length) return <span className="dim small pal-strip-empty">My colours is empty: save a colour with ☆.</span>
  return <span className="pal-strip" role="group" aria-label={label}>{mine.map((c) => <button key={c} className="sw" style={{ background: c }} aria-label={`Use ${c}`} title={`Use ${c}`} onClick={() => onPick(c)} />)}</span>
}

