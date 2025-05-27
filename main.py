import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QTableWidget, QTableWidgetItem, QPushButton,
    QMessageBox, QTreeWidget, QTreeWidgetItem, QSplitter,
    QTabWidget, QLabel, QStatusBar, QAction, QMenuBar, QToolBar,
    QLineEdit, QComboBox, QFileDialog, QDialog, QFormLayout,
    QHeaderView, QInputDialog, QAbstractItemView, QFrame, QGroupBox, QMenu
)
from PyQt5.QtGui import QFont, QColor, QIcon, QSyntaxHighlighter, QTextCharFormat, QBrush
from PyQt5.QtCore import Qt, QRegExp, QTimer, pyqtSignal

from sql_processor import Database, sql_lexer, sql_parser


# ===== SQL语法高亮 =====
class SQLHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)

        # 关键字格式
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor(0, 0, 255))
        keyword_format.setFontWeight(QFont.Bold)

        # 字符串格式
        string_format = QTextCharFormat()
        string_format.setForeground(QColor(163, 21, 21))

        # 数字格式
        number_format = QTextCharFormat()
        number_format.setForeground(QColor(128, 0, 128))

        # 注释格式
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor(0, 128, 0))

        # 操作符格式
        operator_format = QTextCharFormat()
        operator_format.setForeground(QColor(128, 0, 0))

        # 函数格式
        function_format = QTextCharFormat()
        function_format.setForeground(QColor(139, 69, 19))
        function_format.setFontWeight(QFont.Bold)

        # 规则列表
        self.highlightingRules = []

        # 关键字规则
        keywords = [
            'SELECT', 'FROM', 'WHERE', 'CREATE', 'TABLE', 'INSERT', 'INTO',
            'VALUES', 'DELETE', 'UPDATE', 'SET', 'INT', 'VARCHAR', 'PRIMARY',
            'KEY', 'NOT', 'NULL', 'AND', 'OR', 'AS', 'DISTINCT', 'ORDER', 'BY',
            'ASC', 'DESC', 'LIKE', 'IN', 'BETWEEN', 'LIMIT', 'GROUP', 'HAVING',
            'UNIQUE', 'ALTER', 'ADD', 'DROP', 'INDEX', 'VIEW', 'JOIN', 'LEFT',
            'RIGHT', 'FULL', 'OUTER', 'INNER', 'ON', 'UNION', 'ALL', 'WITH',
            'EXISTS', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'IS', 'NULL', 'NOT',
            'DEFAULT', 'CHECK', 'REFERENCES', 'FOREIGN', 'PRIVILEGES', 'GRANT',
            'REVOKE', 'TRUNCATE', 'COMMENT', 'USE', 'DATABASE', 'SHOW', 'TABLES',
            'DESCRIBE', 'EXPLAIN', 'ANALYZE', 'OPTIMIZE', 'BACKUP', 'RESTORE'
        ]
        for keyword in keywords:
            pattern = QRegExp(rf'\b{keyword}\b', Qt.CaseInsensitive)
            self.highlightingRules.append((pattern, keyword_format))

        # 函数规则
        functions = [
            'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'CONCAT', 'SUBSTRING', 'LENGTH',
            'UPPER', 'LOWER', 'TRIM', 'REPLACE', 'ROUND', 'CEIL', 'FLOOR', 'NOW',
            'DATE', 'YEAR', 'MONTH', 'DAY', 'HOUR', 'MINUTE',            'SECOND', 'DATEDIFF', 'TIMESTAMPDIFF', 'IFNULL', 'COALESCE', 'NULLIF',
            'IF', 'CASE', 'EXTRACT', 'CAST', 'CONVERT', 'GROUP_CONCAT', 'RAND',
            'SHA1', 'MD5', 'LEFT', 'RIGHT', 'POSITION', 'FORMAT', 'STR_TO_DATE',
            'DATE_FORMAT', 'CURRENT_DATE', 'CURRENT_TIME', 'CURRENT_TIMESTAMP'
        ]
        for function in functions:
            pattern = QRegExp(rf'\b{function}\b', Qt.CaseInsensitive)
            self.highlightingRules.append((pattern, function_format))

        # 字符串规则
        string_pattern = QRegExp(r'(\'[^\']*\'|\"[^\"]*\")')
        self.highlightingRules.append((string_pattern, string_format))

        # 数字规则
        number_pattern = QRegExp(r'\b\d+\b')
        self.highlightingRules.append((number_pattern, number_format))

        # 注释规则
        comment_pattern = QRegExp(r'--[^\n]*')
        self.highlightingRules.append((comment_pattern, comment_format))

        # 新增多行注释格式（复用comment_format）
        self.multi_line_comment_format = comment_format

        # 多行注释正则表达式模式
        self.comment_start = QRegExp(r"/\*")
        self.comment_end = QRegExp(r"\*/")

        # 操作符规则
        operators = ['=', '<>', '!=', '<', '<=', '=<', '>', '>=', '=>', '+', '-', '*', '/', ',', '(', ')', ';', '.', '[', ']', '%', '|', '&', '^', '~', '<<', '>>']
        for operator in operators:
            pattern = QRegExp(rf'\{operator}')
            self.highlightingRules.append((pattern, operator_format))

    def highlightBlock(self, text):
        for pattern, format in self.highlightingRules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)

        # 处理多行注释
        self.setCurrentBlockState(0)

        start_index = 0
        if self.previousBlockState() != 1:
            start_index = self.comment_start.indexIn(text)

        while start_index >= 0:
            end_index = self.comment_end.indexIn(text, start_index)
            if end_index == -1:  # 注释跨越多行
                comment_length = len(text) - start_index
                self.setCurrentBlockState(1)
                self.setFormat(start_index, comment_length, self.multi_line_comment_format)
                break
            else:  # 完整注释块
                comment_length = end_index - start_index + self.comment_end.matchedLength()
                self.setFormat(start_index, comment_length, self.multi_line_comment_format)
                start_index = self.comment_start.indexIn(text, start_index + comment_length)


