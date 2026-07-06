"""Bidirectional mapping between domain entities and ORM rows."""

from __future__ import annotations

from app.domain.entities.chunk import Chunk
from app.domain.entities.document import Document
from app.domain.entities.document_status import DocumentStatus
from app.domain.value_objects.bibliographic_metadata import BibliographicMetadata
from app.domain.value_objects.language import Language
from app.domain.value_objects.pdf_source import PdfSource
from app.domain.value_objects.sha256_hash import Sha256Hash
from app.domain.value_objects.token_span import TokenSpan
from app.domain.value_objects.topic import Topic
from app.infrastructure.metadata.orm import ChunkModel, DocumentModel


def document_to_orm(document: Document) -> DocumentModel:
    return DocumentModel(
        id=document.id,
        tenant_id=document.tenant_id,
        source_filename=document.source.filename,
        source_path=document.source.path,
        source_pages=document.source.pages,
        source_mime=document.source.mime,
        source_size_bytes=document.source.size_bytes,
        content_hash=document.content_hash.hex,
        bib_title=document.bibliography.title,
        bib_authors=list(document.bibliography.authors),
        bib_institution=document.bibliography.institution,
        bib_faculty=document.bibliography.faculty,
        bib_career=document.bibliography.career,
        bib_year=document.bibliography.year,
        language_code=document.language.code if document.language else None,
        language_confidence=document.language.confidence if document.language else None,
        topic_domain=document.topic.domain if document.topic else None,
        topic_confidence=document.topic.confidence if document.topic else None,
        keywords=list(document.keywords),
        status=document.status.value,
        indexed_at=document.indexed_at,
    )


def orm_to_document(model: DocumentModel) -> Document:
    language = (
        Language(code=model.language_code, confidence=model.language_confidence)
        if model.language_code is not None
        else None
    )
    topic = (
        Topic(domain=model.topic_domain, confidence=model.topic_confidence)
        if model.topic_domain is not None
        else None
    )
    return Document(
        id=model.id,
        tenant_id=model.tenant_id,
        source=PdfSource(
            filename=model.source_filename,
            path=model.source_path,
            pages=model.source_pages,
            mime=model.source_mime,
            size_bytes=model.source_size_bytes,
        ),
        content_hash=Sha256Hash(hex=model.content_hash),
        bibliography=BibliographicMetadata(
            title=model.bib_title,
            authors=tuple(model.bib_authors or ()),
            institution=model.bib_institution,
            faculty=model.bib_faculty,
            career=model.bib_career,
            year=model.bib_year,
        ),
        language=language,
        topic=topic,
        keywords=tuple(model.keywords or ()),
        status=DocumentStatus(model.status),
        indexed_at=model.indexed_at,
    )


def chunk_to_orm(chunk: Chunk) -> ChunkModel:
    return ChunkModel(
        id=chunk.id,
        document_id=chunk.document_id,
        text=chunk.text,
        span_start=chunk.span.start,
        span_end=chunk.span.end,
        span_page=chunk.span.page,
        chunk_order=chunk.order,
    )


def orm_to_chunk(model: ChunkModel) -> Chunk:
    return Chunk(
        id=model.id,
        document_id=model.document_id,
        text=model.text,
        span=TokenSpan(start=model.span_start, end=model.span_end, page=model.span_page),
        order=model.chunk_order,
    )
