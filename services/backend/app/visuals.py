"""A constrained diagram interface; model output never contains executable markup."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DiagramNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^n\d{1,2}$")
    label: str = Field(min_length=1, max_length=100)


class DiagramEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    source: str = Field(alias="from", pattern=r"^n\d{1,2}$")
    to: str = Field(pattern=r"^n\d{1,2}$")
    label: str | None = Field(default=None, max_length=100)


class DiagramSpecification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=100)
    diagram_kind: Literal["flowchart", "sequence", "relationship"] = "flowchart"
    basis: Literal["document", "analysis", "application", "illustrative"] = "document"
    nodes: list[DiagramNode] = Field(min_length=2, max_length=20)
    edges: list[DiagramEdge] = Field(min_length=1, max_length=40)
    citations: list[str] = Field(max_length=8)

    @model_validator(mode="after")
    def valid_graph(self):
        ids = {node.id for node in self.nodes}
        if len(ids) != len(self.nodes):
            raise ValueError("Diagram node IDs must be unique.")
        if any(edge.source not in ids or edge.to not in ids for edge in self.edges):
            raise ValueError("Diagram edges must reference existing nodes.")
        if self.basis in {"document", "analysis"} and not self.citations:
            raise ValueError("A grounded diagram must cite its evidence.")
        return self
