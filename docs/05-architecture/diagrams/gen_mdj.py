#!/usr/bin/env python3
"""Emit a StarUML .mdj model of the TrustLens level 0 DFD.

StarUML ships no DFD notation, so the model is expressed in core UML types that
open in any StarUML install without extensions:

    process 0        -> UMLClass, stereotype <<process>>
    terminators      -> UMLClass, stereotype <<external entity>>
    the 18 flows     -> UMLAssociation, end2 navigable, name = flow label

Geometry mirrors the published figure: users left, governance and providers
right, process 0 in the middle. Re-run after editing FLOWS or ENTITIES.
"""

import json
from pathlib import Path

OUT = Path(__file__).with_name("TrustLens-DFD-Level0.mdj")

# ---------------------------------------------------------------- geometry ---
PROC = dict(left=520, top=250, width=250, height=190)
ENT_W, ENT_H = 190, 54
LEFT_X, RIGHT_X = 90, 1000

# name, documentation, side, top
ENTITIES = [
    ("E1", "Reporting user",     "P1 Priya, 34 · P2 Ramesh, 68. Submits suspicious artifacts and "
                                 "receives a verdict, an evidence trace and a report bundle.", "L",  70),
    ("E2", "Analyst",            "P3 Anjali. Reviews cases routed past the uncertainty threshold "
                                 "and adjudicates them with recorded rationale.",              "L", 230),
    ("E3", "Administrator",      "P6. Operates the platform: thresholds, retention class, "
                                 "feature flags, rate limits.",                                "L", 390),
    ("E4", "Report recipient",   "Authority, bank or reporting portal. Receives the bundle only "
                                 "through a user-initiated, access-controlled export (NG-01).", "L", 550),
    ("E5", "Guidance bodies",    "I4C · CERT-In · RBI · NPCI · SEBI · DoT. Published material is "
                                 "consumed one way and graded before any rule may cite it.",    "R",  70),
    ("E6", "Knowledge editor",   "P4 Vikram. Authors versioned rule JSON with graded source "
                                 "references; never touches engine code (ADR-0003).",           "R", 200),
    ("E7", "Knowledge approver", "P5 Meera. Gate-keeps publication on diff, impact analysis "
                                 "and regression evidence.",                                    "R", 330),
    ("E8", "URL & threat-intel providers",
                                 "Post-MVP. Provider-agnostic reputation adapters; the core "
                                 "path completes with any single provider unavailable.",         "R", 460),
    ("E9", "AI assist provider", "Post-MVP, feature-flagged. Non-authoritative: output is "
                                 "schema-validated, labelled model-derived, human-approved.",   "R", 590),
]

# flow id, label, entity, direction ("in" = entity -> process)
FLOWS = [
    ("F1",  "F1 submitted artifacts",       "E1", "in"),
    ("F2",  "F2 correction · re-evaluate",  "E1", "in"),
    ("F3",  "F3 verdict + evidence trace",  "E1", "out"),
    ("F4",  "F4 report bundle + hashes",    "E1", "out"),
    ("F5",  "F5 queued uncertain case",     "E2", "out"),
    ("F6",  "F6 adjudication + rationale",  "E2", "in"),
    ("F7",  "F7 config · retention policy", "E3", "in"),
    ("F8",  "F8 health · audit · metrics",  "E3", "out"),
    ("F9",  "F9 access-controlled export",  "E4", "out"),
    ("F10", "F10 published advisories",     "E5", "in"),
    ("F11", "F11 draft rule + sources",     "E6", "in"),
    ("F12", "F12 schema + lint verdict",    "E6", "out"),
    ("F13", "F13 diff · impact · replay",   "E7", "out"),
    ("F14", "F14 publish / reject",         "E7", "in"),
    ("F15", "F15 reputation lookup",        "E8", "out"),
    ("F16", "F16 provider verdict",         "E8", "in"),
    ("F17", "F17 isolated content prompt",  "E9", "out"),
    ("F18", "F18 schema-checked draft",     "E9", "in"),
]

PROJECT, MODEL, DIAGRAM = "TL-PROJECT", "TL-MODEL", "TL-DIAGRAM-L0"
PROC_ID, PROC_VIEW = "TL-P0", "V-TL-P0"

ref = lambda i: {"$ref": i}


def label(vid, parent, model, text, font="Arial;13;0"):
    return {"_type": "LabelView", "_id": vid, "_parent": ref(parent),
            "model": ref(model), "font": font, "text": text,
            "horizontalAlignment": 2, "visible": bool(text)}


