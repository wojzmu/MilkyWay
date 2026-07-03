import { useEffect, useMemo, useRef } from "react";
import Plotly from "plotly.js-dist-min";
import type { Star } from "../types";
import { categoryColor, type ColorMode } from "../categories";

interface Props {
  stars: Star[];
  selected: Star | null;
  onSelect: (star: Star | null) => void;
  colorMode: ColorMode;
}

/**
 * Hertzsprung-Russell diagram: BP-RP colour (x) vs absolute G magnitude (y,
 * inverted so brighter stars are up). Each marker keeps the star's true RGB
 * colour. Built directly on plotly.js-dist-min to sidestep React-wrapper
 * peer-dependency issues.
 */
export default function HRDiagram({
  stars,
  selected,
  onSelect,
  colorMode,
}: Props) {
  const ref = useRef<HTMLDivElement>(null);

  const plottable = useMemo(
    () => stars.filter((s) => s.bpRp !== null && s.absG !== null),
    [stars],
  );

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const starTrace: Partial<Plotly.PlotData> = {
      x: plottable.map((s) => s.bpRp as number),
      y: plottable.map((s) => s.absG as number),
      customdata: plottable.map((_, i) => i),
      text: plottable.map(
        (s) => s.properName ?? s.simbadMainId ?? s.starId,
      ),
      hovertemplate:
        "%{text}<br>BP-RP: %{x:.2f}<br>M_G: %{y:.2f}<extra></extra>",
      mode: "markers",
      type: "scattergl",
      marker: {
        size: 5,
        color: plottable.map((s) =>
          colorMode === "category" ? categoryColor(s.starClass) : s.rgbHex,
        ),
        line: { width: 0 },
      },
    };

    // Trace index 1: fixed overlay for the current selection, updated via
    // restyle in the effect below. Starts empty.
    const selectionTrace: Partial<Plotly.PlotData> = {
      x: [],
      y: [],
      mode: "markers",
      type: "scattergl",
      hoverinfo: "skip",
      marker: {
        size: 14,
        color: "rgba(0,0,0,0)",
        line: { color: "#7fd4ff", width: 2 },
      },
    };

    const layout: Partial<Plotly.Layout> = {
      paper_bgcolor: "#03040a",
      plot_bgcolor: "#0b1026",
      font: { color: "#c8d2e8" },
      margin: { l: 60, r: 20, t: 40, b: 50 },
      title: { text: "Hertzsprung–Russell Diagram" },
      xaxis: {
        title: { text: "Colour  BP − RP  (mag)" },
        gridcolor: "#1c2440",
        zeroline: false,
      },
      yaxis: {
        title: { text: "Absolute magnitude  M_G" },
        autorange: "reversed", // brighter (smaller mag) at top
        gridcolor: "#1c2440",
        zeroline: false,
      },
      showlegend: false,
    };

    Plotly.react(el, [starTrace, selectionTrace], layout, {
      responsive: true,
      displaylogo: false,
    });

    const handler = (e: Plotly.PlotMouseEvent) => {
      const pt = e.points?.[0];
      if (pt && typeof pt.customdata === "number") {
        onSelect(plottable[pt.customdata]);
      }
    };
    // @ts-expect-error plotly's element gains an `on` method at runtime
    el.on("plotly_click", handler);

    return () => {
      Plotly.purge(el);
    };
  }, [plottable, onSelect, colorMode]);

  // Update the fixed overlay trace (index 1) for the current selection.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const show =
      selected && selected.bpRp !== null && selected.absG !== null;
    Plotly.restyle(
      el,
      {
        x: [show ? [selected!.bpRp as number] : []],
        y: [show ? [selected!.absG as number] : []],
      },
      [1],
    ).catch(() => {});
  }, [selected]);

  return (
    <div className="hr-diagram-wrap">
      <div ref={ref} className="hr-diagram" />
    </div>
  );
}
