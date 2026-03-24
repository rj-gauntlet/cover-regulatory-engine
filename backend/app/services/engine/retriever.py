"""Layer 3: RAG retrieval + LLM interpretation for ambiguous regulations."""
import json
import logging

from sqlalchemy import text, bindparam
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import String
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.schemas import ConstraintSchema, CitationSchema, ParcelSchema
from app.services.llm.base import LLMService

logger = logging.getLogger(__name__)

ASSESSMENT_SYSTEM_PROMPT = """You are a zoning regulation expert for the City of Los Angeles.
Given parcel information and relevant regulatory text, identify additional building constraints
that are NOT already covered by the provided deterministic constraints.

Focus on:
- Overlay zone restrictions
- Specific plan requirements
- Special conditions or exceptions
- Use restrictions beyond basic zoning
- Any nuanced rules that require interpretation

For each constraint you identify, provide:
1. category: one of "setback", "height", "far", "use", "density", "parking", "coverage", "adu", "other"
2. parameter: a snake_case identifier
3. rule_text: human-readable description of the constraint
4. value: the constraint value (if applicable)
5. unit: the unit (ft, ratio, stories, etc.)
6. confidence: 0.0-1.0 (how certain you are)
7. reasoning: how you derived this from the source text
8. citation_text: the specific passage from the regulation that supports this

Return a JSON object with a "constraints" key containing an array of constraint objects.
Example: {"constraints": [...]}
If no additional constraints are found, return {"constraints": []}.
Only include constraints you are reasonably confident about (confidence >= 0.5).
Do NOT repeat constraints that are already in the deterministic list provided."""

ASSESSMENT_USER_TEMPLATE = """Parcel Information:
- Address: {address}
- Zone: {zone_code} (class: {zone_class})
- Height District: {height_district}
- Lot Area: {lot_area} sqft
- Building Type: {building_type}
- Specific Plan: {specific_plan}
- Overlay Zones: {overlays}

Already-determined constraints (DO NOT repeat these):
{existing_constraints}

Relevant regulatory text passages:
{regulatory_text}

Identify any ADDITIONAL constraints not covered above. Return as a JSON object with a "constraints" key."""


class RegulatoryRetriever:
    """RAG-based retrieval and LLM interpretation of regulations."""

    def __init__(self, db: AsyncSession, llm: LLMService):
        self.db = db
        self.llm = llm

    async def retrieve_relevant_chunks(
        self, query: str, zone_codes: list[str], limit: int = 10
    ) -> list[dict]:
        """Hybrid search: metadata filter + vector similarity."""
        query_embedding = await self.llm.embed_single(query)

        zone_array = zone_codes + ["GENERAL"]

        sql = text("""
            SELECT
                id, chunk_text, section_number, topic, zone_codes,
                embedding <=> CAST(:embedding AS vector) AS distance
            FROM regulatory_chunks
            WHERE zone_codes && :zone_filter
              AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
        """).bindparams(bindparam("zone_filter", type_=ARRAY(String)))

        result = await self.db.execute(
            sql,
            {
                "embedding": str(query_embedding),
                "zone_filter": zone_array,
                "limit": limit,
            },
        )
        rows = result.fetchall()

        return [
            {
                "id": str(row[0]),
                "text": row[1],
                "section_number": row[2],
                "topic": row[3],
                "zone_codes": row[4],
                "distance": row[5],
            }
            for row in rows
        ]

    async def interpret_regulations(
        self,
        parcel: ParcelSchema,
        building_type: str,
        existing_constraints: list[ConstraintSchema],
    ) -> list[ConstraintSchema]:
        """Use RAG + LLM to find additional constraints not in structured rules."""
        query = (
            f"zoning regulations for {parcel.zone_class} zone "
            f"{building_type} building type "
            f"setbacks height FAR density parking use restrictions"
        )

        chunks = await self.retrieve_relevant_chunks(
            query=query,
            zone_codes=[parcel.zone_class],
            limit=8,
        )

        if not chunks:
            logger.info("Layer 3: No relevant regulatory chunks found")
            return []

        logger.info(f"Layer 3: Retrieved {len(chunks)} chunks (nearest distance: {chunks[0]['distance']:.4f})")

        regulatory_text = "\n\n".join(
            f"[Section {c['section_number']}]: {c['text']}" for c in chunks
        )

        existing_summary = "\n".join(
            f"- {c.parameter}: {c.value} ({c.determination_type})"
            for c in existing_constraints
        )

        user_message = ASSESSMENT_USER_TEMPLATE.format(
            address=parcel.address or "N/A",
            zone_code=parcel.zone_code,
            zone_class=parcel.zone_class,
            height_district=parcel.height_district or "1",
            lot_area=f"{parcel.lot_area_sqft:,.0f}" if parcel.lot_area_sqft else "N/A",
            building_type=building_type,
            specific_plan=parcel.specific_plan or "None",
            overlays=", ".join(parcel.overlay_zones) if parcel.overlay_zones else "None",
            existing_constraints=existing_summary,
            regulatory_text=regulatory_text,
        )

        try:
            response = await self.llm.complete(
                messages=[
                    {"role": "system", "content": ASSESSMENT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )

            parsed = json.loads(response)
            if isinstance(parsed, dict):
                parsed = parsed.get("constraints", parsed.get("additional_constraints", []))
            if not isinstance(parsed, list):
                parsed = []

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Layer 3 LLM interpretation failed: {e}")
            return []

        constraints = []
        for item in parsed:
            confidence = self._safe_float(item.get("confidence")) or 0.7
            if confidence < 0.5:
                continue

            citation = CitationSchema(
                section_number=item.get("section_number", ""),
                section_title=f"LAMC Sec. {item.get('section_number', 'N/A')}",
                relevant_text=item.get("citation_text", item.get("reasoning", "")),
            )

            constraint = ConstraintSchema(
                category=item.get("category", "other"),
                parameter=item.get("parameter", "unknown"),
                rule_text=item.get("rule_text", ""),
                value=item.get("value"),
                numeric_value=self._safe_float(item.get("value")),
                unit=item.get("unit"),
                confidence=confidence,
                source_layer="llm_interpreted",
                determination_type="interpreted",
                citations=[citation],
                reasoning=item.get("reasoning", ""),
            )
            constraints.append(constraint)

        logger.info(f"Layer 3: Found {len(constraints)} interpreted constraints")
        return constraints

    def _safe_float(self, val) -> float | None:
        if val is None:
            return None
        try:
            cleaned = "".join(c for c in str(val) if c.isdigit() or c == ".")
            return float(cleaned) if cleaned else None
        except (ValueError, TypeError):
            return None
