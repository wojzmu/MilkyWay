import { useEffect } from "react";

interface Props {
  onClose: () => void;
}

/** Small "Data sources" modal: a minimal credit for where the catalogue comes
 *  from. Closes on ×, backdrop click, or Esc. */
export default function AboutModal({ onClose }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label="Data sources"
        onClick={(e) => e.stopPropagation()}
      >
        <button className="modal__close" onClick={onClose} aria-label="Close">
          ×
        </button>
        <h2 className="modal__title">Data sources</h2>
        <ul className="sources">
          <li>
            <span className="sources__name">Gaia DR3</span>
            <span className="sources__org">
              ESA / Gaia DPAC —{" "}
              <a
                href="https://www.cosmos.esa.int/gaia"
                target="_blank"
                rel="noopener noreferrer"
              >
                cosmos.esa.int/gaia
              </a>
            </span>
          </li>
          <li>
            <span className="sources__name">Hipparcos</span>
            <span className="sources__org">
              ESA (1997) —{" "}
              <a
                href="https://www.cosmos.esa.int/web/hipparcos"
                target="_blank"
                rel="noopener noreferrer"
              >
                cosmos.esa.int/hipparcos
              </a>
            </span>
          </li>
          <li>
            <span className="sources__name">Star names &amp; spectral types</span>
            <span className="sources__org">
              SIMBAD, CDS Strasbourg —{" "}
              <a
                href="https://simbad.cds.unistra.fr/simbad/"
                target="_blank"
                rel="noopener noreferrer"
              >
                simbad.cds.unistra.fr
              </a>
            </span>
          </li>
        </ul>
      </div>
    </div>
  );
}
