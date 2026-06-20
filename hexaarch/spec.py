"""스펙 IR — Pydantic 모델 + 검증. (DESIGN §4.1, §16.5)

LLM이든 사람이든 만든 domain-spec.yaml은 여기를 통과해야만 다음 단계로 간다.
검증 = (1) 스키마 형태(Pydantic) + (2) 스펙 레벨 충돌 판정(§10.3 맛보기):
  - 전이는 선언된 상태만 참조  - 가드 on은 실재 전이만 참조  - 자기 전이 금지 등.
검증 실패는 '깨진 IR 거부'(§16.5) — 생성으로 넘어가지 않는다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class Guard(BaseModel):
    edge: str          # "FROM->TO"  (필드명 'on'은 YAML이 boolean으로 해석하는 푸시건)
    id: str
    desc: str


class Invariant(BaseModel):
    id: str
    desc: str


class RelationshipInvariant(BaseModel):
    id: str
    desc: str
    enforced_by: Literal["store", "adapter"] = "store"


class Formula(BaseModel):
    id: str
    name: str


class Domain(BaseModel):
    kind: Literal["aggregate", "calculation", "reference"]
    states: list[str] = Field(default_factory=list)
    transitions: dict[str, list[str]] = Field(default_factory=dict)
    guards: list[Guard] = Field(default_factory=list)
    invariants: list[Invariant] = Field(default_factory=list)
    relationship_invariants: list[RelationshipInvariant] = Field(default_factory=list)
    formulas: list[Formula] = Field(default_factory=list)
    ports_out: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self):
        if self.kind == "aggregate":
            if not self.states:
                raise ValueError("aggregate 도메인은 states 필수")
            sset = set(self.states)
            for frm, tos in self.transitions.items():
                if frm not in sset:
                    raise ValueError(f"전이 출발 상태 '{frm}'가 states에 없음")
                for to in tos:
                    if to not in sset:
                        raise ValueError(f"전이 도착 상태 '{to}'가 states에 없음")
                    if to == frm:
                        raise ValueError(f"자기 전이 금지: {frm}->{to}")
            for g in self.guards:
                frm, _, to = g.edge.partition("->")
                if to not in self.transitions.get(frm, []):
                    raise ValueError(f"가드 edge '{g.edge}'에 해당하는 전이가 없음")
        if self.kind == "calculation" and not self.formulas:
            raise ValueError("calculation 도메인은 formulas 필수")
        return self


class DecisionTable(BaseModel):
    name: str
    kind: Literal["range", "lookup", "flag"]
    inputs: list[str]
    output: str
    versioned: bool = False
    id: str


class Relation(BaseModel):
    to: str
    via: Literal["event", "call"]
    event: str | None = None


class Context(BaseModel):
    name: str
    domains: dict[str, Domain] = Field(default_factory=dict)
    decision_tables: list[DecisionTable] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)


class Infrastructure(BaseModel):
    database: str
    messaging: str
    task_queue: str | None = None
    web: Literal["none", "drf"] = "none"   # 웹 어댑터 생성 여부(기본 미생성). drf=§11 디폴트


class Spec(BaseModel):
    version: str
    infrastructure: Infrastructure
    contexts: list[Context]

    @model_validator(mode="after")
    def _check_relations(self):
        names = {c.name for c in self.contexts}
        for c in self.contexts:
            for r in c.relations:
                if r.to not in names:
                    raise ValueError(f"관계 대상 컨텍스트 '{r.to}' 미정의")
        return self


def load_spec(path: str | Path) -> Spec:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return Spec.model_validate(data)   # 깨진 IR이면 여기서 ValidationError
