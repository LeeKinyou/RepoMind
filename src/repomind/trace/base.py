"""Shared models and protocol for failure parsers."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field


class TraceFrame(BaseModel):
    file_path: str
    line_number: int = Field(ge=1)
    function_name: str


class ExceptionInfo(BaseModel):
    type: str
    message: str


class ParsedFailure(BaseModel):
    raw_text: str
    frames: list[TraceFrame] = Field(default_factory=list)
    exceptions: list[ExceptionInfo] = Field(default_factory=list)
    chain_markers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def proximate_frame(self) -> TraceFrame | None:
        return self.frames[-1] if self.frames else None


class TraceParser(Protocol):
    def can_parse(self, text: str) -> bool:
        ...

    def parse(self, text: str) -> ParsedFailure:
        ...

