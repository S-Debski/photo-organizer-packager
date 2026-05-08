# Role: Application module

# photo_core/pre_import/directory_templates.py

from datetime import date
import re

class TemplateError(ValueError):
    pass


_TOKEN_PATTERN = re.compile(r"\{([A-Za-z]+)\}")


def resolve_directory_template(
    template: str,
    *,
    title: str,
    shoot_date: date,
) -> str:
    if not template or not template.strip():
        raise TemplateError("Template cannot be empty")

    tokens = {
        "title": _sanitize(title),
        "YYYY": shoot_date.strftime("%Y"),
        "YY": shoot_date.strftime("%y"),
        "MM": shoot_date.strftime("%m"),
        "DD": shoot_date.strftime("%d"),
        "date": shoot_date.strftime("%Y-%m-%d"),
    }

    def replace(match: re.Match) -> str:
        key = match.group(1)
        if key not in tokens:
            raise TemplateError(f"Unknown token: {{{key}}}")
        return tokens[key]

    expanded = _TOKEN_PATTERN.sub(replace, template)
    expanded = _normalize(expanded)

    _validate_relative_path(expanded)

    return expanded


def _sanitize(value: str) -> str:
    """
    Make a string filesystem-safe but human-readable.
    """
    value = value.strip()
    value = re.sub(r"[<>:\"/\\|?*]", "-", value)
    value = re.sub(r"\s+", " ", value)
    return value


def _normalize(path: str) -> str:
    path = path.replace("\\", "/")
    path = re.sub(r"/+", "/", path)
    return path.strip("/")


def _validate_relative_path(path: str) -> None:
    if not path:
        raise TemplateError("Resolved path is empty")

    if path.startswith(("/", "\\")):
        raise TemplateError("Absolute paths are not allowed")

    if re.match(r"^[A-Za-z]:", path):
        raise TemplateError("Drive letters are not allowed")

    if ".." in path.split("/"):
        raise TemplateError("Path traversal is not allowed")
    