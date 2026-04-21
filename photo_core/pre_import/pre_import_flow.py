# photo_core/pre_import/pre_import_flow.py

from pathlib import Path
from datetime import date

from photo_core.pre_import.directory_templates import (
    resolve_directory_template,
    TemplateError,
)


class PreImportError(ValueError):
    """Raised when Pre-Import validation fails."""


def preview_destination(
    *,
    output_root: Path,
    template: str,
    title: str,
    shoot_date: date,
) -> Path:
    """
    Resolve and preview the final destination directory.

    - Does NOT create directories
    - Does NOT modify ctx
    - Safe to call repeatedly
    """
    try:
        relative = resolve_directory_template(
            template,
            title=title,
            shoot_date=shoot_date,
        )
    except TemplateError as e:
        raise PreImportError(str(e))

    return output_root / relative


def freeze_pre_import(
    ctx,
    *,
    resolved_destination: Path,
    input_files: list,
):
    """
    Finalize Pre-Import.

    This is the ONLY place ctx is mutated.
    """
    ctx.output_dir = resolved_destination
    ctx.input_files = tuple(input_files)
    ctx.freeze()
