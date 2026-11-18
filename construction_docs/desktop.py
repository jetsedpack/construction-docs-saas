"""Windows-only PySide6 desktop preview.

No background synchronization. AI requests require showing outbound payload and
explicit approval. This is not a production signed installer.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

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
        QApplication, QHBoxLayout, QInputDialog, QLabel, QMainWindow, QMessageBox,
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
            self.doc_table = QTableWidget(0, 4)
            self.doc_table.setHorizontalHeaderLabels(["Имя документа", "Формат", "Импортирован", "Предупреждения"])
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
                for col, text in enumerate([
                    item.name, item.kind, item.imported_at[:19],
                    "; ".join(item.warnings) or "—",
                ]):
                    self.doc_table.setItem(row, col, QTableWidgetItem(str(text)))
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
                self, "Загрузить документ", str(Path.home()),
                "Документы (*.pdf *.docx *.xlsx *.csv)",
            )
            if not filename:
                return
            try:
                document = self.vault.import_file(filename)
                self.refresh_docs()
                self.output.setPlainText(
                    f"Локально импортировано: {document.name}\n"
                    + "\n".join(document.warnings)
                )
                self.statusBar().showMessage("Файл локально сохранён в шифрованном vault")
            except Exception as exc:
                QMessageBox.warning(self, "Ошибка импорта", str(exc))

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
