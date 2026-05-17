"""Schemas Pydantic do modulo de telemetria."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TelemetryPoint(BaseModel):
    """Um ponto de uma serie temporal."""

    time: datetime
    variable: str
    value: float
    unit: str
    quality: int


class TelemetrySeriesOut(BaseModel):
    """Resposta da consulta de serie temporal."""

    asset_tag: str
    variable: str | None
    count: int
    points: list[TelemetryPoint]


class LatestReading(BaseModel):
    """Valor instantaneo mais recente de uma variavel."""

    variable: str
    value: float
    unit: str
    quality: int
    time: datetime


class LatestOut(BaseModel):
    """Snapshot com a ultima leitura de cada variavel do ativo."""

    asset_tag: str
    readings: list[LatestReading]
