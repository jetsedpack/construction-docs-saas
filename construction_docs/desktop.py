"""Windows-only PySide6 desktop preview.

No background synchronization. AI requests require showing outbound payload and
explicit approval. This is not a production signed installer.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .batch import discover_files
from .document_types import DOCUMENT_TYPES
from .gateway import GPUGOGateway, GatewayError, safe_batch
from .models import Issue
from .rules import check_register
from .vault import EncryptedVault


def main() -> int:
    if sys.platform != "win32":
        print("Windows 10/11 x64 only. Unit tests are cross-platform.")
        return 2

    from PySide6.QtCore import QThread, Signal
    from PySide6.QtWidgets import (
        QApplication, QComboBox, QHBoxLayout, QInputDialog, QLabel, QMainWindow, QMessageBox,
        QFileDialog, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
        QTextEdit, QVBoxLayout, QWidget,
    )

    class AIWorker(QThread):
        result = Signal(object)
        failed = Signal(str)

        def __init__(self, findings: list[Issue]):
            super().__init__()
            self.findings = findings

        def run(self):
            try:
                advice = GPUGOGateway().explain(self.findings)
                self.result.emit(advice)
            except Exception as exc:
                # Do not include tokens or request bodies in user-facing errors.
                self.failed.emit(str(exc) if isinstance(exc, GatewayError) else "Ошибка при запросе AI")

    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Construction Docs | ПТО · локальный PoC")
            self.resize(1220, 790)
            self.vault = EncryptedVault()
            self.docs: list = []
            self.current_issues: list[Issue] = []
            self.worker: AIWorker | None = None

            container = QWidget()
            layout = QVBoxLayout(container)
            title = QLabel("Исполнительная документация · Windows / защищённый локальный прототип")
            title.setStyleSheet("font-size: 18px; font-weight: 600; padding: 12px;")
            layout.addWidget(title)
            buttons = QHBoxLayout()
            for caption, fn in [
                ("Загрузить всю папку", self.import_batch),
                ("Импорт файла", self.import_document),
                ("Проверить реестр", self.check_selected),
                ("AI: показать обезличенный запрос", self.ask_ai),
                ("Отметить замечание рассмотренным", self.review_selected),
                ("История", self.show_events),
            ]:
                btn = QPushButton(caption)
                btn.clicked.connect(fn)
                buttons.addWidget(btn)
            layout.addLayout(buttons)

            splitter = QSplitter()
            self.doc_table = QTableWidget(0, 5)
            self.doc_table.setHorizontalHeaderLabels(["Файл", "Формат", "Тип (выбирает инженер)", "Статус", "Импортирован"])
            self.doc_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            self.doc_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            self.doc_table.itemSelectionChanged.connect(self.display_selected)
            splitter.addWidget(self.doc_table)

            right = QWidget()
            right_layout = QVBoxLayout(right)
            right_layout.addWidget(QLabel("Замечания / предмет проверки (не юридическое заключение)"))
            self.issue_table = QTableWidget(0, 4)
            self.issue_table.setHorizontalHeaderLabels(["Важность", "Тип", "Строка", "Пояснение"])
            self.issue_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            self.issue_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            right_layout.addWidget(self.issue_table)
            right_layout.addWidget(QLabel("Информация и история действий"))
            self.output = QTextEdit()
            self.output.setReadOnly(True)
            right_layout.addWidget(self.output)
            splitter.addWidget(right)
            splitter.setSizes([460, 760])
            layout.addWidget(splitter)
            self.setCentralWidget(container)
            self.statusBar().showMessage("Офлайн по умолчанию · исходные файлы не отправляются на GPUGO")
            self.refresh_docs()

        def refresh_docs(self):
            self.docs = self.vault.list_documents()
            self.doc_table.setRowCount(len(self.docs))
            for row, item in enumerate(self.docs):
                for col, value in (
                    (0, item.name), (1, item.kind),
                    (3, item.parse_status), (4, item.imported_at[:19]),
                ):
                    self.doc_table.setItem(row, col, QTableWidgetItem(str(value)))
                chooser = QComboBox()
                chooser.addItem("— Выберите тип документа —", "")
                for category in DOCUMENT_TYPES:
                    if category.code != "other":
                        chooser.addItem(category.label, category.code)
                idx = chooser.findData(item.doc_type)
                chooser.setCurrentIndex(max(idx, 0))
                chooser.currentIndexChanged.connect(
                    lambda _idx, document_id=item.id, widget=chooser:
                        self.classify_selected(document_id, widget.currentData())
                )
                self.doc_table.setCellWidget(row, 2, chooser)
            self.doc_table.resizeColumnsToContents()

        def selected(self):
            row = self.doc_table.currentRow()
            return self.docs[row] if 0 <= row < len(self.docs) else None

        def display_selected(self):
            doc = self.selected()
            if doc:
                self.current_issues = self.vault.get_findings(doc.id)
                self.display_issues()
                self.output.setPlainText(
                    f"Файл: {doc.name}\nРазмер: {doc.size} байт\n"
                    f"Таблиц/листов: {len(doc.tables)}\n"
                    "Файлы и извлечённый текст остаются локально зашифрованными.\n"
                    + "\n".join(doc.warnings)
                )

        def import_document(self):
            filename, _filter = QFileDialog.getOpenFileName(
                self, "Загрузить исходный файл", str(Path.home()), "Все файлы (*.*)",
            )
            if not filename:
                return
            try:
                document = self.vault.stage_file(filename)
                self.refresh_docs()
                self.output.setPlainText(
                    f"Защищённо сохранён оригинал: {document.name}\n"
                    "Выберите тип файла в третьем столбце.\n"
                    "До выбора типа локальный парсер и AI не запускаются."
                )
            except Exception as exc:
                QMessageBox.warning(self, "Ошибка импорта", str(exc))

        def import_batch(self):
            folder = QFileDialog.getExistingDirectory(
                self, "Выбрать папку со всей рабочей документацией", str(Path.home()),
            )
            if not folder:
                return
            try:
                manifest = discover_files(folder)
            except ValueError as exc:
                QMessageBox.warning(self, "Пакет не принят", str(exc))
                return
            accepted = 0
            errors: list[str] = []
            for entry in manifest:
                try:
                    self.vault.stage_file(entry.path)
                    accepted += 1
                except (OSError, ValueError) as exc:
                    errors.append(f"{entry.relative_path}: {exc}")
            self.refresh_docs()
            self.output.setPlainText(
                f"Пакет: {len(manifest)} файлов\n"
                f"В закрытый контур сохранено: {accepted}\n"
                f"Ошибок: {len(errors)}\n\n"
                "Для каждого файла выберите его тип отдельно.\n"
                + "\n".join(errors[:50])
            )
            self.statusBar().showMessage(
                f"Закрытый контур: {accepted} файлов. Сначала укажите тип КАЖДОГО."
            )

        def classify_selected(self, document_id: str, doc_type: str):
            if not doc_type:
                return
            try:
                document = self.vault.classify_document(document_id, doc_type)
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "Классификация не выполнена", str(exc))
                return
            self.refresh_docs()
            self.output.setPlainText(
                f"Тип выбран: {doc_type}\n"
                f"Локальный парсер: {document.parse_status}\n"
                + "\n".join(document.warnings)
                + "\nТип файла не разрешает передачу его содержимого на GPUGO."
            )

        def display_issues(self):
            self.issue_table.setRowCount(len(self.current_issues))
            for i, finding in enumerate(self.current_issues):
                for j, val in enumerate([
                    finding.severity, finding.category,
                    str(finding.source_row), finding.message,
                ]):
                    self.issue_table.setItem(i, j, QTableWidgetItem(val))
            self.issue_table.resizeColumnsToContents()

        def check_selected(self):
            doc = self.selected()
            if not doc:
                QMessageBox.information(self, "Выбор", "Выберите документ")
                return
            self.current_issues = check_register(doc)
            self.vault.save_findings(doc.id, self.current_issues)
            self.display_issues()
            self.statusBar().showMessage(
                f"Детерминированная проверка выполнена: {len(self.current_issues)} замечаний"
            )

        def review_selected(self):
            doc = self.selected()
            row = self.issue_table.currentRow()
            if not doc or row < 0 or row >= len(self.current_issues):
                QMessageBox.information(self, "Выбор", "Сначала выберите замечание")
                return
            decision, ok = QInputDialog.getItem(
                self, "Решение ПТО", "Результат рассмотрения:",
                ["Проверено / не нарушение", "Нужно исправить", "Недостаточно данных"], 0, False,
            )
            if ok:
                # A review event is NOT a signature, change to source, or accepted construction fact.
                issue = self.current_issues[row]
                self.vault.audit(
                    "review_recorded",
                    {"document_id": doc.id, "source_row": issue.source_row,
                     "category": issue.category, "decision": decision},
                )
                self.statusBar().showMessage("Решение зафиксировано в локальной истории")

        def ask_ai(self):
            if not self.current_issues:
                QMessageBox.information(self, "AI", "Сначала выполните локальную проверку реестра")
                return
            priority = {"high": 0, "review": 1, "info": 2}
            sample = sorted(self.current_issues, key=lambda item: priority[item.severity])[:10]
            try:
                gateway = GPUGOGateway()
                outgoing = safe_batch(sample)
            except GatewayError as exc:
                QMessageBox.information(self, "Офлайн", str(exc))
                return
            message = (
                "На GPUGO будут отправлены ТОЛЬКО следующие обезличенные данные:\n\n"
                + json.dumps(outgoing, ensure_ascii=False, indent=2)
                + f"\n\nEndpoint: {gateway.url}\n"
                + "\nОтправить?"
            )
            choice = QMessageBox.question(
                self, "Проверить отправку", message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return
            self.worker = AIWorker(sample)
            self.worker.result.connect(self.on_ai_result)
            self.worker.failed.connect(self.on_ai_error)
            self.worker.start()
            self.statusBar().showMessage("Ожидание рекомендации GPUGO; файлы не передаются")

        def on_ai_result(self, advice):
            self.output.setPlainText(
                "РЕКОМЕНДАЦИЯ ИИ (НЕ ПОДТВЕРЖДЁННЫЙ ФАКТ)\n"
                + json.dumps(advice, ensure_ascii=False, indent=2)
            )
            self.statusBar().showMessage("Ответ AI получен; оцените вручную")

        def on_ai_error(self, message):
            QMessageBox.warning(self, "AI недоступен", message)
            self.statusBar().showMessage("Сохранена офлайн-работа; данные не менялись")

        def show_events(self):
            events = self.vault.events()
            self.output.setPlainText(json.dumps(events[-100:], ensure_ascii=False, indent=2))

        def closeEvent(self, event):
            if self.worker and self.worker.isRunning():
                QMessageBox.information(self, "AI запрос", "Дождитесь завершения текущего запроса")
                event.ignore()
                return
            self.vault.close()
            event.accept()

    application = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