def class_view(vid, cid, name, stereo, left, top, width, height):
    """A UMLClassView with the full compartment set StarUML expects."""
    nc, ac, oc, rc, tc = (f"{vid}-NC", f"{vid}-AC", f"{vid}-OC", f"{vid}-RC", f"{vid}-TC")
    name_comp = {
        "_type": "UMLNameCompartmentView", "_id": nc, "_parent": ref(vid),
        "model": ref(cid),
        "subViews": [
            label(f"{nc}-name", nc, cid, name, "Arial;13;1"),
            label(f"{nc}-stereo", nc, cid, f"«{stereo}»"),
            label(f"{nc}-namespace", nc, cid, ""),
            label(f"{nc}-property", nc, cid, ""),
        ],
        "nameLabel": ref(f"{nc}-name"),
        "stereotypeLabel": ref(f"{nc}-stereo"),
        "namespaceLabel": ref(f"{nc}-namespace"),
        "propertyLabel": ref(f"{nc}-property"),
    }
    empties = [{"_type": t, "_id": i, "_parent": ref(vid), "model": ref(cid), "subViews": []}
               for t, i in (("UMLAttributeCompartmentView", ac),
                            ("UMLOperationCompartmentView", oc),
                            ("UMLReceptionCompartmentView", rc),
                            ("UMLTemplateParameterCompartmentView", tc))]
    return {
        "_type": "UMLClassView", "_id": vid, "_parent": ref(DIAGRAM),
        "model": ref(cid), "subViews": [name_comp] + empties,
        "left": left, "top": top, "width": width, "height": height,
        "nameCompartment": ref(nc),
        "attributeCompartment": ref(ac),
        "operationCompartment": ref(oc),
        "receptionCompartment": ref(rc),
        "templateParameterCompartment": ref(tc),
        "suppressAttributes": True, "suppressOperations": True,
        "stereotypeDisplay": "label", "showVisibility": False,
    }


def assoc(aid, name, src, dst):
    return {
        "_type": "UMLAssociation", "_id": aid, "_parent": ref(src),
        "name": name,
        "end1": {"_type": "UMLAssociationEnd", "_id": f"{aid}-e1", "_parent": ref(aid),
                 "reference": ref(src), "navigable": "notNavigable"},
        "end2": {"_type": "UMLAssociationEnd", "_id": f"{aid}-e2", "_parent": ref(aid),
                 "reference": ref(dst), "navigable": "navigable"},
    }


def assoc_view(vid, aid, tail_view, head_view, points, name):
    ne1, ne2 = f"{vid}-END1", f"{vid}-END2"
    end_view = lambda i, edge: {
        "_type": "UMLAssociationEndView", "_id": i, "_parent": ref(vid),
        "model": ref(f"{aid}-e{edge}"), "edgePosition": 0, "subViews": [],
        "visible": False,
    }
    return {
        "_type": "UMLAssociationView", "_id": vid, "_parent": ref(DIAGRAM),
        "model": ref(aid), "tail": ref(tail_view), "head": ref(head_view),
        "points": points, "lineStyle": 0,
        "subViews": [
            {"_type": "EdgeLabelView", "_id": f"{vid}-NAME", "_parent": ref(vid),
             "model": ref(aid), "font": "Arial;11;0", "text": name,
             "edgePosition": 1, "distance": 18, "alpha": 0.5, "hostEdge": ref(vid)},
            {"_type": "EdgeLabelView", "_id": f"{vid}-STEREO", "_parent": ref(vid),
             "model": ref(aid), "font": "Arial;11;0", "text": "",
             "edgePosition": 1, "distance": 34, "alpha": 0.5, "visible": False,
             "hostEdge": ref(vid)},
            end_view(ne1, 1), end_view(ne2, 2),
        ],
        "nameLabel": ref(f"{vid}-NAME"),
        "stereotypeLabel": ref(f"{vid}-STEREO"),
        "tailRoleEnd": ref(ne1), "headRoleEnd": ref(ne2),
        "showVisibility": False, "showMultiplicity": False,
    }


# ------------------------------------------------------------------- build ---
elements, views = [], []

elements.append({
    "_type": "UMLClass", "_id": PROC_ID, "_parent": ref(MODEL),
    "name": "0. TrustLens", "stereotype": "process",
    "documentation": ("Process 0 — the entire system as one process. Explainable scam detection, "
                      "evidence preservation and assisted reporting. Rules-as-data decide; AI is "
                      "never the decision authority. No data stores appear at level 0."),
    "attributes": [], "operations": [],
})
views.append(class_view(PROC_VIEW, PROC_ID, "0. TrustLens", "process", **PROC))

