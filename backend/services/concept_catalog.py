import sqlite3

from backend.concepts import (
    CATALOG_VERSION,
    CONCEPT_SEEDS,
    normalize_alias,
    normalize_area,
    seed_by_id,
    seed_for_value,
)
from backend.database import get_db_connection


class ConceptCatalog:
    CATALOG_VERSION = CATALOG_VERSION

    @staticmethod
    def _seed_dict(seed):
        if seed is None:
            return None
        return {
            "concept_id": seed.concept_id,
            "area": seed.area,
            "canonical_name": seed.canonical_name,
            "catalog_version": CATALOG_VERSION,
            "selectable": 1,
            "source": "seed",
        }

    @classmethod
    def get(cls, concept_id, area=None):
        if not isinstance(concept_id, str) or not concept_id.strip():
            return None
        concept_id = concept_id.strip()
        normalized_area = normalize_area(area) if area is not None else None

        seed = seed_by_id(concept_id)
        if seed is not None and (normalized_area is None or seed.area == normalized_area):
            return cls._seed_dict(seed)

        connection = get_db_connection()
        try:
            if normalized_area is None:
                row = connection.execute(
                    "SELECT * FROM concept_definitions WHERE concept_id = ?",
                    (concept_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT * FROM concept_definitions WHERE concept_id = ? AND area = ?",
                    (concept_id, normalized_area),
                ).fetchone()
            return dict(row) if row is not None else None
        except sqlite3.OperationalError:
            return None
        finally:
            connection.close()

    @classmethod
    def resolve(cls, area, value, selectable_only=False):
        normalized_area = normalize_area(area)
        seed = seed_for_value(normalized_area, value)
        if seed is not None:
            return cls._seed_dict(seed)

        if not isinstance(value, str) or not value.strip():
            return None

        direct = cls.get(value.strip(), area=normalized_area)
        if direct is not None:
            if selectable_only and not direct.get("selectable"):
                return None
            return direct

        normalized_alias = normalize_alias(value)
        if not normalized_alias:
            return None

        connection = get_db_connection()
        try:
            sql = """
                SELECT definition.*
                FROM concept_aliases AS alias
                JOIN concept_definitions AS definition
                  ON definition.concept_id = alias.concept_id
                WHERE alias.area = ?
                  AND alias.normalized_alias = ?
            """
            if selectable_only:
                sql += " AND definition.selectable = 1"
            row = connection.execute(sql, (normalized_area, normalized_alias)).fetchone()
            return dict(row) if row is not None else None
        except sqlite3.OperationalError:
            return None
        finally:
            connection.close()

    @classmethod
    def list_selectable(cls, area):
        normalized_area = normalize_area(area)
        # Seeds are the complete selectable catalog in v1; no DB read is needed.
        return [
            cls._seed_dict(seed)
            for seed in CONCEPT_SEEDS
            if seed.area == normalized_area
        ]

    @classmethod
    def canonical_name(cls, area, value):
        concept = cls.resolve(area, value)
        return concept.get("canonical_name") if concept else None

    @classmethod
    def concept_id(cls, area, value, selectable_only=False):
        concept = cls.resolve(area, value, selectable_only=selectable_only)
        return concept.get("concept_id") if concept else None

    @classmethod
    def seeded_ids(cls, area):
        normalized_area = normalize_area(area)
        return [seed.concept_id for seed in CONCEPT_SEEDS if seed.area == normalized_area]
