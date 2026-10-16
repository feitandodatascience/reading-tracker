"""Privacy guard for committed notebooks (see CLAUDE.md, "Privacy").

Notebooks may only read public data (``data/processed/`` or ``data/demo/``) and
must be committed with outputs cleared, so private notes and exact timestamps
can't leak through a saved DataFrame preview.
"""

import json
from pathlib import Path

import pytest

NOTEBOOKS = sorted(
    (Path(__file__).resolve().parents[1] / "notebooks").glob("**/*.ipynb")
)
RAW_DATA_MARKERS = ("data/raw", "data\\raw", "RAW_DB_PATH", "reading.db", "connect()")


def code_cells(notebook: Path) -> list[dict]:
    cells = json.loads(notebook.read_text(encoding="utf-8"))["cells"]
    return [cell for cell in cells if cell["cell_type"] == "code"]


@pytest.mark.parametrize("notebook", NOTEBOOKS, ids=lambda path: path.name)
def test_notebook_has_no_saved_outputs(notebook):
    with_outputs = [cell for cell in code_cells(notebook) if cell.get("outputs")]
    assert not with_outputs, "Clear all outputs before committing this notebook."


@pytest.mark.parametrize("notebook", NOTEBOOKS, ids=lambda path: path.name)
def test_notebook_does_not_read_raw_data(notebook):
    source = "\n".join("".join(cell["source"]) for cell in code_cells(notebook))
    found = [marker for marker in RAW_DATA_MARKERS if marker in source]
    assert not found, f"Notebook references private data: {found}"
