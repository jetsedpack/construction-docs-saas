"""Draft construction-document taxonomy for the F01 per-file dropdown.

Product catalog will be versioned in the protected box. The selected type
determines a local parser profile; it is NEVER permission to transmit data.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentType:
    code: str
    label: str


DOCUMENT_TYPES: tuple[DocumentType, ...] = tuple(
    DocumentType(code, label)
    for code, label in (
        ("working_drawing", "Рабочий чертёж"),
        ("working_documentation", "Комплект рабочей документации"),
        ("technical_assignment", "Техническое задание"),
        ("technical_conditions", "Технические условия"),
        ("technical_specification", "Спецификация оборудования"),
        ("bill_of_quantities", "Ведомость объёмов работ"),
        ("estimate", "Смета / ССР"),
        ("change_register", "Ведомость изменений и отступлений"),
        ("construction_log", "Общий журнал работ"),
        ("special_works_log", "Специальный журнал работ"),
        ("input_inspection_log", "Журнал входного контроля"),
        ("hidden_works_act", "АОСР / скрытые работы"),
        ("executive_survey", "Исполнительная схема"),
        ("equipment_passport", "Паспорт оборудования"),
        ("quality_certificate", "Сертификат / паспорт качества"),
        ("material_batch", "Документ партии материала"),
        ("inspection_act", "Акт контроля / приёмки"),
        ("electrical_installation_act", "Акт электромонтажа"),
        ("p_nr_protocol", "Протокол ПНР"),
        ("equipment_config_archive", "Архив конфигурации"),
        ("id_register", "Реестр исполнительной документации"),
        ("contract", "Договор / приложение"),
        ("order", "Приказ / распоряжение"),
        ("other", "Иное / требуется уточнение"),
    )
)
BY_CODE: dict[str, DocumentType] = {entry.code: entry for entry in DOCUMENT_TYPES}


def require_type(code: str) -> DocumentType:
    """Fail closed for unknown or intentionally non-classifying type selections."""
    if not isinstance(code, str) or code not in BY_CODE or code == "other":
        raise ValueError("Необходимо выбрать поддерживаемый тип документа")
    return BY_CODE[code]