# ===== 表数据编辑对话框 =====
class EditTableDialog(QDialog):
    def __init__(self, table_name, table_data, columns, db, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"编辑表: {table_name}")
        self.setMinimumSize(800, 600)

        self.table_name = table_name
        self.table_data = table_data
        self.columns = columns
        self.db = db

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 表格视图
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(len(self.columns))
        self.table_widget.setHorizontalHeaderLabels(self.columns)
        self.table_widget.setEditTriggers(QTableWidget.AllEditTriggers)
        self.table_widget.setAlternatingRowColors(True)

        # 填充数据
        self.table_widget.setRowCount(len(self.table_data))
        for row_idx, row_data in enumerate(self.table_data):
            for col_idx, col_name in enumerate(self.columns):
                item = QTableWidgetItem(str(row_data.get(col_name, "")))
                self.table_widget.setItem(row_idx, col_idx, item)

        # 调整列宽
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_widget.horizontalHeader().setStretchLastSection(True)

        # 按钮区域
        btn_layout = QHBoxLayout()

        self.add_row_btn = QPushButton("添加行")
        self.add_row_btn.clicked.connect(self.add_row)
        btn_layout.addWidget(self.add_row_btn)

        self.delete_row_btn = QPushButton("删除选中行")
        self.delete_row_btn.clicked.connect(self.delete_row)
        btn_layout.addWidget(self.delete_row_btn)

        self.save_changes_btn = QPushButton("保存更改")
        self.save_changes_btn.clicked.connect(self.save_changes)
        btn_layout.addWidget(self.save_changes_btn)

        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.close_btn)

        # 状态栏
        self.status_label = QLabel("就绪")

        layout.addWidget(self.table_widget)
        layout.addLayout(btn_layout)
        layout.addWidget(self.status_label)

    def add_row(self):
        row_idx = self.table_widget.rowCount()
        self.table_widget.insertRow(row_idx)

        # 初始化新行的值
        for col_idx in range(self.table_widget.columnCount()):
            item = QTableWidgetItem("")
            self.table_widget.setItem(row_idx, col_idx, item)

        # 滚动到新行
        self.table_widget.scrollToBottom()

    def delete_row(self):
        selected_rows = sorted(set(index.row() for index in self.table_widget.selectedIndexes()), reverse=True)

        if not selected_rows:
            QMessageBox.warning(self, "警告", "请选择要删除的行")
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除选中的 {len(selected_rows)} 行数据吗？此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            for row in selected_rows:
                self.table_widget.removeRow(row)

            self.status_label.setText(f"已删除 {len(selected_rows)} 行")

    def save_changes(self):
        try:
            # 获取表的主键
            table = self.db.tables[self.table_name]
            primary_key = table['primary_key']

            if not primary_key:
                QMessageBox.warning(self, "警告", f"表 '{self.table_name}' 没有主键，无法保存更改")
                return

            # 收集当前数据
            current_data = {}
            for row_idx in range(self.table_widget.rowCount()):
                row = {}
                for col_idx, col_name in enumerate(self.columns):
                    item = self.table_widget.item(row_idx, col_idx)
                    row[col_name] = item.text() if item else ""

                # 使用主键作为键
                primary_key_value = row[primary_key]
                if primary_key_value:
                    if primary_key_value in current_data:  # 检查是否发生主键冲突
                        QMessageBox.warning(self, "错误修改", f"主键 '{primary_key_value}' 的记录已存在! 发生主键冲突!")
                        return
                    current_data[primary_key_value] = row

            # 找出已删除的行(或已经修改主键值的行)
            original_pks = {str(row[primary_key]): row for row in self.table_data if primary_key in row}
            deleted_pks = [pk for pk in original_pks if pk not in current_data]

            # 执行删除操作
            for pk in deleted_pks:
                self.db.delete_row(self.table_name, pk)

            # 处理列更新和新增
            for pk, row in current_data.items():
                if pk in original_pks:
                    # 更新行
                    original_row = original_pks[pk]
                    updates = {}

                    for col_name, value in row.items():
                        if str(original_row.get(col_name, "")) != value:
                            updates[col_name] = value  # 若有不一致的列数据, 则更新此记录的列信息, 更新为用户输入的数据

                    if updates:  # 更新!
                        self.db.update_row(self.table_name, pk, updates)
                else:
                    # 新增行
                    self.db.insert_row(self.table_name, list(row.values()))

            QMessageBox.information(self, "成功", "所有更改已保存")
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存更改失败: {str(e)}")
            self.status_label.setText(f"错误: {str(e)}")


