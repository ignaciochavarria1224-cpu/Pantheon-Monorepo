import re, ast

path = r"C:/Users/Ignac/AppData/Local/Temp/Black-Book/Black Book/app.py"
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find section bounds
start_idx = end_idx = None
for i, line in enumerate(lines):
    if '\u2500\u2500 Vault view \u2500' in line and start_idx is None:
        start_idx = i
    if 'height=580, scrolling=False)' in line:
        end_idx = i + 1

print(f"Section: lines {start_idx}-{end_idx}")
if start_idx is None or end_idx is None:
    raise SystemExit("ERROR: Section not found")

# The new vault+graph section as a plain string
new_section = (
    "            # \u2500\u2500 Vault view \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
    '            _STAGE_ORDER = ["framework", "tree", "sprout", "seed"]\n'
    '            _STAGE_LABELS = {\n'
    '                "framework": "Frameworks",\n'
    '                "tree": "Trees",\n'
    '                "sprout": "Sprouts",\n'
    '                "seed": "Seeds",\n'
    '            }\n'
    '            _STAGE_COLORS = {\n'
    '                "framework": "#FFD700",\n'
    '                "tree": "#E8A020",\n'
    '                "sprout": "#5BA85A",\n'
    '                "seed": "#4A90D9",\n'
    '            }\n'
    '\n'
    '            if not _notes and not _brain_raw:\n'
    '                st.info("No vault data yet. Run a cycle to populate.")\n'
    '            else:\n'
    '                if _notes:\n'
    '                    _filter_stage = st.selectbox(\n'
    '                        "Filter by stage",\n'
    '                        ["All"] + [_STAGE_LABELS[s] for s in _STAGE_ORDER if _stage_counts.get(s, 0) > 0],\n'
    '                        key="meridian_stage_filter"\n'
    '                    )\n'
    '                    _filter_map = {v: k for k, v in _STAGE_LABELS.items()}\n'
    '                    _filtered = [\n'
    '                        n for n in _notes\n'
    '                        if _filter_stage == "All" or n["stage"] == _filter_map.get(_filter_stage)\n'
    '                    ]\n'
    '                    for _stage in _STAGE_ORDER:\n'
    '                        _group = [n for n in _filtered if n["stage"] == _stage]\n'
    '                        if not _group:\n'
    '                            continue\n'
    '                        _color = _STAGE_COLORS[_stage]\n'
    "                        st.markdown(\n"
    "                            f'<div style=\"font-family:JetBrains Mono,monospace;font-size:0.65rem;'\n"
    "                            f'letter-spacing:0.15em;text-transform:uppercase;color:{_color};'\n"
    "                            f'margin:1.2rem 0 0.4rem\">\u2014 {_STAGE_LABELS[_stage]} ({len(_group)}) \u2014</div>',\n"
    "                            unsafe_allow_html=True\n"
    "                        )\n"
    "                        for _n in _group:\n"
    '                            _fit = f"{_n[\'fitness\']:.0f}" if _n["fitness"] else "\u2014"\n'
    '                            _doms = ", ".join(d for d in _n["domains"] if d)[:60]\n'
    '                            with st.expander(f"{_n[\'title\'][:80]}   \u00b7 fit {_fit}", expanded=False):\n'
    '                                if _doms:\n'
    '                                    st.caption(_doms)\n'
    '                                if _n["body"]:\n'
    '                                    st.markdown(_n["body"][:1500])\n'
    '\n'
    '                # \u2500\u2500 Graph view \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n'
    '                st.markdown("---")\n'
    '                st.markdown(\n'
    "                    '<div style=\"font-family:JetBrains Mono,monospace;font-size:0.62rem;'\n"
    "                    'letter-spacing:0.18em;text-transform:uppercase;color:rgba(189,52,254,0.7);'\n"
    "                    'margin-bottom:0.8rem\">\u2014 Graph View \u2014</div>',\n"
    '                    unsafe_allow_html=True\n'
    '                )\n'
    '\n'
    '                _BB_PALETTE = [\n'
    '                    "#E040FB", "#00E5FF", "#BD34FE", "#7C3AED",\n'
    '                    "#06B6D4", "#F59E0B", "#10B981", "#F472B6",\n'
    '                    "#818CF8", "#34D399",\n'
    '                ]\n'
    '\n'
    '                _g_nodes = []\n'
    '                _g_edges = []\n'
    '                _g_edge_set = set()\n'
    '                _node_info = {}\n'
    '\n'
    '                if _brain_raw:\n'
    '                    _t2id = {}\n'
    '                    for _bi, _br in enumerate(_brain_raw):\n'
    '                        _btheme = str(_col(_br, 0, "theme"))\n'
    '                        _bbody = str(_col(_br, 1, "body") or "")\n'
    "                        _ec = re.search(r'entry_count:\\s*(\\d+)', _bbody)\n"
    '                        _ec_n = int(_ec.group(1)) if _ec else 1\n'
    '                        _t2id[_btheme.lower()] = _bi\n'
    '                        _bcol = _BB_PALETTE[_bi % len(_BB_PALETTE)]\n'
    "                        _belief = re.search(r'\\*\\*Core Belief:\\*\\*\\s*([^\\n]+)', _bbody)\n"
    '                        _belief_txt = _belief.group(1)[:100] if _belief else ""\n'
    '                        _g_nodes.append({\n'
    '                            "id": _bi,\n'
    '                            "label": _btheme,\n'
    '                            "color": {\n'
    '                                "background": _bcol, "border": _bcol,\n'
    '                                "highlight": {"background": _bcol, "border": "#ffffff"},\n'
    '                                "hover": {"background": _bcol, "border": "#ffffff"},\n'
    '                            },\n'
    '                            "size": max(10, min(32, 8 + _ec_n * 3)),\n'
    '                            "title": f"<b>{_html.escape(_btheme)}</b><br>Entries: {_ec_n}" + (f"<br><br>{_html.escape(_belief_txt)}" if _belief_txt else ""),\n'
    '                            "font": {"size": 11},\n'
    '                        })\n'
    '                        _node_info[str(_bi)] = {\n'
    '                            "title": _btheme,\n'
    '                            "body": f"<b>Entries:</b> {_ec_n}" + (f"<br><br>{_html.escape(_belief_txt)}" if _belief_txt else ""),\n'
    '                        }\n'
    '                    for _bi, _br in enumerate(_brain_raw):\n'
    '                        _bbody = str(_col(_br, 1, "body") or "")\n'
    "                        for _lnk in re.findall(r'\\[\\[([^\\]|#]+?)(?:\\|[^\\]]+)?\\]\\]', _bbody):\n"
    '                            _tid2 = _t2id.get(_lnk.strip().lower())\n'
    '                            if _tid2 is not None and _tid2 != _bi:\n'
    '                                _ek = tuple(sorted([_bi, _tid2]))\n'
    '                                if _ek not in _g_edge_set:\n'
    '                                    _g_edge_set.add(_ek)\n'
    '                                    _g_edges.append({"from": _bi, "to": _tid2})\n'
    '                    _leg_rows = []\n'
    '                    for _li, _lb in enumerate(_brain_raw[:8]):\n'
    '                        _lt = str(_col(_lb, 0, "theme"))\n'
    '                        _lc = _BB_PALETTE[_li % len(_BB_PALETTE)]\n'
    '                        _leg_rows.append(f\'<div class="lr"><div class="ld" style="background:{_lc}"></div>{_html.escape(_lt[:22])}</div>\')\n'
    '                    if len(_brain_raw) > 8:\n'
    '                        _leg_rows.append(f\'<div class="lr" style="color:rgba(130,105,170,0.4)">+{len(_brain_raw)-8} more</div>\')\n'
    '                    _legend_html = "".join(_leg_rows)\n'
    '\n'
    '                elif _notes:\n'
    '                    _tid_map = {n["title"].lower(): n["id"] for n in _notes}\n'
    '                    for _n in _notes:\n'
    '                        _fit_val = _n["fitness"] or 30\n'
    '                        _nc = _STAGE_COLORS.get(_n["stage"], "#4A90D9")\n'
    '                        _g_nodes.append({\n'
    '                            "id": _n["id"],\n'
    '                            "label": _n["title"][:35],\n'
    '                            "color": {\n'
    '                                "background": _nc, "border": _nc,\n'
    '                                "highlight": {"background": _nc, "border": "#ffffff"},\n'
    '                                "hover": {"background": _nc, "border": "#ffffff"},\n'
    '                            },\n'
    '                            "size": 6 + _fit_val / 12,\n'
    "                            \"title\": f\"<b>{_html.escape(_n['title'])}</b><br>Stage: {_n['stage']}<br>Fitness: {_n['fitness'] or '?'}\",\n"
    '                            "font": {"size": 11},\n'
    '                        })\n'
    '                        _node_info[str(_n["id"])] = {\n'
    '                            "title": _n["title"],\n'
    "                            \"body\": f\"Stage: {_n['stage']}<br>Fitness: {_n['fitness'] or '?'}\",\n"
    '                        }\n'
    '                        if _n["body"]:\n'
    "                            for _lnk in re.findall(r'\\[\\[([^\\]|#]+?)(?:\\|[^\\]]+)?\\]\\]', _n[\"body\"]):\n"
    '                                _tgt = _tid_map.get(_lnk.strip().lower())\n'
    '                                if _tgt and _tgt != _n["id"]:\n'
    '                                    _ek2 = tuple(sorted([_n["id"], _tgt]))\n'
    '                                    if _ek2 not in _g_edge_set:\n'
    '                                        _g_edge_set.add(_ek2)\n'
    '                                        _g_edges.append({"from": _n["id"], "to": _tgt})\n'
    '                    _legend_html = (\n'
    '                        \'<div class="lr"><div class="ld" style="background:#FFD700"></div>Framework</div>\'\n'
    '                        \'<div class="lr"><div class="ld" style="background:#E8A020"></div>Tree</div>\'\n'
    '                        \'<div class="lr"><div class="ld" style="background:#5BA85A"></div>Sprout</div>\'\n'
    '                        \'<div class="lr"><div class="ld" style="background:#4A90D9"></div>Seed</div>\'\n'
    '                    )\n'
    '                else:\n'
    '                    _legend_html = ""\n'
    '\n'
    '                _g_nodes_json = json.dumps(_g_nodes)\n'
    '                _g_edges_json = json.dumps(_g_edges)\n'
    '                _node_info_json = json.dumps(_node_info)\n'
    '\n'
    # The graph HTML f-string — JS braces need doubling
    '                _graph_html = f"""<!DOCTYPE html>\n'
    '<html><head>\n'
    '<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>\n'
    '<style>\n'
    '*{{box-sizing:border-box;margin:0;padding:0}}\n'
    "body{{background:#03030A;overflow:hidden;font-family:'JetBrains Mono',monospace}}\n"
    '#net{{width:100%;height:680px}}\n'
    '#controls{{position:absolute;bottom:14px;right:14px;display:flex;flex-direction:column;gap:4px;z-index:10}}\n'
    '.ctrl{{background:rgba(16,8,32,0.9);border:1px solid rgba(189,52,254,0.35);color:rgba(224,64,251,0.9);width:30px;height:30px;border-radius:4px;cursor:pointer;font-size:15px;display:flex;align-items:center;justify-content:center;transition:all 0.15s ease}}\n'
    '.ctrl:hover{{background:rgba(224,64,251,0.18);border-color:rgba(224,64,251,0.7)}}\n'
    '#legend{{position:absolute;top:12px;left:12px;background:rgba(10,5,22,0.88);border:1px solid rgba(189,52,254,0.2);border-radius:5px;padding:9px 12px;z-index:10;max-height:calc(100% - 24px);overflow:auto}}\n'
    '.lr{{display:flex;align-items:center;gap:7px;font-size:9px;letter-spacing:0.12em;text-transform:uppercase;color:rgba(180,150,220,0.65);margin-bottom:4px}}\n'
    '.lr:last-child{{margin-bottom:0}}\n'
    '.ld{{width:9px;height:9px;border-radius:50%;flex-shrink:0}}\n'
    '#panel{{position:absolute;top:12px;right:12px;background:rgba(10,5,22,0.93);border:1px solid rgba(224,64,251,0.3);border-radius:6px;padding:12px 14px 10px;z-index:10;max-width:220px;display:none}}\n'
    '#pt{{font-size:12px;font-weight:700;color:#E040FB;margin-bottom:5px;letter-spacing:0.04em;line-height:1.3}}\n'
    '#pb{{font-size:10px;color:rgba(180,150,220,0.7);line-height:1.6;letter-spacing:0.03em}}\n'
    '#px{{position:absolute;top:7px;right:9px;cursor:pointer;font-size:10px;color:rgba(180,150,220,0.45)}}\n'
    '#px:hover{{color:#E040FB}}\n'
    '#hint{{position:absolute;bottom:14px;left:14px;font-size:9px;letter-spacing:0.15em;text-transform:uppercase;color:rgba(130,105,170,0.35)}}\n'
    ".vis-tooltip{{background:rgba(10,5,22,0.96)!important;border:1px solid rgba(189,52,254,0.45)!important;color:rgba(220,210,255,0.92)!important;font-family:'JetBrains Mono',monospace!important;font-size:11px!important;border-radius:4px!important;padding:8px 12px!important;line-height:1.55!important;box-shadow:0 4px 22px rgba(189,52,254,0.25)!important}}\n"
    '</style></head><body>\n'
    '<div id="net"></div>\n'
    '<div id="legend">{_legend_html}</div>\n'
    '<div id="panel"><div id="px">\u2715</div><div id="pt"></div><div id="pb"></div></div>\n'
    '<div id="controls">\n'
    '  <button class="ctrl" id="btn-fit" title="Fit all">&#x229F;</button>\n'
    '  <button class="ctrl" id="btn-zi" title="Zoom in">+</button>\n'
    '  <button class="ctrl" id="btn-zo" title="Zoom out">&minus;</button>\n'
    '  <button class="ctrl" id="btn-rst" title="Reset">&#x25CB;</button>\n'
    '</div>\n'
    '<div id="hint">click to focus &middot; double-click to zoom</div>\n'
    '<script>\n'
    'var ndata=new vis.DataSet({_g_nodes_json});\n'
    'var edata=new vis.DataSet({_g_edges_json});\n'
    'var infoMap={_node_info_json};\n'
    "var net=new vis.Network(document.getElementById('net'),{{nodes:ndata,edges:edata}},{{\n"
    "  nodes:{{shape:'dot',font:{{color:'rgba(200,185,235,0.85)',size:11,face:'JetBrains Mono,monospace',strokeWidth:0}},borderWidth:1.5,borderWidthSelected:3,shadow:{{enabled:true,color:'rgba(189,52,254,0.35)',size:12,x:0,y:0}}}},\n"
    "  edges:{{color:{{color:'rgba(189,52,254,0.28)',highlight:'rgba(224,64,251,0.9)',hover:'rgba(0,229,255,0.7)'}},width:1.5,hoverWidth:3,selectionWidth:3,smooth:{{type:'curvedCW',roundness:0.2}},arrows:{{to:{{enabled:true,scaleFactor:0.45}}}}}},\n"
    "  physics:{{stabilization:{{iterations:400,fit:true}},barnesHut:{{gravitationalConstant:-5000,centralGravity:0.25,springLength:150,springConstant:0.04,damping:0.18,avoidOverlap:0.6}}}},\n"
    "  interaction:{{hover:true,tooltipDelay:100,navigationButtons:false,zoomView:true,selectConnectedEdges:true,hoverConnectedEdges:true}}\n"
    "}});\n"
    "function resetAll(){{\n"
    "  var allN=ndata.getIds(),allE=edata.getIds(),rn=[],re2=[];\n"
    "  for(var i=0;i<allN.length;i++){{rn.push({{id:allN[i],opacity:1}});}}\n"
    "  for(var i=0;i<allE.length;i++){{re2.push({{id:allE[i],color:undefined}});}}\n"
    "  ndata.update(rn);edata.update(re2);\n"
    "  document.getElementById('panel').style.display='none';net.unselectAll();\n"
    "}}\n"
    "document.getElementById('btn-fit').onclick=function(){{net.fit({{animation:{{duration:500,easingFunction:'easeInOutQuad'}}}});}};\n"
    "document.getElementById('btn-zi').onclick=function(){{net.moveTo({{scale:net.getScale()*1.4,animation:{{duration:250}}}});}};\n"
    "document.getElementById('btn-zo').onclick=function(){{net.moveTo({{scale:net.getScale()/1.4,animation:{{duration:250}}}});}};\n"
    "document.getElementById('btn-rst').onclick=resetAll;\n"
    "document.getElementById('px').onclick=resetAll;\n"
    "net.on('click',function(p){{\n"
    "  if(!p.nodes.length){{resetAll();return;}}\n"
    "  var id=p.nodes[0],conn=net.getConnectedNodes(id),cedges=net.getConnectedEdges(id);\n"
    "  var allN=ndata.getIds(),allE=edata.getIds(),dn=[],bn=[{{id:id,opacity:1}}];\n"
    "  for(var i=0;i<allN.length;i++){{\n"
    "    if(allN[i]!==id&&conn.indexOf(allN[i])===-1){{dn.push({{id:allN[i],opacity:0.08}});}}\n"
    "    else if(allN[i]!==id){{bn.push({{id:allN[i],opacity:0.8}});}}\n"
    "  }}\n"
    "  ndata.update(dn);ndata.update(bn);\n"
    "  var de=[],be=[];\n"
    "  for(var j=0;j<allE.length;j++){{\n"
    "    if(cedges.indexOf(allE[j])===-1){{de.push({{id:allE[j],color:{{color:'rgba(189,52,254,0.04)'}}}});}}\n"
    "    else{{be.push({{id:allE[j],color:{{color:'rgba(224,64,251,0.95)'}}}});}}\n"
    "  }}\n"
    "  edata.update(de);edata.update(be);\n"
    "  var info=infoMap[String(id)];\n"
    "  if(info){{document.getElementById('pt').textContent=info.title;document.getElementById('pb').innerHTML=info.body;document.getElementById('panel').style.display='block';}}\n"
    "}});\n"
    "net.on('doubleClick',function(p){{if(p.nodes.length){{net.focus(p.nodes[0],{{scale:2.2,animation:{{duration:500,easingFunction:'easeInOutQuad'}}}});}}}});\n"
    "net.on('stabilizationIterationsDone',function(){{net.setOptions({{physics:{{enabled:false}}}});}});\n"
    '</script></body></html>"""\n'
    '                st.components.v1.html(_graph_html, height=700, scrolling=False)\n'
)

lines[start_idx:end_idx] = [new_section]
src = "".join(lines)
with open(path, 'w', encoding='utf-8') as f:
    f.write(src)
try:
    ast.parse(src)
    print(f"Syntax OK — {len(src)} chars")
except SyntaxError as e:
    print(f"SYN ERR line {e.lineno}: {e.msg}")
    ls = src.splitlines()
    for li in range(max(0, e.lineno-4), min(len(ls), e.lineno+3)):
        print(f"  {li+1:4}: {ls[li]}")
