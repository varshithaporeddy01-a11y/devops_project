"""
GraphMind Standard — FastAPI backend.

Endpoints:
    GET  /api/health          - liveness check
    POST /api/parse           - source code -> {nodes, edges} structural AST graph (all languages)
    POST /api/trace           - source code -> dynamic execution frames (Python only; others -> supported:false)
    POST /api/complexity      - source code -> empirical Big-O benchmark (Python only; others -> supported:false)

Run locally:
    uvicorn main:app --reload --port 8000
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from parsers.ast_parser import parse_code_to_graph
from tracer.execution import run_complexity_benchmark, trace_execution

FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")

app = FastAPI(
    title="GraphMind Standard API",
    description="Code inspection & execution visualizer backend",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ParseRequest(BaseModel):
    code: str = Field(..., description="Source code to parse")
    language: str = Field(..., description="Language identifier")


class ParseResponse(BaseModel):
    nodes: list[dict]
    edges: list[dict]
    hasError: bool


class TraceRequest(BaseModel):
    code: str = Field(..., description="Source code to execute and trace")
    language: str = Field(..., description="Language identifier")


class LoopInfo(BaseModel):
    var: str | None
    iteration: int
    total: int | None


class CallInfo(BaseModel):
    function: str
    args: dict | None = None
    value: object | None = None


class TraceFrame(BaseModel):
    step: int
    activeLine: int
    event: str
    operation: str
    description: str
    callStack: list[str]
    variables: dict
    arrayName: str | None
    arrayState: list
    pointers: dict
    loop: LoopInfo | None
    callInfo: CallInfo | None


class TraceResponse(BaseModel):
    supported: bool
    message: str | None
    frames: list[TraceFrame]
    stdout: str
    error: str | None


class ComplexityRequest(BaseModel):
    code: str = Field(..., description="Source code to benchmark across N")
    language: str = Field(..., description="Language identifier")


class ComplexityResponse(BaseModel):
    supported: bool
    message: str | None
    n_values: list[int]
    step_counts: list[int]
    estimated_big_o: str | None
    error: str | None


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/parse", response_model=ParseResponse)
def parse(payload: ParseRequest) -> ParseResponse:
    try:
        graph = parse_code_to_graph(payload.code, payload.language)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ParseResponse(**graph)


@app.post("/api/trace", response_model=TraceResponse)
def trace(payload: TraceRequest) -> TraceResponse:
    result = trace_execution(payload.code, payload.language)
    return TraceResponse(**result)


@app.post("/api/complexity", response_model=ComplexityResponse)
def complexity(payload: ComplexityRequest) -> ComplexityResponse:
    result = run_complexity_benchmark(payload.code, payload.language)
    return ComplexityResponse(**result)
