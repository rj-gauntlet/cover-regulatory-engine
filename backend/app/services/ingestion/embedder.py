import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.database import RawSource, ParsedRegulation, RegulatoryChunk, IngestionLog
from app.services.ingestion.scraper import scrape_all_sections
from app.services.ingestion.parser import parse_html_to_regulations
from app.services.llm.openai_provider import get_llm_service

logger = logging.getLogger(__name__)


def chunk_text(text: str, chunk_size: int = None, overlap: int = None) -> list[str]:
    """Split text into overlapping chunks at sentence boundaries."""
    chunk_size = chunk_size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap

    sentences = []
    current = ""
    for char in text:
        current += char
        if char in ".;:" and len(current.strip()) > 10:
            sentences.append(current.strip())
            current = ""
    if current.strip():
        sentences.append(current.strip())

    if not sentences:
        return [text] if text.strip() else []

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            words = current_chunk.split()
            overlap_words = words[-max(1, len(words) // 4):]
            current_chunk = " ".join(overlap_words) + " " + sentence
        else:
            current_chunk += (" " if current_chunk else "") + sentence

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


async def run_full_ingestion(db: AsyncSession) -> dict:
    """Run the complete ingestion pipeline: scrape → parse → chunk → embed."""
    llm = get_llm_service()
    stats = {"sections_scraped": 0, "regulations_parsed": 0, "chunks_created": 0}
    log_id = uuid.uuid4()

    log_entry = IngestionLog(
        id=log_id,
        action="initial_ingest",
        new_hash="",
        started_at=datetime.utcnow(),
    )
    db.add(log_entry)

    logger.info("Starting full ingestion pipeline...")

    scraped = await scrape_all_sections()
    stats["sections_scraped"] = len(scraped)

    for section_data in scraped:
        existing = await db.execute(
            select(RawSource).where(
                RawSource.source_url == section_data["url"],
                RawSource.content_hash == section_data["content_hash"],
            )
        )
        if existing.scalar_one_or_none():
            logger.info(f"Section {section_data['section_number']} unchanged, skipping")
            continue

        raw_source = RawSource(
            source_url=section_data["url"],
            content_hash=section_data["content_hash"],
            raw_content=section_data["raw_html"],
            content_type="html",
        )
        db.add(raw_source)
        await db.flush()

        regulations = parse_html_to_regulations(
            raw_html=section_data["raw_html"],
            section_number=section_data["section_number"],
            section_title=section_data["title"],
            article=section_data["article"],
            source_url=section_data["url"],
        )

        for reg_data in regulations:
            regulation = ParsedRegulation(
                raw_source_id=raw_source.id,
                section_number=reg_data["section_number"],
                section_title=reg_data["section_title"],
                article=reg_data["article"],
                chapter=reg_data["chapter"],
                zone_codes=reg_data["zone_codes"],
                topic=reg_data["topic"],
                body_text=reg_data["body_text"],
            )
            db.add(regulation)
            await db.flush()
            stats["regulations_parsed"] += 1

            text_chunks = chunk_text(reg_data["body_text"])

            if text_chunks:
                try:
                    embeddings = await llm.embed(text_chunks)
                except Exception as e:
                    logger.error(f"Embedding failed for section {reg_data['section_number']}: {e}")
                    embeddings = [None] * len(text_chunks)

                for idx, (chunk_text_str, embedding) in enumerate(zip(text_chunks, embeddings)):
                    chunk = RegulatoryChunk(
                        regulation_id=regulation.id,
                        chunk_index=idx,
                        chunk_text=chunk_text_str,
                        embedding=embedding,
                        zone_codes=reg_data["zone_codes"],
                        topic=reg_data["topic"],
                        section_number=reg_data["section_number"],
                    )
                    db.add(chunk)
                    stats["chunks_created"] += 1

    log_entry.new_hash = "full_ingestion"
    log_entry.chunks_created = stats["chunks_created"]
    log_entry.completed_at = datetime.utcnow()
    await db.commit()

    logger.info(f"Ingestion complete: {stats}")
    return stats
