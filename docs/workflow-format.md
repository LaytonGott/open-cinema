# ComfyUI workflow JSON format (UI format)

This describes the UI (graph) format that ComfyUI saves and loads, as seen in
`comfyui_workflow_templates_json/templates/api_bria_image_outpainting.json`
(frontend 1.40.10). It is not the API ("prompt") format.

## Top-level keys

| Key | Meaning |
| --- | --- |
| `id` | Workflow UUID string. |
| `revision` | Integer revision counter. |
| `last_node_id` | Highest node id used so far (integer). |
| `last_link_id` | Highest link id used so far (integer). |
| `nodes` | List of node objects. |
| `links` | List of link entries. |
| `groups` | List of group boxes (`[]` when none). |
| `config` | Object, usually `{}`. |
| `extra` | Free-form object: `ds` (canvas `scale` and `offset`), `frontendVersion`, and other frontend or extension data. |
| `version` | Schema version number, `0.4` here. |

## Node keys

| Key | Meaning |
| --- | --- |
| `id` | Integer node id, unique in the workflow. |
| `type` | Node class name, for example `LoadImage` or `PreviewImage`. |
| `pos` | `[x, y]` canvas position. |
| `size` | `[width, height]` in canvas units. |
| `flags` | Object, `{}` or for example `{"collapsed": false}`. |
| `order` | Integer execution order. |
| `mode` | Integer; `0` is normal (always run). |
| `inputs` | List of input entries (see below). |
| `outputs` | List of output entries (see below). |
| `properties` | Object, for example `"Node name for S&R"`, `cnr_id`, `ver`. |
| `widgets_values` | List of widget values in widget order. |

Some nodes also carry optional `color` and `bgcolor` strings.

## `inputs` entries

```json
{ "name": "images", "type": "IMAGE", "link": 73 }
```

`name` is the input name, `type` the socket type, `link` the id of the
connected link, or `null` when unconnected. An entry may also have `shape`
(for example `7` for an optional input).

## `outputs` entries

```json
{ "name": "IMAGE", "type": "IMAGE", "links": [73, 74], "slot_index": 0 }
```

`name` is the output name, `type` the socket type, `links` the list of link ids
leaving this output (or `null` when nothing is connected), and `slot_index` the
output's index on the node. `slot_index` is written by many ComfyUI versions
but is absent from the example file above; the slot is then the entry's
position in `outputs`.

## `links` entries

Each link is an array:

```json
[73, 42, 0, 43, 0, "IMAGE"]
```

`[id, from_node, from_slot, to_node, to_slot, type]`: link id, source node id,
source output slot, target node id, target input slot, and the socket type.
The id matches the `link` field of the target input and an item in the source
output's `links`.

## LoadImage

`widgets_values` is `[filename, "image"]`: the file name in ComfyUI's input
folder, then the upload widget's fixed value `"image"`.

```json
{
  "id": 11,
  "type": "LoadImage",
  "inputs": [],
  "outputs": [
    { "name": "IMAGE", "type": "IMAGE", "links": [70] },
    { "name": "MASK", "type": "MASK", "links": null }
  ],
  "widgets_values": ["baby_otter.png", "image"]
}
```

A `PreviewImage` node has one `images` input of type `IMAGE`, no outputs, and
`widgets_values` of `[]`.

## OpenOptics_DepthToMetric

Widget inputs, in `INPUT_TYPES` order:

| Input | Default |
| --- | --- |
| `near_m` | 0.5 |
| `far_m` | 10.0 |
| `inverse_depth` | true |
| `low_percentile` | 2.0 |
| `high_percentile` | 98.0 |
| `chunk_frames` | 8 |
| `mode` | near_far (`near_far` or `subject`) |
| `subject_m` | 3.0 |
| `subject_x` | 0.5 |
| `subject_y` | 0.5 |
| `subject_radius_px` | 4 |
| `anchor_scope` | batch (`batch` or `frame`) |

Linked inputs (all optional):

- `depth_mask` (`MASK`)
- `depth_image` (`IMAGE`)
- `subject_mask` (`MASK`)

Outputs (`RETURN_TYPES`):

- `depth_m` (`MASK`)
- `preview` (`IMAGE`)

## OpenOptics_FocalCrop

Widget inputs, in `INPUT_TYPES` order:

| Input | Default |
| --- | --- |
| `source_focal_mm` | 24.0 |
| `target_focal_mm` | 50.0 |
| `output_size` | original (`original` or `cropped`) |
| `chunk_frames` | 8 |

Linked inputs:

- `image` (`IMAGE`)

Outputs (`RETURN_TYPES`):

- `IMAGE` (`IMAGE`; the node defines no `RETURN_NAMES`)

## OpenOptics_DepthOfField

Widget inputs, in `INPUT_TYPES` order:

| Input | Default |
| --- | --- |
| `focal_mm` | 50.0 |
| `f_number` | 2.8 |
| `focus_m` | 3.0 |
| `sensor_width_mm` | 36.0 |
| `quality` | normal (`draft` or `normal`) |
| `max_radius_px` | 16 |
| `colorspace` | srgb (`srgb` or `linear`) |
| `chunk_frames` | 8 |

Linked inputs:

- `image` (`IMAGE`, required)
- `depth_mask` (`MASK`, optional)
- `depth_image` (`IMAGE`, optional)

Outputs (`RETURN_TYPES`):

- `image` (`IMAGE`)
- `coc_px` (`MASK`)

## OpenOptics_LensDistortion

Widget inputs, in `INPUT_TYPES` order:

| Input | Default |
| --- | --- |
| `focal_mm` | 35.0 |
| `sensor_width_mm` | 36.0 |
| `k1` | 0.0 |
| `k2` | 0.0 |
| `k3` | 0.0 |
| `p1` | 0.0 |
| `p2` | 0.0 |
| `direction` | apply (`apply` or `remove`) |
| `fit` | keep (`keep` or `crop`) |
| `chunk_frames` | 8 |

Linked inputs:

- `image` (`IMAGE`)

Outputs (`RETURN_TYPES`):

- `IMAGE` (`IMAGE`; the node defines no `RETURN_NAMES`)
