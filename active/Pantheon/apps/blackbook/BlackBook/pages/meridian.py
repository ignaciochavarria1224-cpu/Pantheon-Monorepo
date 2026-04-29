"""
pages/meridian.py — Meridian belief graph and wiki themes.
vis-network is loaded in <head> by BlackBook.py.
Node clicks bridge into Reflex via data-meridian-theme attribute on chips.
"""
from __future__ import annotations

import reflex as rx

from BlackBook.state.meridian_state import MeridianState


def theme_chip(t: dict) -> rx.Component:
    return rx.el.button(
        t["theme"],
        data_meridian_theme=t["theme"],
        class_name=rx.cond(
            MeridianState.selected_theme == t["theme"],
            "bb-tag",
            "bb-btn bb-btn-ghost",
        ),
        on_click=MeridianState.select_theme(t["theme"]),
        style={"font_size": "0.5rem", "padding": "0.2rem 0.6rem", "margin": "0.15rem"},
    )


# The graph init script — vis-network already loaded in <head>
_GRAPH_SCRIPT = """
<script>
(function() {
  var _net = null;

  function buildGraph() {
    // Guard: vis must be loaded
    if (typeof vis === 'undefined') return;

    var dataEl = document.getElementById('meridian-data');
    var container = document.getElementById('meridian-graph');
    if (!dataEl || !container) return;

    var nodesRaw = dataEl.getAttribute('data-nodes') || '[]';
    var edgesRaw = dataEl.getAttribute('data-edges') || '[]';
    var nodes, edges;
    try {
      nodes = JSON.parse(nodesRaw);
      edges = JSON.parse(edgesRaw);
    } catch(e) { return; }
    if (!nodes.length) return;

    var palette = ['#E040FB','#BD34FE','#00E5FF','#00FFB3','#FF6B6B','#FFB347'];
    var nodeData = nodes.map(function(n, i) {
      return {
        id: n.id,
        label: n.label,
        color: {
          background: palette[i % palette.length],
          border: 'rgba(255,255,255,0.2)',
          highlight: { background: '#ffffff', border: '#E040FB' },
          hover:     { background: '#ffffff', border: '#00E5FF' }
        },
        font: { color: 'rgba(240,235,255,0.9)', size: 11, face: 'JetBrains Mono' },
        borderWidth: 1,
        shape: 'dot',
        size: 10 + Math.min((n.cycle || 0), 6) * 2
      };
    });
    var edgeData = edges.map(function(e) {
      return {
        from: e.from, to: e.to,
        color: { color: 'rgba(189,52,254,0.3)', highlight: '#E040FB', hover: '#00E5FF' },
        width: 1,
        smooth: { type: 'curvedCW', roundness: 0.2 },
        arrows: { to: { enabled: true, scaleFactor: 0.45 } }
      };
    });

    if (_net) { try { _net.destroy(); } catch(e) {} _net = null; }

    _net = new vis.Network(container, {
      nodes: new vis.DataSet(nodeData),
      edges: new vis.DataSet(edgeData)
    }, {
      physics: {
        enabled: true,
        barnesHut: { gravitationalConstant: -9000, springLength: 150, damping: 0.15 },
        stabilization: { iterations: 150, fit: true }
      },
      interaction: { hover: true, zoomView: true, dragView: true, tooltipDelay: 200 },
      layout: { improvedLayout: true }
    });

    // Node click → find the chip with matching data-meridian-theme and trigger it
    _net.on('selectNode', function(params) {
      if (!params.nodes.length) return;
      var nodeId = String(params.nodes[0]);
      var chip = document.querySelector('[data-meridian-theme="' + CSS.escape(nodeId) + '"]');
      if (chip) chip.click();
    });
  }

  // Watch for the data-attributes to change (Reflex state updates)
  function attachDataObserver() {
    var el = document.getElementById('meridian-data');
    if (!el) { setTimeout(attachDataObserver, 300); return; }
    new MutationObserver(buildGraph).observe(el, { attributes: true });
    buildGraph();
  }

  // Watch for the graph container to be (re)inserted into the DOM by React
  new MutationObserver(function(mutations) {
    for (var m of mutations) {
      for (var node of m.addedNodes) {
        if (!node.querySelector) continue;
        if (node.id === 'meridian-graph' || node.querySelector('#meridian-graph')) {
          setTimeout(buildGraph, 100);
        }
      }
    }
  }).observe(document.body, { childList: true, subtree: true });

  // Wait for vis to be ready (it's in <head> but may not be parsed yet)
  function waitVis() {
    if (typeof vis !== 'undefined') { attachDataObserver(); }
    else { setTimeout(waitVis, 150); }
  }
  setTimeout(waitVis, 200);
})();
</script>
"""


