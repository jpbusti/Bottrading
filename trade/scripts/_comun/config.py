"""Carga de config.yaml de una estrategia. Vive en scripts/ (nunca en validacion/): la dependencia es scripts -> validacion."""
from __future__ import annotations

from pathlib import Path

import yaml


def cargar_config(carpeta_estrategia: str | Path) -> dict:
    """Lee <carpeta_estrategia>/config.yaml. Falla si falta o esta vacio (no hay valores por defecto ocultos)."""
    ruta = Path(carpeta_estrategia) / "config.yaml"
    with open(ruta, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not cfg:
        raise ValueError(f"{ruta} vacio")
    return cfg
