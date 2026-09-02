import { useRef, type KeyboardEvent } from "react";

import type { ModelingTrack } from "../model/processing-registry";

interface ModelingTrackMenuProps {
  value: ModelingTrack;
  onChange: (track: ModelingTrack) => void;
  onOpenValidation: () => void;
}

const TRACKS: Array<{ value: ModelingTrack; label: string }> = [
  { value: "metal", label: "Metal · elastoplastic" },
  { value: "polymer", label: "Polymer · viscoelastic" },
  { value: "elastomer", label: "Elastomer · hyper-viscoelastic" },
];

export function ModelingTrackMenu({ value, onChange, onOpenValidation }: ModelingTrackMenuProps) {
  const detailsRef = useRef<HTMLDetailsElement>(null);
  const summaryRef = useRef<HTMLElement>(null);
  const close = () => {
    if (detailsRef.current) detailsRef.current.open = false;
  };
  const choose = (track: ModelingTrack) => {
    onChange(track);
    close();
    summaryRef.current?.focus();
  };
  const openValidation = () => {
    onOpenValidation();
    close();
    summaryRef.current?.focus();
  };
  const moveMenuFocus = (event: KeyboardEvent<HTMLDivElement>) => {
    const menuItems = Array.from(event.currentTarget.querySelectorAll<HTMLElement>("[role^='menuitem']"));
    const current = menuItems.indexOf(document.activeElement as HTMLElement);
    let next = current;
    if (event.key === "ArrowDown") next = current < menuItems.length - 1 ? current + 1 : 0;
    else if (event.key === "ArrowUp") next = current > 0 ? current - 1 : menuItems.length - 1;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = menuItems.length - 1;
    else if (event.key === "Escape") {
      event.preventDefault();
      close();
      summaryRef.current?.focus();
      return;
    } else return;
    event.preventDefault();
    menuItems[next]?.focus();
  };

  return (
    <details ref={detailsRef} className="modeling-track-menu">
      <summary ref={summaryRef} className="button secondary">Change model family</summary>
      <div role="menu" aria-label="Modeling options" onKeyDown={moveMenuFocus}>
        <div role="group" aria-label="Material model family">
          {TRACKS.map((track) => (
            <button
              key={track.value}
              type="button"
              role="menuitemradio"
              aria-checked={value === track.value}
              onClick={() => choose(track.value)}
            >
              {track.label}
            </button>
          ))}
        </div>
        <button className="modeling-track-review-action" type="button" role="menuitem" onClick={openValidation}>
          Validation &amp; review
        </button>
      </div>
    </details>
  );
}