# ===== 表结构详情对话框 =====
class TableStructureDialog(QDialog):
    def __init__(self, table_name, table_data, db, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"表结构: {table_name}")
        self.setMinimumSize(600, 400)

        self.table_name = table_name
        self.table_data = table_data
        self.db = db

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 创建分组框显示表信息
        table_info_group = QGroupBox("表信息")
        table_info_layout = QFormLayout()

        table_info_layout.addRow("表名:", QLabel(self.table_name))
        table_info_layout.addRow("记录数:", QLabel(str(len(self.table_data['data']))))

        primary_key = self.table_data['primary_key']
        table_info_layout.addRow("主键:", QLabel(primary_key if primary_key else "无"))

        table_info_group.setLayout(table_info_layout)
        layout.addWidget(table_info_group)

        # 创建分组框显示列信息
        columns_group = QGroupBox("列信息")
        columns_layout = QVBoxLayout()

        # 表格视图
        self.columns_table = QTableWidget()
        self.columns_table.setColumnCount(4)
        self.columns_table.setHorizontalHeaderLabels(["列名", "数据类型", "约束", "默认值"])
        self.columns_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.columns_table.setAlternatingRowColors(True)

        # 填充列数据
        columns = self.table_data['columns']
        self.columns_table.setRowCount(len(columns))

        for row_idx, (col_name, col_data) in enumerate(columns.items()):
            self.columns_table.setItem(row_idx, 0, QTableWidgetItem(col_name))
            self.columns_table.setItem(row_idx, 1, QTableWidgetItem(col_data['type']))
            self.columns_table.setItem(row_idx, 2, QTableWidgetItem(", ".join(col_data['constraints'])))
            self.columns_table.setItem(row_idx, 3, QTableWidgetItem(""))  # 默认值暂时不支持

        # 调整列宽
        self.columns_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.columns_table.horizontalHeader().setStretchLastSection(True)

        columns_layout.addWidget(self.columns_table)
        columns_group.setLayout(columns_layout)
        layout.addWidget(columns_group)

        # 关闭按钮
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)
        layout.addWidget(self.close_btn, alignment=Qt.AlignRight)


