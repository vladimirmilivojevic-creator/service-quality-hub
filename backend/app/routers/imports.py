"""CSV import of Jira Service Management exports: preview first, then import."""

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.config import settings
from app.deps import DB, ManagerUser
from app.importers import jsm
from app.schemas import ImportPreview, ImportPreviewRow, ImportResult
from app.services import load_catalogue

router = APIRouter(prefix="/imports/jsm", tags=["imports"])

PREVIEW_ROWS = 20
TIMEZONE = Query("Europe/Vienna", description="Time zone of the dates in the export (the exporting user's zone)")


async def _read(file: UploadFile) -> bytes:
    limit = settings.max_upload_mb * 1024 * 1024
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(413, f"The file is larger than {settings.max_upload_mb} MB")
    return content


async def _map(db: DB, file: UploadFile, timezone: str) -> jsm.MappingResult:
    try:
        frame = jsm.read_csv(await _read(file))
        if len(frame) > settings.max_import_rows:
            raise HTTPException(413, f"The file has more than {settings.max_import_rows} rows")
        return jsm.map_rows(frame, await load_catalogue(db), timezone)
    except jsm.ImportFileError as error:
        raise HTTPException(422, str(error)) from error


@router.post("/preview", response_model=ImportPreview)
async def preview(
    db: DB, _: ManagerUser, file: Annotated[UploadFile, File()], timezone: str = TIMEZONE
) -> ImportPreview:
    result = await _map(db, file, timezone)
    catalogue = await load_catalogue(db)
    return ImportPreview(
        total_rows=result.total_rows,
        valid_rows=len(result.rows),
        detected=result.detected,
        rows=[
            ImportPreviewRow(
                row=r.row,
                key=r.key,
                type=r.type,
                plant_code=catalogue.plants[r.plant_id].code,
                service_name=catalogue.services[r.service_id].name,
                priority=r.priority,
                status=r.status,
                created_at=r.created_at,
                resolved_at=r.resolved_at,
                title=r.title,
            )
            for r in result.rows[:PREVIEW_ROWS]
        ],
        skipped=result.skipped,
        warnings=result.warnings,
    )


@router.post("", response_model=ImportResult)
async def import_file(
    db: DB, _: ManagerUser, file: Annotated[UploadFile, File()], timezone: str = TIMEZONE
) -> ImportResult:
    result = await _map(db, file, timezone)
    created, updated = await jsm.upsert(db, result.rows, await load_catalogue(db))
    return ImportResult(created=created, updated=updated, skipped=result.skipped, warnings=result.warnings)
