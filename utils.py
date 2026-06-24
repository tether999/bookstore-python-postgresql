from PyQt6.QtWidgets import QMessageBox, QTableWidgetItem


def message(parent, title, text):
    QMessageBox.information(parent, title, text)


def error(parent, text):
    QMessageBox.warning(parent, 'Ошибка', text)


def fill_table(table, headers, rows):
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        vals = list(row.values())
        for c in range(len(headers)):
            table.setItem(r, c, QTableWidgetItem(str(vals[c]) if c < len(vals) and vals[c] is not None else ''))
    table.resizeColumnsToContents()