# ===== 表数据预览对话框 =====
class TableDataPreviewDialog(QDialog):
    def __init__(self, table_name, table_data, db, parent=None):
        super().__init__(parent)
        self.data_table = None
        self.table_name = table_name
        self.db = db
        self._init_base_ui()  # 初始化基础布局
        self.refresh_data()  # 初始化加载数据
        self.setMinimumSize(800, 600)

    def _init_base_ui(self):
        """初始化基础布局（只创建一次）"""
        layout = QVBoxLayout()
        self.data_group = QGroupBox()
        self.data_layout = QVBoxLayout()
        self.data_group.setLayout(self.data_layout)
        layout.addWidget(self.data_group)

        btn_layout = QHBoxLayout()
        self.edit_btn = QPushButton("编辑数据")
        self.refresh_btn = QPushButton("刷新")
        self.close_btn = QPushButton("关闭")
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self.edit_btn.clicked.connect(self.edit_data)
        self.refresh_btn.clicked.connect(self.refresh_data)
        self.close_btn.clicked.connect(self.close)

    def _init_table(self):
        """初始化表格控件（可重用）"""
        if self.data_table:
            self.data_table.deleteLater()
        self.data_table = QTableWidget()
        self.data_layout.addWidget(self.data_table)
        self.data_table.setSortingEnabled(True)

    def update_table(self):
        """核心数据更新方法"""
        self._init_table()  # 重建表格控件
        table_data = self.table_data
        if not table_data:
            self._show_empty_state()
            return

        # 更新表格结构
        columns = list(table_data[0].keys())
        self.data_table.setColumnCount(len(columns))
        self.data_table.setHorizontalHeaderLabels(columns)
        self.data_table.setRowCount(len(table_data))

        # 填充数据
        for row_idx, row in enumerate(table_data):
            for col_idx, col in enumerate(columns):
                item = QTableWidgetItem(str(row.get(col, "")))
                self.data_table.setItem(row_idx, col_idx, item)

        # 保持原有交互状态
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.data_table.horizontalHeader().setStretchLastSection(True)

    def refresh_data(self):
        """优化后的刷新逻辑"""
        try:
            self.table_data = self.db.get_table_data(self.table_name)
            self.update_table()  # 仅更新表格内容
        except Exception as e:
            QMessageBox.critical(self, "错误", f"刷新失败: {str(e)}")

    def edit_data(self):
        if not self.table_data:
            QMessageBox.information(self, "信息", "表中没有数据可编辑")
            return

        # 获取列名
        columns = list(self.table_data[0].keys()) if self.table_data else []

        # 打开编辑对话框
        edit_dialog = EditTableDialog(self.table_name, self.table_data, columns, self.db, self)
        if edit_dialog.exec_():
            self.refresh_data()

    def _show_empty_state(self):
        """空数据状态处理"""
        self.data_table.setColumnCount(1)
        self.data_table.setHorizontalHeaderLabels(["信息"])
        self.data_table.setRowCount(1)
        self.data_table.setItem(0, 0, QTableWidgetItem("表中没有数据"))


