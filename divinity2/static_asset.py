"""Static assets: a region's streamed props, at the level the game draws them.

What the engine does (GUP addresses; the Developer's Cut agrees where checked;
docs/sources.md, "Static assets"):

- Any node of the region's `StaticMeshes.nif` whose name contains `ASSET` is one
  (`CRegionVisual::ParseRegionNode` @6a3790). Its `UserPropBuffer` names the asset,
  `AssetFile="StaticAssets/Aleroth/AL_House_C.nif"`; the file name without folder and
  extension is the key (`CStaticAssetManager::Init` @6fe830).
- Under its `DummyAsset` child, one `NiLODNode` per model (`LODGroup01`, ...) holds level 0
  inline and an empty stub for every finer level. Level n > 0 is streamed from
  `Win32/CompiledAssets/<asset>/<LODGroupNN>/<n>.nif`, whose node carries the stub's name
  (`CStaticAssetDataManager::RequestLoadData` @73e040); the names per asset come from
  `Win32/CompiledAssets/AssetDataDescriptors.xml` (`CollectLODNodeNames` @73e310, which
  compares the asset name with `NiStricmp`: the tutorial's `AL_House_A_Piece_F` is the
  manifest's `AL_House_A_PIECE_F`). Level names are
  not unique across assets (15 are shared, e.g. `AL_Market_A_MAX` in `AL_Market_A` and
  `AL_Market_D`), so a stub is filled only from its own asset's files.
- With `StaticAssetHighQuality` on, as the game runs here, the finest level is always
  requested (`CStaticAsset::UpdateStreaming` @742c60) and the finest loaded one is drawn
  (`EvaluateLODNode` @742a40). Once filled, `divinity2.lod` shows that level: every asset
  `NiLODNode` orders its ranges finest nearest.
- The region's `StaticAssets.xml` gives each (asset, LOD group, placement) its switch
  distances in cm and whether it casts shadows; a placement it does not describe casts
  shadows, and one whose file name contains `_SHADOWDUMMY` is drawn only into shadows
  (`CStaticAssetManager::LoadXML` @6fe390, `FindDescriptor` @6fdfb0, `CStaticAssetDescriptor`
  constructor @740860).
"""

import re
from pathlib import Path

from . import lod, terrain

MANIFEST = Path("Win32") / "CompiledAssets" / "AssetDataDescriptors.xml"

_ASSET_FILE = re.compile(r'AssetFile="([^"]*)"')


def levels(game_root) -> dict:
    """`{(asset lower-cased, LOD group): {stub name: streamed file}}` for every level the game ships."""
    base = Path(game_root) / MANIFEST.parent
    found = {}
    for entry, name, index in terrain.manifest(Path(game_root) / MANIFEST):
        path = base / entry.get("base", "") / entry.get("sub", "") / f"{index}.nif"
        if index > 0 and name and path.is_file():
            found.setdefault((entry.get("base", "").lower(), entry.get("sub", "")), {})[name] = path
    return found


def asset_of(node) -> str | None:
    """The asset key of an `ASSET` node, or None for any other node."""
    if "ASSET" not in str(getattr(node, "name", "")):
        return None
    match = _ASSET_FILE.search(lod._user_prop(node))
    return Path(match.group(1).replace("\\", "/")).stem if match else None


def placements(root):
    """`(node, asset key)` for every static asset under `root`."""
    stack = [root]
    while stack:
        node = stack.pop()
        asset = asset_of(node)
        if asset is not None:
            yield node, asset
            continue
        stack += lod.child_nodes(node)


def graft(root, game_root) -> int:
    """Fill each static asset's empty level stubs from its own streamed files; how many were filled."""
    known, read, grafted = None, {}, 0
    for placed, asset in placements(root):
        if known is None:
            known = levels(game_root)
        stack = [placed]
        while stack:
            node = stack.pop()
            children = lod.child_nodes(node)
            stack += children
            if type(node).__name__ != "NiLODNode":
                continue
            files = known.get((asset.lower(), str(node.name)), {})
            for stub in children:
                name = str(getattr(stub, "name", ""))
                if name not in files or lod.child_nodes(stub):
                    continue
                grafted += terrain.fill_stub(stub, name, files[name], read)
    return grafted