def meridian_page() -> rx.Component:
    return rx.fragment(
        rx.el.div(
            rx.el.h1("Meridian", class_name="bb-title"),
            rx.el.p("BELIEF GRAPH · WIKI THEMES · COGNITIVE MAP", class_name="bb-subtitle"),
            class_name="bb-page-header",
        ),

        rx.cond(MeridianState.error != "", rx.el.div(MeridianState.error, class_name="bb-error")),

        # Stats row
        rx.el.div(
            rx.el.div(
                rx.el.div("Themes Loaded", class_name="bb-stat-label"),
                rx.el.div(MeridianState.theme_count, class_name="bb-stat-value accent"),
                rx.el.div(
                    rx.cond(
                        MeridianState.theme_count == 0,
                        "No data — check meridian_brain table",
                        "nodes active",
                    ),
                    class_name="bb-stat-delta",
                ),
                class_name="bb-stat",
                style={"max_width": "220px"},
            ),
            rx.el.div(
                rx.el.div("Connections", class_name="bb-stat-label"),
                rx.el.div(MeridianState.edge_count, class_name="bb-stat-value cyan"),
                rx.el.div("wikilinks mapped", class_name="bb-stat-delta"),
                class_name="bb-stat",
                style={"max_width": "220px"},
            ),
            style={"display": "flex", "gap": "1rem", "margin_bottom": "1.5rem"},
        ),

        # Search
        rx.el.input(
            placeholder="Search themes...",
            value=MeridianState.search,
            on_change=MeridianState.set_search,
            class_name="bb-input",
            style={"max_width": "380px", "margin_bottom": "1.2rem"},
        ),

        # Two-column: graph + detail
        rx.el.div(
            # Graph canvas
            rx.el.div(
                rx.el.span("BELIEF GRAPH", class_name="bb-graph-label"),
                rx.el.div(id="meridian-graph", style={"width": "100%", "height": "500px"}),
                class_name="bb-graph-wrap",
                style={"flex": "1.5", "position": "relative"},
            ),
            # Detail panel
            rx.el.div(
                rx.cond(
                    MeridianState.selected_theme != "",
                    rx.el.div(
                        rx.el.div(MeridianState.selected_theme, class_name="bb-theme-name"),
                        rx.el.div(MeridianState.selected_body, class_name="bb-theme-body"),
                    ),
                    rx.el.div(
                        rx.el.div("⬡", style={"font_size": "2.5rem", "color": "rgba(0,229,255,0.12)", "text_align": "center", "margin_bottom": "0.8rem"}),
                        rx.el.div(
                            "Click a node or theme chip to explore its body.",
                            style={"color": "var(--t2)", "font_size": "0.72rem", "text_align": "center", "line_height": "1.7"},
                        ),
                    ),
                ),
                class_name="bb-theme-detail",
                style={"flex": "1"},
            ),
            style={"display": "flex", "gap": "1.2rem", "align_items": "flex-start"},
        ),

        # Theme chips
        rx.el.div("All Themes", class_name="bb-section"),
        rx.el.div(
            rx.foreach(MeridianState.filtered_themes, theme_chip),
            style={"display": "flex", "flex_wrap": "wrap", "gap": "0.25rem"},
        ),

        # Hidden data bridge
        rx.el.div(
            id="meridian-data",
            data_nodes=MeridianState.graph_nodes_json,
            data_edges=MeridianState.graph_edges_json,
            style={"display": "none"},
        ),

        # Graph initialization (vis-network already in <head>)
        rx.html(_GRAPH_SCRIPT),

        on_mount=MeridianState.load,
    )
