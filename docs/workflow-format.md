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
