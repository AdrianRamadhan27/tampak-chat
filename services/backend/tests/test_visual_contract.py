import pytest

from app.visuals import DiagramSpecification


def test_diagram_rejects_unknown_nodes_and_executable_fields():
    data = {
        "title": "Safe diagram",
        "nodes": [{"id": "n0", "label": "Read"}, {"id": "n1", "label": "Review"}],
        "edges": [{"from": "n0", "to": "n9"}],
        "citations": ["S1"],
    }
    with pytest.raises(ValueError):
        DiagramSpecification.model_validate(data)
    data["edges"] = [{"from": "n0", "to": "n1"}]
    data["javascript"] = "alert(1)"
    with pytest.raises(ValueError):
        DiagramSpecification.model_validate(data)
    del data["javascript"]
    assert DiagramSpecification.model_validate(data).model_dump(by_alias=True, exclude_none=True)[
        "edges"
    ] == [{"from": "n0", "to": "n1"}]
