# GMT mesh format (gMotor2 / rFactor 1)

Reverse-engineered from the working install, 2026-06-06, by decoding
extracted `.gmt` members (groundplane, scenery, car body) and validating
geometry against known world coordinates (AIW waypoints, vehicle bbox in
meters).  Implemented in `juliaMotor/RFactorData/src/gmt.jl`.

GMT is the gMotor2 mesh container — geometry + per-LOD materials/textures.
For juliaMotor it serves two jobs: rendering (Phase 4.3) and the track
collision surface / HAT (the gate for standalone physics).

## Header

| Offset | Type | Meaning |
|-------:|------|---------|
| `0x00` | u32 | per-file signature — varies, lightly obfuscated (e.g. `f2225500`, `50050000`); **not** a constant magic |
| `0x04` | u32 | `0x04000020` — version/flags, constant across every mesh in the corpus |
| `0x08` | float[3]×8 | axis-aligned bounding box, 8 corners. Meters, ISI frame (+x left, **+y up**, +z rearward). Verified: BRM body = 3.9 m long × 1.1 m wide × 0.94 m tall |
| `0x180` | u32[8] | section table (see below) |
| `0x194` | char[] | object name, NUL-terminated (`groundplane`, `brm_body`) |

The `0x68`–`0xc8` gap and `0x1e8`–`0x2d8` gap are zero-filled reserved
buffers (fixed-size name/scratch fields).

### Section table at `0x180`

Eight u32 slots.  **Slot 4 (`0x190`) is the vertex-array byte offset** —
confirmed in both the trivial groundplane (→ `0x3c4`) and the car body
(→ `0x162a3c`, where a stride-32 vertex run begins).  The other slots
carry counts/pointers whose exact meaning still differs between trivial
single-group meshes and multi-group/multi-LOD vehicle meshes (the
remaining decode work).

## Vertices — stride 32, non-interleaved attributes

Each vertex record is 32 bytes:

| Within record | Type | Meaning |
|--------------:|------|---------|
| `+0`  | u32 | pad / leading word (0) |
| `+4`  | float[3] | **position** (x, y, z) |
| `+16` | float[3] | **normal** |
| `+28` | u32 | vertex **color**, RGBA (`0xffffffff` = white) |

UV texture coordinates are stored in a **separate array** following the
vertex block (non-interleaved). The groundplane's UVs are all `0/16` —
the 16× tiling of a large ground quad — which is what first revealed the
arrays are split.

The vertex count is bounded exactly: `vptr + nverts*32` lands on the
start of the UV array. For the groundplane, `0x3c4 + 6*32 = 0x484` = UV
array start.

## Indices — sequential u16 triangle soup

A `u16` triangle list sits after the vertex/attribute region.  In this
corpus it is always a **sequential triangle soup**: the array is exactly
`0,1,2,…,3·ntri-1`, so each vertex is referenced once, in draw order
(triangle `t` = verts `3t,3t+1,3t+2`).  The decoder finds the longest
strictly-sequential u16 run (`index[k]==k`) whose implied vertex block
(`len·32` bytes from `vptr`) fits before it; this is unambiguous where a
"longest valid run" heuristic gets fooled by coincidental small-integer
patterns in the attribute arrays.  `nverts = run length`.

Examples (Zandvoort `Zand67.mas`): groundplane 6 verts / 2 tris;
asphalt01 2025 / 675; grass01 10140 / 3380; curb01 1446 / 482.  All 260
GMTs in the archive decode with in-range indices; 11,940 triangles total.

The per-vertex attribute arrays (normals, UVs) that follow the vertex
positions contain small near-origin values, so a naive "vertices are the
in-bbox floats" cutoff over-counts wildly (asphalt read 5700 instead of
2025) — `nverts` must come from the index run, not the bbox.

## Materials and LODs

After geometry come material descriptors:

- material name (`GRASASHD`)
- LOD texture slots `L0DIFFUSET0`, `L1DIFFUSET0`, `L2DIFFUSET0` — one per
  level of detail
- referenced texture filenames (`zan_inf02_d.dds`), one per LOD slot

So a mesh can carry several LODs and several materials; the loader
currently decodes the primary geometry group (sufficient for the track
surface). Vehicle bodies are large multi-group meshes (the BRM body LOD0
vertex block alone is ~30 k vertices) whose full group walk is the next
step.

## Validated decode

`GROUNDPLANE.GMT` (Zandvoort, 2856 bytes) decodes to exactly 6 vertices /
2 triangles, all normals `(0, 1, 0)` (up), positions on the `y = -4.05 m`
ground plane spanning the scenery bbox — matching the in-file bounding
box. This is the end-to-end correctness anchor for `parse_gmt`.

## UVs and per-vertex attributes (partial)

UV coordinates live in a separate array immediately after the vertex
positions (`vptr + nverts*32`).  On the plain groundplane the stride is 16
bytes/vertex and the first two floats are the diffuse `(u, v)` — giving a
clean quad mapping `(0,0),(16,0),(16,16),…` (16× tiling).  **But textured
meshes carry more per-vertex attribute data**: asphalt01 has ~56
bytes/vertex between the positions and the index array — multiple UV
channels plus tangents, because its material uses bump/spec maps
(`L1BUMPSPECMAPT0`).  So the post-position attribute stride is
material/shader-dependent; a general UV extractor must key off the
material's texture-slot set.  Geometry (positions + triangles) is fully
recovered regardless; UVs are a bounded follow-on for the renderer.

## Remaining work

1. General UV extraction: map each material's texture-slot set to its
   per-vertex attribute stride (diffuse UV is the first channel).
2. Material → texture mapping (rendering) and material → surface-type
   wiring for HAT (collision grip via the track `.tdf`).
3. Index width: confirm u16 vs u32 on meshes with > 65535 vertices
   (all corpus meshes seen so far are u16 sequential soup).
