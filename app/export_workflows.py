"""Export the two example ComfyUI workflows of the director app to workflows/.

export() writes open_cinema_generate.json and open_cinema_optics.json (API-format
graphs built by app.graphs) and returns their paths.
"""

import json
import sys
from pathlib import Path

from app import graphs, shot

EXAMPLE_SHOT = {
    "description": "A saxophone player on a rain-wet night street, neon reflections in the puddles",
    "camera": "dolly-in",
    "lens_mm": 50,
    "framing": "waist-up",
}
EXAMPLE_PROMPT = shot.build_prompt(EXAMPLE_SHOT)


def export(dest_dir) -> list:
    """Write the generation and optics example graphs as JSON into dest_dir.

    dest_dir is a folder path (created if missing). The optics graph uses a 50 mm
    lens, f/2.8 and a subject distance of 5.1005 metres. Returns a list of the two
    written Paths, open_cinema_generate.json first.
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    generate = graphs.build_generation_graph(EXAMPLE_PROMPT, 42, "opencinema/example/before")
    optics = graphs.build_optics_graph("example.mp4", 50, 2.8, 5.1005, "opencinema/example/after")
    written = []
    for name, graph in (("open_cinema_generate.json", generate), ("open_cinema_optics.json", optics)):
        path = dest / name
        path.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8", newline="\n")
        written.append(path)
    return written


def main(argv=None) -> int:
    """Export the example workflows to the repository's workflows/ folder.

    argv is unused. Prints each written path and returns the exit code 0.
    """
    for path in export(Path(__file__).resolve().parent.parent / "workflows"):
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