geom = {}
for eid, name, doc, side, top in ENTITIES:
    left = LEFT_X if side == "L" else RIGHT_X
    geom[eid] = dict(side=side, top=top, left=left)
    elements.append({
        "_type": "UMLClass", "_id": eid, "_parent": ref(MODEL), "name": name,
        "stereotype": "external entity", "documentation": doc,
        "attributes": [], "operations": [],
    })
    views.append(class_view(f"V-{eid}", eid, name, "external entity",
                            left, top, ENT_W, ENT_H))

# spread each side's flows down the process edge so parallel lines never overlap
slots = {"L": [f for f in FLOWS if geom[f[2]]["side"] == "L"],
         "R": [f for f in FLOWS if geom[f[2]]["side"] == "R"]}
proc_y = {}
for side, group in slots.items():
    for n, flow in enumerate(group, start=1):
        proc_y[flow[0]] = PROC["top"] + round(PROC["height"] * n / (len(group) + 1))

per_entity = {}
for fid, _, eid, _ in FLOWS:
    per_entity.setdefault(eid, []).append(fid)

for fid, text, eid, direction in FLOWS:
    g = geom[eid]
    siblings = per_entity[eid]
    ey = g["top"] + round(ENT_H * (siblings.index(fid) + 1) / (len(siblings) + 1))
    ex = g["left"] + ENT_W if g["side"] == "L" else g["left"]
    px = PROC["left"] if g["side"] == "L" else PROC["left"] + PROC["width"]
    py = proc_y[fid]

    src, dst = (eid, PROC_ID) if direction == "in" else (PROC_ID, eid)
    tail, head = (f"V-{eid}", PROC_VIEW) if direction == "in" else (PROC_VIEW, f"V-{eid}")
    pts = f"{ex}:{ey};{px}:{py}" if direction == "in" else f"{px}:{py};{ex}:{ey}"

    elements.append(assoc(f"A-{fid}", text, src, dst))
    views.append(assoc_view(f"V-A-{fid}", f"A-{fid}", tail, head, pts, text))

diagram = {
    "_type": "UMLClassDiagram", "_id": DIAGRAM, "_parent": ref(MODEL),
    "name": "DFD Level 0 — Context Diagram", "defaultDiagram": True,
    "documentation": ("TrustLens level 0 DFD. 1 process, 9 external entities, 18 flows "
                      "(9 in, 9 out), no data stores. Derived from PROGRAM-001 v1.1, "
                      "RESEARCH-001…005 and ADR-0003 — not the Phase 5 ARCH-001 artifact."),
    "ownedViews": views,
}

project = {
    "_type": "Project", "_id": PROJECT, "name": "TrustLens",
    "author": "TrustLens programme",
    "documentation": "Level 0 data flow diagram for the TrustLens platform.",
    "ownedElements": [{
        "_type": "UMLModel", "_id": MODEL, "_parent": ref(PROJECT), "name": "TrustLens DFD",
        "ownedElements": [diagram] + elements,
    }],
}

OUT.write_text(json.dumps(project, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

# ------------------------------------------------------------------ verify ---
raw = json.loads(OUT.read_text(encoding="utf-8"))
ids, refs = set(), []


def walk(node, path="$"):
    if isinstance(node, dict):
        if "$ref" in node and len(node) == 1:
            refs.append((node["$ref"], path))
            return
        if "_id" in node:
            assert node["_id"] not in ids, f"duplicate _id {node['_id']} at {path}"
            ids.add(node["_id"])
        for k, v in node.items():
            walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for n, v in enumerate(node):
            walk(v, f"{path}[{n}]")


walk(raw)
dangling = [(r, p) for r, p in refs if r not in ids]
assert not dangling, f"dangling $ref: {dangling[:5]}"

print(f"wrote {OUT.name}: {OUT.stat().st_size:,} bytes")
print(f"  unique _id       {len(ids)}")
print(f"  $ref resolved    {len(refs)} / {len(refs)}")
print(f"  UMLClass         {sum(1 for e in elements if e['_type'] == 'UMLClass')}")
print(f"  UMLAssociation   {sum(1 for e in elements if e['_type'] == 'UMLAssociation')}")
print(f"  views on diagram {len(views)}")
