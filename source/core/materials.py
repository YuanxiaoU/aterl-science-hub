# -*- coding: utf-8 -*-
"""物料数据库: 默认物料体系 + 用户自定义物料 (持久化 JSON)"""
import json
from dataclasses import dataclass, field, asdict

from .config import CUSTOM_MATERIAL_FILE


@dataclass
class Component:
    name: str = ""
    frac: float = 0.0      # 质量分数 %
    bp: float = 100.0      # 常压沸点 ℃
    density: float = 0.8   # g/cm3
    hazard: str = ""


@dataclass
class MaterialSystem:
    name: str = ""
    components: list = field(default_factory=list)   # [Component]
    note: str = ""


def _default_materials():
    return [
        MaterialSystem("丙烯酸甲酯体系(含伴生物)", [
            Component("丙烯酸甲酯", 72.0, 80.5, 0.953, "易燃, 受热易聚合"),
            Component("甲醇(伴生)", 23.0, 64.7, 0.792, "易燃, 有毒"),
            Component("水", 5.0, 100.0, 1.000, ""),
        ], "酯化反应产物体系, 回收甲醇/精制丙烯酸甲酯"),
        MaterialSystem("乙醇-水体系", [
            Component("乙醇", 88.0, 78.37, 0.789, "易燃"),
            Component("水", 12.0, 100.0, 1.000, ""),
        ], "乙醇精馏提浓 (共沸物, 常压最高约95%质)"),
    ]


def load_custom():
    out = []
    try:
        with open(CUSTOM_MATERIAL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for m in data:
            comps = [Component(**c) for c in m.get("components", [])]
            out.append(MaterialSystem(m.get("name", ""), comps, m.get("note", "")))
    except Exception:
        pass
    return out


def save_custom(materials):
    data = []
    for m in materials:
        data.append({"name": m.name, "note": m.note,
                     "components": [asdict(c) for c in m.components]})
    try:
        with open(CUSTOM_MATERIAL_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def all_materials():
    """返回默认 + 自定义物料列表"""
    return _default_materials() + load_custom()


def find_material(name):
    for m in all_materials():
        if m.name == name:
            return m
    return all_materials()[0]
