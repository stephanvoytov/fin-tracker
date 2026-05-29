import csv
import io
import sys

import sqlite3

from PyQt6 import uic
from PyQt6.QtCore import QDate, QTime, QRectF, QTimer, QDateTime
from PyQt6.QtGui import QBrush, QColor, QFont, QPixmap, QIcon
from PyQt6.QtWidgets import QMainWindow, QApplication, QTableWidgetItem, QDialog, QGraphicsScene, \
    QGraphicsTextItem, QMessageBox, QFileDialog


class AddTransactWidget(QDialog):
    def __init__(self, parent, conn, r_id=-1, is_expense=False):
        super().__init__(parent)
        self.file_path = None
        uic.loadUi('ui/AddTransactionWidget.ui', self)

        self.expenses = [el[0] for el in conn.cursor().execute('select name from expenses').fetchall()]
        self.incomes = [el[0] for el in conn.cursor().execute('select name from incomes').fetchall()]

        if r_id == -1:
            self.dateTimeEdit.setDate(QDate.currentDate())
            self.dateTimeEdit.setTime(QTime.currentTime())
            if is_expense:
                self.comboBox.addItems(self.expenses)
            else:
                self.comboBox.addItems(self.incomes)
        else:
            sql = f'''select amount, date, case when is_expense = 0 then incomes_id else expenses_id end as category_id, description, image_path, is_expense from transactions
            where id = ?'''
            data = conn.cursor().execute(sql, (r_id,)).fetchall()
            data = data[0]
            self.amount.setText(str(data[0]))

            date, time = data[1].split()
            date = QDate.fromString(date, 'yyyy.MM.dd')
            time = QTime.fromString(time, 'hh:mm')

            self.dateTimeEdit.setDate(date)
            self.dateTimeEdit.setTime(time)
            self.comboBox.setCurrentIndex(data[2])
            self.description.setText(data[3])
            self.file_path = data[4]
            self.show_image()

            is_expense = True if data[5] == 1 else False

            if is_expense:
                self.comboBox.addItems(self.expenses)
            else:
                self.comboBox.addItems(self.incomes)

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.dateTimeEdit.setDisplayFormat("yyyy.MM.dd hh:mm")
        self.addImage.clicked.connect(self.load_image)
        self.deleteImg.clicked.connect(self.delete_image)

    def show_image(self):
        try:
            pixmap = QPixmap(self.file_path).scaled(50, 50)
            self.image_loaded.setPixmap(pixmap)
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'{e}')

    def delete_image(self):
        self.file_path = None
        self.image_loaded.clear()

    def load_image(self):
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilter('Images (*.png *.jpg *.jpeg *.bmp *.gif)')
        self.file_path, _ = file_dialog.getOpenFileName(self, "Выберите изображение")
        self.show_image()

    def get_input(self):
        return [self.amount.text(), self.dateTimeEdit.text(), self.comboBox.currentText(), self.description.text(),
                self.file_path]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.timer = QTimer(self)
        uic.loadUi('ui/MainWindow.ui', self)

        self.countclicks = 0
        self.scene = QGraphicsScene(self)
        self.connection = sqlite3.connect("db.sqlite")
        self.expenses = [el[0] for el in self.connection.cursor().execute('select name from expenses').fetchall()]
        self.incomes = [el[0] for el in self.connection.cursor().execute('select name from incomes').fetchall()]
        self.initUi()

    def initUi(self):
        self.view.setScene(self.scene)

        self.buttonGroup.setId(self.weekBtn, 0)
        self.buttonGroup.setId(self.monthBtn, 1)
        self.buttonGroup.setId(self.yearBtn, 2)
        self.buttonGroup_graphic.setId(self.expenseRadioBtn, 0)
        self.buttonGroup_graphic.setId(self.incomeRadioBtn, 1)
        self.monthBtn.setChecked(True)
        self.expenseRadioBtn.setChecked(True)
        self.buttonGroup.buttonToggled.connect(self.graphic_expenses)
        self.buttonGroup_graphic.buttonToggled.connect(self.graphic_expenses)
        self.refreshBtn.clicked.connect(self.refresh)
        self.leftBtn.setEnabled(False)
        self.leftBtn.clicked.connect(self.countClicks)
        self.rightBtn.clicked.connect(self.countClicks)
        self.deleteBtn.clicked.connect(self.deleteTran)
        self.addExpenseBtn.clicked.connect(self.addExpense)
        self.addIncomeBtn.clicked.connect(self.addIncome)
        self.saveBtn.clicked.connect(self.save_to_csv)
        self.editBtn.clicked.connect(self.update_data)

        self.timer.timeout.connect(self.update_date_time)
        self.timer.start(1000)

        self.refresh()

    def update_data(self):
        selected_row = self.tableWidget.currentRow()
        if selected_row != -1:
            try:
                r_id = self.tableWidget.item(selected_row, 4).text()

                widget = AddTransactWidget(self, self.connection, r_id=r_id)
                if widget.exec() == 1:
                    values = widget.get_input()
                    if int(values[0]) <= 0:
                        raise ValueError
                    is_expense = \
                        self.connection.cursor().execute('select is_expense from transactions where id = ?',
                                                         (r_id,)).fetchall()[0][0]
                    if is_expense == '0':
                        sql = (
                            'update transactions set amount = ?, date = ?, incomes_id = (SELECT id FROM incomes WHERE name = ?), description = ?, image_path = ? '
                            'where id = ?')
                    else:
                        sql = (
                            'update transactions set amount = ?, date = ?, expenses_id = (SELECT id FROM expenses WHERE name = ?), description = ?, image_path = ? '
                            f'where id = {r_id}')
                    self.connection.cursor().execute(sql, values)
            except Exception as e:
                self.error(f"Не удалось изменить: {str(e)}")
            else:
                self.connection.commit()
                self.refresh()
        else:
            QMessageBox.warning(self, "Ошибка", "Пожалуйста, выберите запись для изменения.")
            return

    def save_to_csv(self):
        file_name, _ = QFileDialog.getSaveFileName(self, "Сохранить файл", "", "CSV Files (*.csv);;All Files (*)")

        if file_name:
            with open(file_name, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                for row in range(self.tableWidget.rowCount()):
                    row_data = []
                    for col in range(self.tableWidget.columnCount()):
                        item = self.tableWidget.item(row, col)
                        row_data.append(item.text() if item else "")

                    writer.writerow(row_data)
            print("Данные сохранены в", file_name)

    def deleteTran(self):
        selected_row = self.tableWidget.currentRow()
        try:
            if selected_row == -1:
                QMessageBox.warning(self, "Ошибка", "Пожалуйста, выберите запись для удаления.")
                return

            item = self.tableWidget.item(selected_row, 4)
            record_id = item.text()
            cursor = self.connection.cursor()
            sql = "select amount, date from transactions where id = ?"
            a = cursor.execute(sql, (record_id,)).fetchall()
            amount, date = a[0]

            reply = QMessageBox.question(self, 'Подтверждение удаления',
                                         f"Вы действительно хотите удалить транзакцию ID: {record_id}; сумма: {amount}; дата: {date}",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes:
                cursor.execute("DELETE FROM transactions WHERE id = ?", (record_id,))
                self.connection.commit()

                self.tableWidget.removeRow(selected_row)

                QMessageBox.information(self, "Успех", f"Запись с ID {record_id} удалена.")
                self.refresh()
        except Exception as e:
            self.error(f"Не удалось удалить запись: {str(e)}")

    def update_date_time(self):
        date_time = QDateTime.currentDateTime()
        date = date_time.toString("d MMMM yyyy")
        time = date_time.toString("HH:mm:ss")
        self.time.setText(time)
        self.date.setText(date)

    def countClicks(self):
        if self.sender().text() == '>':
            self.countclicks += 1
            if self.countclicks == 1:
                self.leftBtn.setEnabled(True)
        else:
            self.countclicks -= 1
            if self.countclicks == 0:
                self.leftBtn.setEnabled(False)
        self.refresh_graph()

    def balance(self):
        sql = 'select SUM(amount) from transactions where is_expense = 1'
        sql1 = 'select SUM(amount) from transactions where is_expense = 0'

        expense_sum = self.connection.cursor().execute(sql).fetchall()[0][0]
        if not expense_sum:
            expense_sum = 0
        income_sum = self.connection.cursor().execute(sql1).fetchall()[0][0]
        if not income_sum:
            income_sum = 0
        summ = -int(expense_sum) + int(income_sum)
        self.balanceLabel.setText(f"{str(summ)} ₽")
        if summ < 0:
            self.balanceLabel.setStyleSheet('color: rgb(100, 0, 0)')
        else:
            self.balanceLabel.setStyleSheet('color: rgb(0, 100, 0)')

    def amount_expenses(self, date, date1, is_expense):
        sql = f'''select SUM(amount) from transactions where is_expense = {1 if is_expense else 0} and date >= "{date}" and date <= "{date1}"'''

        expense_sum = self.connection.cursor().execute(sql).fetchall()[0][0]
        if not expense_sum:
            expense_sum = 0
        summ = int(expense_sum)
        self.amountExpenses.setText(f"{str(summ)} ₽")

    def select_data(self):
        query = '''SELECT 
            t.amount, 
            t.date, 
            CASE 
                WHEN t.is_expense = 1 THEN e.name
                ELSE i.name
            END AS category_name, 
            t.description,
            t.id,
            t.image_path
        FROM 
            transactions t
        LEFT JOIN 
            expenses e ON t.expenses_id = e.id
        LEFT JOIN 
            incomes i ON t.incomes_id = i.id
        ORDER BY 
            t.date DESC;'''

        res = self.connection.cursor().execute(query).fetchall()

        self.tableWidget.setColumnCount(5)
        self.tableWidget.setRowCount(len(res))

        expense_color = QColor(100, 0, 0)
        income_color = QColor(0, 100, 0)

        for i, row in enumerate(res):
            expense = row[2] not in self.incomes
            image_path = row[5]

            for j, elem in enumerate(row[:-1]):
                item = QTableWidgetItem(str(elem))

                if j == 0:
                    if expense:
                        elem = f"-{elem}"
                        item.setForeground(expense_color)
                    else:
                        elem = f"+{elem}"
                        item.setForeground(income_color)
                    item.setText(str(elem))

                elif j == 1:
                    item.setText(str(elem))

                self.tableWidget.setItem(i, j, item)

            if image_path:
                pixmap = QPixmap(image_path)
                if not pixmap.isNull():
                    icon = QIcon(pixmap)
                    self.tableWidget.item(i, 0).setIcon(icon)

        self.tableWidget.setColumnWidth(0, 90)
        self.tableWidget.setColumnWidth(1, 130)
        self.tableWidget.setColumnWidth(2, 150)
        self.tableWidget.setColumnWidth(3, 130)

        self.refresh_graph()

    def addExpense(self):
        widget = AddTransactWidget(self, self.connection, is_expense=True)
        if widget.exec() == 1:
            values = widget.get_input()
            image_path = values[-1]
            try:
                if int(values[0]) <= 0:
                    raise ValueError
                if image_path:
                    with open(image_path, 'rb') as file:
                        img_data = file.read()

                    sql = """INSERT INTO transactions (date, amount, expenses_id, description, is_expense, image_path, image_data)
                                    VALUES (?, ?, (SELECT id FROM expenses WHERE name = ?), ?, ?, ?, ?)"""
                    cursor = self.connection.cursor()
                    cursor.execute(sql, (values[1], values[0], values[2], values[3], 1, image_path, img_data))
                    self.connection.commit()

                else:
                    sql = """INSERT INTO transactions (date, amount, expenses_id, description, is_expense)
                                    VALUES (?, ?, (SELECT id FROM expenses WHERE name = ?), ?, ?)"""
                    cursor = self.connection.cursor()
                    cursor.execute(sql, (values[1], values[0], values[2], values[3], 1))
                    self.connection.commit()

            except ValueError:
                self.error(f"Не удалось записать данные: неправильная сумма")
            except Exception as e:
                self.error(f"Не удалось записать данные: {str(e)}")
            else:
                self.connection.commit()
                self.refresh()

    def addIncome(self):
        widget = AddTransactWidget(self, self.connection, is_expense=False)
        if widget.exec() == 1:
            values = widget.get_input()
            image_path = values[-1]
            try:
                if int(values[0]) <= 0:
                    raise ValueError
                if image_path:
                    with open(image_path, 'rb') as file:
                        img_data = file.read()

                    sql = """INSERT INTO transactions (date, amount, incomes_id, description, is_expense, image_path, image_data)
                                                VALUES (?, ?, (SELECT id FROM incomes WHERE name = ?), ?, ?, ?, ?)"""
                    cursor = self.connection.cursor()
                    cursor.execute(sql, (values[1], values[0], values[2], values[3], 0, image_path, img_data))
                    self.connection.commit()

                else:
                    sql = """INSERT INTO transactions (date, amount, incomes_id, description, is_expense)
                                                VALUES (?, ?, (SELECT id $10))
                    self.connection.commit()
            except ValueError:
                self.error(f"Не удалось записать данные: неправильная сумма")
            except Exception as e:
                self.error(f'Ошибка: {e}')
            else:
                self.connection.commit()
                self.refresh()

    def graphic_expenses(self):
        cursor = self.connection.cursor()
        b_id = self.buttonGroup.checkedId()
        is_expense = True if self.buttonGroup_graphic.checkedId() == 0 else False

        dates = [QDate.currentDate().addDays(-QDate.currentDate().dayOfWeek() - 7 * self.countclicks),
                 QDate.currentDate().addDays(-QDate.currentDate().day() + 1).addMonths(-self.countclicks),
                 QDate.currentDate().addDays(-QDate.currentDate().day() + 1).addMonths(
                     -QDate.currentDate().month() + 1).addYears(-self.countclicks)]
        dates1 = [dates[0].addDays(7), dates[1].addMonths(1), dates[2].addYears(1)]

        date1 = dates1[b_id].toString("yyyy.MM.dd")
        date = dates[b_id].toString("yyyy.MM.dd")

        self.first_date.setText(f"от {dates[b_id].toString("d MMM yyyy")}")
        self.last_date.setText(f"до {dates1[b_id].toString("d MMM yyyy")}")
        if is_expense:
            query = f"""SELECT e.name, SUM(amount) AS total_amount
                        FROM transactions t
                        JOIN expenses e ON t.expenses_id = e.id
                        WHERE date >= "{date}" and date <= "{date1}" and is_expense = 1
                        GROUP BY e.name
                        ORDER BY total_amount DESC
                        LIMIT 5;
                    """
        else:
            query = f"""SELECT i.name, SUM(amount) AS total_amount
                        FROM transactions t
                        JOIN incomes i ON t.incomes_id = i.id
                        WHERE date >= "{date}" and date <= "{date1}" and is_expense = 0
                        GROUP BY i.name
                        ORDER BY total_amount DESC
                        LIMIT 5;
                    """
        self.amount_expenses(date, date1, is_expense)
        self.select_graphics_transactions(date, date1, is_expense)
        a = cursor.execute(query).fetchall()
        self.scene.clear()
        if not a:
            text_item = QGraphicsTextItem("В этом промежутке не было расходов")
            text_item.setFont(QFont('Arial', 18))
            text_item.setTextWidth(150)
            text_item.setPos(0, 50)
            self.scene.addItem(text_item)
        else:
            categories = []
            amounts = []
            for row in a:
                categories.append(row[0])
                amounts.append(row[1])

            max_amount = max(amounts) if amounts else 1

            bar_width = 70
            spacing = 15

            max_bar_height = 170
            colors = [[54, 162, 235],
                      [255, 99, 132],
                      [75, 192, 192],
                      [153, 102, 255],
                      [255, 159, 64]]
            for index, (category, amount) in enumerate(zip(categories, amounts)):
                bar_height = (amount / max_amount) * max_bar_height

                self.scene.addRect(
                    index * (bar_width + spacing),
                    max_bar_height - bar_height,
                    bar_width,
                    bar_height,
                    brush=QBrush(QColor(*colors[index]))
                )

                text_item = QGraphicsTextItem(category)
                text_item.setFont(QFont('Arial', 10))
                text_item.setTextWidth(bar_width)
                text_item.setPos(index * (bar_width + spacing), max_bar_height + 5)

                amount_text_item = QGraphicsTextItem(f"{amount:.2f}")
                amount_text_item.setFont(QFont('Arial', 10))
                amount_text_item.setPos(
                    index * (bar_width + spacing) + (bar_width // 2) - (amount_text_item.boundingRect().width() / 2),
                    max_bar_height - bar_height - 20)
                self.scene.addItem(amount_text_item)

                self.scene.addItem(text_item)

            self.scene.setSceneRect(QRectF(0, 0, len(categories) * (bar_width + spacing), max_bar_height + 50))

    def select_graphics_transactions(self, date, date1, is_expense):
        if is_expense:
            query = f'''SELECT t.amount, t.date, e.name, t.description, t.id, t.image_path 
            FROM transactions t
                LEFT JOIN 
                    expenses e ON t.expenses_id = e.id
                    WHERE date >= "{date}" and date <= "{date1}" and is_expense = 1
                ORDER BY 
                    t.date DESC;'''
        else:
            query = f'''SELECT t.amount, t.date, i.name, t.description, t.id , t.image_path
                FROM transactions t
                LEFT JOIN 
                    incomes i ON t.incomes_id = i.id
                    WHERE date >= "{date}" and date <= "{date1}" and is_expense = 0
                ORDER BY 
                    t.date DESC;'''

        res = self.connection.cursor().execute(query).fetchall()
        self.tableWidget2.setColumnCount(5)
        self.tableWidget2.setRowCount(len(res))

        expense_color = QColor(100, 0, 0)
        income_color = QColor(0, 100, 0)

        for i, row in enumerate(res):
            expense = row[2] not in self.incomes
            image_path = row[5]

            for j, elem in enumerate(row[:-1]):
                item = QTableWidgetItem(str(elem))

                if j == 0:
                    if expense:
                        elem = f"-{elem}"
                        item.setForeground(expense_color)
                    else:
                        elem = f"+{elem}"
                        item.setForeground(income_color)
                    item.setText(str(elem))

                elif j == 1:
                    item.setText(str(elem))

                self.tableWidget2.setItem(i, j, item)

            if image_path:
                pixmap = QPixmap(image_path)
                if not pixmap.isNull():
                    icon = QIcon(pixmap)
                    self.tableWidget2.item(i, 0).setIcon(icon)

        self.tableWidget2.setColumnWidth(0, 90)
        self.tableWidget2.setColumnWidth(1, 130)
        self.tableWidget2.setColumnWidth(2, 150)
        self.tableWidget2.setColumnWidth(3, 130)

    def error(self, error):
        QMessageBox.critical(self, 'Ошибка', error)

    def refresh_graph(self):
        self.graphic_expenses()

    def refresh(self):
        self.graphic_expenses()
        self.select_data()
        self.balance()

    def closeEvent(self, event):
        self.connection.close()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MainWindow()
    ex.show()
    sys.exit(app.exec())
