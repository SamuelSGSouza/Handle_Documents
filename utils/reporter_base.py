from dataclasses import asdict, dataclass, field
from typing import Optional
from pathlib import Path

@dataclass
class Report:
    original_path: str
    path: str
    extension: str
    execution_time_seconds: float = 0.0
    result: str = "success"
    find_cols: list[str] = field(default_factory=list)
    warning: Optional[str] = None
    failure_reason: Optional[str] = None
    suggested_solution: Optional[str] = None

def failure(reason: str, solution: str, file_path:Path, original_path:Path) -> dict:
    if type(file_path) ==str:
        file_path = Path(file_path)

    if type(original_path) ==str:
        original_path = Path(original_path)

    return asdict(Report(
        original_path=str(original_path),
        path=str(file_path),
        extension=file_path.suffix,
        result="failure",
        failure_reason=reason,
        suggested_solution=solution,
    ))

def success(file_path:Path, original_path:Path, find_cols:list, execution_time_seconds:float, warning:str="") -> dict:
    if "CAMPO_1" in find_cols:
        warning +="\nNão foi possível identificar com precisão as colunas do arquivo."

    if type(file_path) ==str:
        file_path = Path(file_path)

    if type(original_path) ==str:
        original_path = Path(original_path)


    return asdict(Report(
        original_path=str(original_path),
        path=str(file_path),
        extension=file_path.suffix,
        result="success",
        find_cols=find_cols,
        execution_time_seconds=execution_time_seconds,
        warning=warning
    ))