# ===== 增强版SQL解释器图形界面 =====
class AdvancedSQLInterpreterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("高级SQL解释器")
        self.setGeometry(100, 100, 1200, 800)

        self.db = Database()
        self.init_ui()

    def init_ui(self):
        # 创建菜单栏
        self.create_menu_bar()

        # 创建工具栏
        self.create_tool_bar()

        # 创建主界面组件
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)

        # SQL编辑区域
        self.sql_edit = QTextEdit()
        self.sql_edit.setFont(QFont("Consolas", 10))
        self.sql_edit.setPlaceholderText("输入SQL语句...")

        # 应用语法高亮
        self.highlighter = SQLHighlighter(self.sql_edit.document())

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("就绪")
        self.status_bar.addWidget(self.status_label)

        # 执行按钮
        self.execute_btn = QPushButton("执行 SQL")
        self.execute_btn.setIcon(QIcon.fromTheme("system-run"))
        self.execute_btn.clicked.connect(self.execute_sql)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.execute_btn)
        btn_layout.addStretch()

        # 结果区域
        self.result_tabs = QTabWidget()
        self.result_tabs.setTabsClosable(True)  # 允许关闭标签页
        self.result_tabs.tabCloseRequested.connect(self.close_result_tab)  # 绑定关闭事件

        # 数据库浏览器
        self.db_browser = QTreeWidget()
        self.db_browser.setHeaderLabels(["数据库浏览器"])
        self.db_browser.setColumnCount(1)
        self.db_browser.setContextMenuPolicy(Qt.CustomContextMenu)
        self.db_browser.customContextMenuRequested.connect(self.show_db_context_menu)
        self.db_browser.itemDoubleClicked.connect(self.on_db_item_double_click)

        # 分割器（水平分割，左侧数据库浏览器，右侧结果）
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.db_browser)
        splitter.addWidget(self.result_tabs)
        splitter.setSizes([250, 950])

        main_layout.addLayout(btn_layout)
        main_layout.addWidget(self.sql_edit)
        main_layout.addWidget(splitter)

        self.setCentralWidget(central_widget)

        # 示例SQL
        self.set_example_sql()

        # 初始化数据库浏览器
        self.update_db_browser()

    def create_menu_bar(self):
        menu_bar = self.menuBar()

        # 文件菜单
        file_menu = menu_bar.addMenu("文件")

        new_action = QAction("新建", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_query)
        file_menu.addAction(new_action)

        open_action = QAction("打开", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)

        save_action = QAction("保存", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 查询菜单
        query_menu = menu_bar.addMenu("查询")

        execute_action = QAction("执行", self)
        execute_action.setShortcut("F5")
        execute_action.triggered.connect(self.execute_sql)
        query_menu.addAction(execute_action)

        # 数据库菜单
        db_menu = menu_bar.addMenu("数据库")

        refresh_action = QAction("刷新结构", self)
        refresh_action.triggered.connect(self.update_db_browser)
        db_menu.addAction(refresh_action)

        # 帮助菜单
        help_menu = menu_bar.addMenu("帮助")

        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_tool_bar(self):
        tool_bar = QToolBar("工具栏")
        self.addToolBar(tool_bar)

        execute_action = QAction(QIcon.fromTheme("system-run"), "执行", self)
        execute_action.triggered.connect(self.execute_sql)
        tool_bar.addAction(execute_action)

        refresh_action = QAction(QIcon.fromTheme("view-refresh"), "刷新", self)
        refresh_action.triggered.connect(self.update_db_browser)
        tool_bar.addAction(refresh_action)

    def set_example_sql(self):
        example = """
        /* 创建users表 */
        CREATE TABLE users (
            id INT PRIMARY KEY,             -- id为整形主键
            name VARCHAR(50) NOT NULL,      -- name为非空字符串, 长度为50
            age INT,                        -- age为整形
            email VARCHAR(100) UNIQUE       -- email为唯一的字符串, 长度为50
        );
        
        /* 插入数据 */
        INSERT INTO users VALUES (1, 'Alice', 28, 'alice@example.com');
        INSERT INTO users VALUES (2, 'Bob', 35, 'bob@example.com');
        INSERT INTO users VALUES (3, 'Charlie', 30, 'charlie@example.com');
        
        /* 查询 */
        SELECT * FROM users;
        SELECT id, name, age FROM users WHERE age > 30 ORDER BY age DESC;
        
        /* 更新 */
        UPDATE users SET email = 'alice.new@example.com' WHERE id = 1;
        
        /* 再次查询 */
        SELECT COUNT(*) AS total_users, AVG(age) AS avg_age FROM users;
        
        /* 删除记录 */
        DELETE FROM users WHERE age < 29;
            
        /* 删除users表 */
        -- DROP TABLE users;
        """
        self.sql_edit.setPlainText(example)

    def execute_sql(self):
        sql = self.sql_edit.toPlainText().strip()
        if not sql:
            self.status_label.setText("错误: SQL语句为空")
            return

        try:
            self.status_label.setText("正在执行...")
            self.status_bar.repaint()

            # 解析和执行
            tokens = sql_lexer(sql)
            ast = sql_parser(tokens)
            results = self.db.execute(ast)

            # 清空现有结果并重新渲染
            while self.result_tabs.count() > 0:
                self.result_tabs.removeTab(0)

            for i, result in enumerate(results):
                if isinstance(result, tuple) and result[0] == 'select':
                    self.display_result(result[1], f"查询结果 { i +1}")
                elif isinstance(result, tuple) and result[0] == 'error':
                    self.display_error(result[1])
                else:
                    self.display_message(result)

            # 更新数据库浏览器
            self.update_db_browser()
            self.status_label.setText("执行完成")

        except Exception as e:
            self.display_error(f"执行错误: {str(e)}")
            self.status_label.setText(f"错误: {str(e)}")

    def display_result(self, data, tab_name="结果"):
        """通用结果显示方法"""
        table_widget = QTableWidget()
        table_widget.setEditTriggers(QTableWidget.NoEditTriggers)
        table_widget.setAlternatingRowColors(True)

        if data:
            # 获取列名
            columns = list(data[0].keys()) if isinstance(data[0], dict) else []
            table_widget.setColumnCount(len(columns))
            table_widget.setHorizontalHeaderLabels(columns)

            # 设置表格内容
            table_widget.setRowCount(len(data))
            for row_idx, row_data in enumerate(data):
                for col_idx, col_name in enumerate(columns):
                    item = QTableWidgetItem(str(row_data.get(col_name, "")))
                    table_widget.setItem(row_idx, col_idx, item)

            # 调整列宽以适应内容
            table_widget.resizeColumnsToContents()

        self.result_tabs.addTab(table_widget, tab_name)
        self.result_tabs.setCurrentWidget(table_widget)

    def display_error(self, msg):
        """显示错误信息"""
        error_widget = QTextEdit()
        error_widget.setReadOnly(True)
        error_widget.setPlainText(msg)
        error_widget.setTextColor(QColor("red"))
        self.result_tabs.addTab(error_widget, "错误")
        self.result_tabs.setCurrentWidget(error_widget)

    def display_message(self, msg):
        """显示操作消息"""
        msg_widget = QTextEdit()
        msg_widget.setReadOnly(True)
        msg_widget.setPlainText(str(msg))
        self.result_tabs.addTab(msg_widget, "操作结果")
        self.result_tabs.setCurrentWidget(msg_widget)

    def close_result_tab(self, index):
        """关闭结果标签页"""
        self.result_tabs.removeTab(index)

    def update_db_browser(self):
        """更新数据库浏览器"""
        self.db_browser.clear()

        # 添加数据库节点
        db_item = QTreeWidgetItem([f"main ({len(self.db.tables)} 张表)"])
        db_item.setData(0, Qt.UserRole, {"type": "database", "name": "main"})
        self.db_browser.addTopLevelItem(db_item)

        # 添加表节点
        for table_name in sorted(self.db.tables.keys()):
            table = self.db.tables[table_name]
            table_item = QTreeWidgetItem([f"{table_name} ({len(table['data'])} 条记录)"])
            table_item.setData(0, Qt.UserRole, {"type": "table", "name": table_name})

            # 添加列子节点
            columns_item = QTreeWidgetItem(["列"])
            columns_item.setData(0, Qt.UserRole, {"type": "columns", "table": table_name})

            for col_name, col_data in table['columns'].items():
                col_item = QTreeWidgetItem([f"{col_name} ({col_data['type']})"])
                col_item.setData(0, Qt.UserRole, {"type": "column", "table": table_name, "name": col_name})
                columns_item.addChild(col_item)

            table_item.addChild(columns_item)

            # 添加索引子节点（当前简化实现，实际需要解析索引信息）
            indexes_item = QTreeWidgetItem(["索引"])
            indexes_item.setData(0, Qt.UserRole, {"type": "indexes", "table": table_name})

            # 如果有主键，添加为主键索引
            if table['primary_key']:
                pk_item = QTreeWidgetItem([f"PRIMARY ({table['primary_key']})"])
                pk_item.setData(0, Qt.UserRole, {"type": "index", "table": table_name, "name": "PRIMARY"})
                indexes_item.addChild(pk_item)

            table_item.addChild(indexes_item)

            db_item.addChild(table_item)

        self.db_browser.expandAll()

    def show_db_context_menu(self, position):
        """显示数据库浏览器的右键菜单"""
        item = self.db_browser.itemAt(position)
        if not item:
            return

        item_data = item.data(0, Qt.UserRole)
        if not item_data:
            return

        menu = QMenu()

        if item_data['type'] == 'database':
            refresh_action = menu.addAction("刷新")
            refresh_action.triggered.connect(self.update_db_browser)

        elif item_data['type'] == 'table':
            view_data_action = menu.addAction("查看数据")
            view_data_action.triggered.connect(lambda: self.view_table_data(item_data['name']))

            view_structure_action = menu.addAction("查看结构")
            view_structure_action.triggered.connect(lambda: self.view_table_structure(item_data['name']))

            generate_select_action = menu.addAction("生成SELECT语句")
            generate_select_action.triggered.connect(lambda: self.generate_select(item_data['name']))

            menu.addSeparator()

            drop_table_action = menu.addAction("删除表")
            drop_table_action.triggered.connect(lambda: self.drop_table(item_data['name']))

        elif item_data['type'] == 'column':
            copy_name_action = menu.addAction("复制列名")
            copy_name_action.triggered.connect(lambda: self.copy_column_name(item_data['table'], item_data['name']))

            generate_where_action = menu.addAction("生成WHERE条件")
            generate_where_action.triggered.connect(lambda: self.generate_where(item_data['table'], item_data['name']))

        menu.exec_(self.db_browser.viewport().mapToGlobal(position))

    def on_db_item_double_click(self, item, column):
        """处理数据库浏览器中的双击事件"""
        item_data = item.data(0, Qt.UserRole)
        if not item_data:
            return

        if item_data['type'] == 'table':
            self.view_table_data(item_data['name'])

    def view_table_data(self, table_name):
        """查看表数据"""
        try:
            table_data = self.db.get_table_data(table_name)
            dialog = TableDataPreviewDialog(table_name, table_data, self.db, self)
            dialog.exec_()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"查看表数据失败: {str(e)}")

    def view_table_structure(self, table_name):
        """查看表结构"""
        try:
            table_data = self.db.tables.get(table_name)
            if not table_data:
                QMessageBox.warning(self, "警告", f"表 '{table_name}' 不存在")
                return

            dialog = TableStructureDialog(table_name, table_data, self.db, self)
            dialog.exec_()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"查看表结构失败: {str(e)}")

    def generate_select(self, table_name):
        """生成SELECT语句"""
        try:
            table_data = self.db.tables.get(table_name)
            if not table_data:
                QMessageBox.warning(self, "警告", f"表 '{table_name}' 不存在")
                return

            columns = list(table_data['columns'].keys())
            sql = f"SELECT {', '.join(columns)}\nFROM {table_name};\n"

            # 将生成的SQL添加到编辑器中
            self.sql_edit.insertPlainText(sql)
            self.status_label.setText(f"已生成SELECT语句: {table_name}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"生成SELECT语句失败: {str(e)}")

    def drop_table(self, table_name):
        """删除表"""
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除表 '{table_name}' 吗？此操作将永久删除所有数据！",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # 执行删除表操作
                sql = f"DROP TABLE {table_name};"
                tokens = sql_lexer(sql)
                ast = sql_parser(tokens)
                results = self.db.execute(ast)

                # 更新数据库浏览器
                self.update_db_browser()

                # 显示结果
                if results and isinstance(results[0], str):
                    self.status_label.setText(results[0])
                else:
                    self.status_label.setText(f"表 '{table_name}' 已删除")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除表失败: {str(e)}")
                self.status_label.setText(f"错误: {str(e)}")

    def copy_column_name(self, table_name, column_name):
        """复制列名到剪贴板"""
        clipboard = QApplication.clipboard()
        clipboard.setText(column_name)
        self.status_label.setText(f"已复制列名: {column_name}")

    def generate_where(self, table_name, column_name):
        """生成WHERE条件"""
        value, ok = QInputDialog.getText(
            self, "输入值",
            f"为列 '{column_name}' 输入值 (将生成 WHERE {column_name} = value):"
        )

        if ok and value:
            # 判断值类型
            if value.isdigit():
                condition = f"{column_name} = {value}"
            else:
                condition = f"{column_name} = '{value}'"

            # 将生成的条件添加到编辑器中
            current_text = self.sql_edit.toPlainText()

            # 如果当前有SQL语句，尝试找到合适的位置插入WHERE
            if current_text.strip().upper().startswith("SELECT"):
                # 查找FROM子句
                from_pos = current_text.upper().find("FROM")
                if from_pos != -1:
                    # 查找FROM之后的第一个分号或行尾
                    end_pos = current_text.find(";", from_pos)
                    if end_pos == -1:
                        end_pos = len(current_text)

                    # 插入WHERE子句
                    new_text = (
                            current_text[:end_pos] +
                            f"\nWHERE {condition}" +
                            current_text[end_pos:]
                    )
                    self.sql_edit.setPlainText(new_text)
                    self.status_label.setText(f"已添加WHERE条件: {condition}")
                    return

            # 默认直接添加到末尾
            self.sql_edit.insertPlainText(f"\nWHERE {condition}")
            self.status_label.setText(f"已添加WHERE条件: {condition}")

    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于 高级SQL解释器",
            "版本: 1.3\n\n"
            "支持语法:\n"
            "- CREATE TABLE (PRIMARY KEY/NOT NULL/UNIQUE)\n"
            "- INSERT/SELECT/UPDATE/DELETE\n"
            "- WHERE/ORDER BY/LIMIT/GROUP BY/HAVING\n"
            "- 聚合函数 (COUNT/SUM/AVG/MIN/MAX)\n"
            "- 基本表达式和运算符\n\n"
            "界面功能:\n"
            "- 完整的数据库浏览功能\n"
            "- 表数据查看和编辑\n"
            "- 表结构查看\n"
            "- SQL自动生成\n"
            "- 语法高亮\n"
            "- 多结果标签页\n"
            "- SQL文件导入/导出"
        )

    def new_query(self):
        """新建查询"""
        self.sql_edit.clear()
        self.status_label.setText("新建查询")

    def open_file(self):
        """打开SQL文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开SQL文件", "", "SQL文件 (*.sql);;所有文件 (*.*)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.sql_edit.setPlainText(f.read())
                self.status_label.setText(f"已打开文件: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"打开文件失败: {str(e)}")
                self.status_label.setText("打开文件失败")

    def save_file(self):
        """保存SQL文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存SQL文件", "", "SQL文件 (*.sql);;所有文件 (*.*)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.sql_edit.toPlainText())
                self.status_label.setText(f"已保存文件: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存文件失败: {str(e)}")
                self.status_label.setText("保存文件失败")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    font = QFont("Segoe UI", 9)
    app.setFont(font)

    window = AdvancedSQLInterpreterGUI()
    window.show()
    sys.exit(app.exec_())