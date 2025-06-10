from PyQt5.QtCore import Qt, QRegExp, QTimer, pyqtSignal

# ===== 词法分析器 =====
# 读取器模式标志
STR_READER = 0    # 字符流模式
TOKEN_READER = 1  # Token列表模式


# SQL常用关键字集合（部分）
KEYWORDS = {
    'SELECT', 'FROM', 'WHERE', 'CREATE', 'TABLE', 'INSERT', 'INTO',
    'VALUES', 'DELETE', 'UPDATE', 'SET', 'INT', 'VARCHAR', 'PRIMARY',
    'KEY', 'NOT', 'NULL', 'AND', 'OR', 'AS', 'DISTINCT', 'ORDER', 'BY',
    'ASC', 'DESC', 'LIKE', 'IN', 'BETWEEN', 'LIMIT', 'COUNT', 'SUM',
    'AVG', 'MIN', 'MAX', 'GROUP', 'HAVING', 'UNIQUE', 'DROP'
}
KEYWORDS_AS_OPERATORS = {'LIKE', 'IN', 'BETWEEN'}  # 新增的关键字视为操作符
# 操作符映射表
OPERATORS = {
    '=': 'EQ', '<>': 'NEQ', '!=': 'NEQ', '<': 'LT', '<=': 'LTE',
    '=<': 'LTE', '>': 'GT', '>=': 'GTE', '=>': 'GTE',
    '+': 'PLUS', '-': 'MINUS', '*': 'ASTERISK', '/': 'SLASH',
    ',': 'COMMA', '(': 'LPAREN', ')': 'RPAREN', ';': 'SEMI',
    '.': 'DOT', '[': 'LBRACKET', ']': 'RBRACKET'
}


def error(src, msg):
    raise Exception(f'{src} : {msg}')


def tk_tag(t):
    return t[0]

def mk_tk(tag, val=None):
    return [tag, val]


class BaseReader:
    """SQL命令 字符串/token列表 读取器"""
    def __init__(self, s, err, mod=STR_READER):
        self.err = err
        self.pos = -1  # 当前读取到的位置
        self.current_val = None  # 当前读取到的值
        self.current_str = s  # 输入的srt字符串/token
        self.current_mod = mod  # 当前模式(读取str or 读取token)
        self.next()

    def peek(self, p=0):
        """读取前方第p个字符"""
        if self.pos + p >= len(self.current_str):
            return 'eof'
        elif self.current_mod == STR_READER:  # 读取字符串
            return self.current_str[self.pos + p]
        else:  # 读取token
            return tk_tag(self.current_str[self.pos + p])

    def is_eof(self):
        """判断是否读完"""
        return self.pos >= len(self.current_str)

    def skip(self, n=1):
        """跳过n个字符"""
        self.pos += n

    def next(self):
        """读取下一个字符"""
        old = self.current_val
        self.pos = self.pos + 1
        if self.pos >= len(self.current_str):
            self.current_val = 'eof'
        else:
            self.current_val = self.current_str[self.pos]
        return old

    def match(self, t):
        if self.current_mod == STR_READER and self.peek() != t:
            self.err(f'期望 "{t}" , 实际为 "{self.current_val}"')
        elif self.current_mod == TOKEN_READER and t not in self.current_val:
            self.err(f'期望 "{t}" , 实际为 "{self.current_val}"')
        return self.next()


def sql_lexer(input_str):
    """SQL命令词法解析器"""

    def _error(msg):
        # 专用报错
        error('SQL lexer', msg)

    reader = BaseReader(input_str, _error, 0)  # 初始化读取器, 设置为字符流模式
    tokens = []  # 储存由 SQL命令字符 转化而成的 Token列表

    def tokenize():
        """主入口：生成Token列表"""
        while not reader.is_eof():
            c = reader.peek()

            # 跳过空白字符 或 注释符
            if c.isspace() or (reader.peek() == '-' and reader.peek(1) == '-') or (reader.peek() == '/' and reader.peek(1) == '*') :  # 跳过空白符 或 "--"注释 或 "/**/" 注释
                _skip_whitespace()
                continue

            # 处理标识符和关键字
            if c.isalpha() or c == '_':
                _read_identifier()
                continue

            # 处理数字字面量
            if c.isdigit():
                _read_number()
                continue

            # 处理字符串字面量
            if c == "'" or c == '"':
                _read_string()
                continue

            # 处理操作符
            if c in OPERATORS:
                _read_operator()
                continue

            _error(f"无法识别的字符: {c}")

        return tokens

    def _skip_whitespace():
        while True:
            # 处理空白符
            while reader.peek() in [' ', '\t', '\r', '\n']:
                reader.next()
            # 新增注释处理
            if reader.peek() == '-':
                while reader.peek() not in ['\n', '\r', 'eof']:
                    reader.next()
                continue
            elif reader.peek() == '/':
                reader.next()  # 跳过'/'
                reader.next()  # 跳过'*'
                while True:
                    if reader.peek() == '*' and reader.peek(1) == '/' :
                        reader.next()  # 跳过'*'
                        reader.next()  # 跳过'/'
                        break
                    elif reader.peek() == 'eof':
                        _error("非法注释: 未匹配到 '*/'")
                    reader.next()
            else:
                break

    def _read_identifier():
        """读取标识符或关键字"""
        start_pos = reader.pos
        while (c := reader.peek()) and (c.isalnum() or c == '_') and c != 'eof':
            reader.next()

        value = reader.current_str[start_pos:reader.pos]
        upper_value = value.upper()

        # 判断是否是关键字
        if upper_value in KEYWORDS:
            if upper_value in KEYWORDS_AS_OPERATORS:
                # 将LIKE等关键字作为操作符处理
                tokens.append(mk_tk(upper_value,'OPERATOR'))  # 标记类型为OPERATOR，值为LIKE
            else:
                tokens.append(mk_tk(upper_value, 'KEYWORD'))
        else:
            tokens.append(mk_tk('IDENTIFIER', value))
            # tokens.append(('IDENTIFIER', value))

    def _read_number():
        """读取数字字面量（整数或浮点数）"""
        start_pos = reader.pos
        has_dot = False

        while (c := reader.peek()) and (c.isdigit() or c == '.'):
            if c == '.':
                if has_dot:
                    _error("数字包含多个小数点")
                has_dot = True
            reader.next()

        value = reader.current_str[start_pos:reader.pos]
        tokens.append(mk_tk('NUMBER', float(value) if has_dot else int(value)))
        # tokens.append(('NUMBER', float(value) if has_dot else int(value)))

    def _read_string():
        """读取字符串字面量"""
        start_quotation = reader.peek()  # 记录起始引号
        reader.next()  # 跳过起始引号
        start_pos = reader.pos
        escaped = False

        while True:
            c = reader.peek()
            if c is None:
                _error("未闭合的字符串")

            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == "'" and start_quotation == c:
                break
            elif c == '"' and start_quotation == c:
                break

            reader.next()

        value = reader.current_str[start_pos:reader.pos]
        tokens.append(mk_tk('STRING', value))
        # tokens.append(('STRING', value))
        reader.next()  # 跳过结束引号

    def _read_operator():
        """读取操作符，处理组合操作符如>=, <=等"""
        c = reader.next()
        next_c = reader.peek()

        # 优先处理双字符操作符
        if next_c and (op := c + next_c) in OPERATORS:
            reader.next()
            tokens.append(mk_tk(OPERATORS[op], 'OPERATOR'))
            # tokens.append(('OPERATOR', OPERATORS[op]))
        elif c in OPERATORS:
            tokens.append(mk_tk(OPERATORS[c],'OPERATOR' ))
            # tokens.append(('OPERATOR', OPERATORS[c]))
        else:
            _error(f"无法识别的操作符: {c}")

    return tokenize()  # 开始执行词法解析器程序, 最终返回SQL命令对应Token列表


def sql_parser(tokens):
    """SQL 语法解析器"""
    def _error(msg):
        # 专用报错
        error('SQL Parser', msg)

    reader = BaseReader(tokens, _error, TOKEN_READER)  # 初始化读取器, 设置为Token模式
    statements = []  # 存储解析后的语句

    def parser():
        """主入口, 生成语法树"""
        while not reader.is_eof():
            current_token = reader.current_val
            if current_token[1] == 'KEYWORD':
                keyword = reader.next()[0]
                if keyword == 'CREATE':
                    statements.append(parse_create())
                elif keyword == 'INSERT':
                    statements.append(parse_insert())
                elif keyword == 'SELECT':
                    statements.append(parse_select())
                elif keyword == 'DELETE':
                    statements.append(parse_delete())
                elif keyword == 'UPDATE':
                    statements.append(parse_update())
                elif keyword == 'DROP':
                    statements.append(parse_drop())
                else:
                    _error(f"未实现的语句类型: {keyword}")
            reader.match('SEMI')  # 吃掉语句结束符 ;

        return statements

    def parse_expression():
        """解析表达式"""
        expr = []
        while reader.peek() not in ('RPAREN', 'COMMA', 'SEMI', 'WHERE', 'eof'):
            if reader.current_val[1] == 'OPERATOR':
                expr.append(reader.next()[0])  #  获取运算符, 由于早期设计问题, 运算法Token格式为[op , 'OPERATOR']
            else:
                expr.append(reader.next()[1])  #  获取数据, 由于早期设计问题, 数据Token格式为['数据类型' , 值]

        return expr

    def parse_column_definitions():
        """解析列定义列表"""
        columns = []
        reader.match('LPAREN')  # 吃掉 (
        while reader.peek() != 'RPAREN':
            # 解析列名
            col_name = reader.match('IDENTIFIER')[1]
            # 解析数据类型
            data_type = reader.match('KEYWORD')[0]
            size = None
            if reader.peek() == 'LPAREN':  # 处理类似 VARCHAR(255)
                reader.next()
                size = int(reader.match('NUMBER')[1])
                reader.match('RPAREN')
            # 解析约束
            constraints = []
            while reader.current_val[1] == 'KEYWORD':
                if reader.peek() == 'PRIMARY':
                    reader.next()
                    reader.match('KEY')  # 吃掉 KEY
                    constraints.append('PRIMARY KEY')
                elif reader.peek() == 'NOT':
                    reader.next()
                    reader.match('NULL')  # 吃掉 NULL
                    constraints.append('NOT NULL')
                else:
                    constraints.append(reader.next()[0])
            # 添加到列定义
            columns.append({
                'name': col_name,
                'type': data_type + (f'({size})' if size else ''),
                'constraints': constraints
            })
            if reader.peek() == 'COMMA':
                reader.next()  # 吃掉逗号
        reader.match('RPAREN')  # 吃掉 )
        return columns

    # ---------------------- 语句解析 ----------------------
    def parse_create():
        """解析CREATE TABLE语句"""
        reader.match('TABLE')  # 吃掉 TABLE
        table_name = reader.match('IDENTIFIER')[1]
        columns = parse_column_definitions()
        return {'type': 'create_table', 'name': table_name, 'columns': columns}

    def parse_insert():
        """解析INSERT INTO语句"""
        reader.match('INTO')  # 吃掉 INTO
        table_name = reader.match('IDENTIFIER')[1]
        reader.match('VALUES')  # 吃掉 VALUES
        reader.match('LPAREN')  # 吃掉 (
        values = []
        while reader.peek() != 'RPAREN':
            if reader.peek() in ('STRING', 'NUMBER'):
                values.append(reader.next()[1])
            elif reader.peek() == 'COMMA':
                reader.next()  # 吃掉逗号
        reader.match('RPAREN')  # 吃掉 )
        return {'type': 'insert', 'table': table_name, 'values': values}

    def parse_select():
        """解析SELECT语句"""
        select_clause = {'columns': [], 'distinct': False}

        # 处理DISTINCT关键字
        if reader.peek() == 'DISTINCT':
            select_clause['distinct'] = True
            reader.next()

        # 解析选择的列
        while reader.peek() not in ('FROM', 'eof'):
            # 处理带表名前缀的列名
            if reader.peek() == 'IDENTIFIER' and reader.peek(1) == 'DOT':
                table_name = reader.next()[1]  # 表名
                reader.match('DOT')  # 吃掉点
                column_name = reader.match('IDENTIFIER')[1]  # 列名
                identifier = f"{table_name}.{column_name}"

                # 处理别名
                alias = None
                if reader.peek() == 'AS':
                    reader.next()
                    alias = reader.match('IDENTIFIER')[1]
                select_clause['columns'].append({
                    'name': identifier,
                    'alias': alias
                })
            # 处理通配符
            elif reader.peek() == 'ASTERISK':
                select_clause['columns'].append('*')
                reader.next()
            # 处理聚合函数
            elif reader.peek() in ('COUNT', 'SUM', 'AVG', 'MIN', 'MAX'):
                func = parse_aggregate_function()
                select_clause['columns'].append(func)
            # 处理普通列名
            else:
                col = reader.match('IDENTIFIER')[1]
                # 处理别名
                if reader.peek() == 'AS':
                    reader.next()
                    alias = reader.match('IDENTIFIER')[1]
                    select_clause['columns'].append({'name': col, 'alias': alias})
                else:
                    select_clause['columns'].append(col)

            # 处理逗号分隔
            if reader.peek() == 'COMMA':
                reader.next()

        reader.match('FROM')

        # 解析多表（逗号分隔）
        tables = []
        while True:
            # 读取表名
            table_name = reader.match('IDENTIFIER')[1]
            alias = None

            # 检查是否有别名
            if reader.peek() == 'AS':
                reader.next()  # 跳过AS
                alias = reader.match('IDENTIFIER')[1]
            elif reader.peek() == 'IDENTIFIER':  # AS关键字可选
                alias = reader.match('IDENTIFIER')[1]

            tables.append({
                'name': table_name,
                'alias': alias or table_name  # 如果没有别名，使用表名
            })

            # 检查是否有更多表
            if reader.peek() == 'COMMA':
                reader.next()  # 跳过逗号
            else:
                break

        # 解析WHERE子句
        where_clause = None
        if reader.peek() == 'WHERE':
            reader.next()
            where_clause = parse_where_expression()

        # 解析GROUP BY子句
        group_by = None
        if reader.peek() == 'GROUP':
            reader.next()  # 吃掉GROUP
            reader.match('BY')  # 吃掉BY
            group_by = []
            while reader.peek() not in ('HAVING', 'ORDER', 'LIMIT', 'SEMI', 'eof'):
                # 处理带表名前缀的列名
                if reader.peek() == 'IDENTIFIER' and reader.peek(1) == 'DOT':
                    table_name = reader.next()[1]  # 表名
                    reader.match('DOT')  # 吃掉点
                    column_name = reader.match('IDENTIFIER')[1]  # 列名
                    group_by.append(f"{table_name}.{column_name}")
                else:
                    col = reader.match('IDENTIFIER')[1]
                    group_by.append(col)
                if reader.peek() == 'COMMA':
                    reader.next()

        # 解析ORDER BY子句
        order_by = None
        if reader.peek() == 'ORDER':
            reader.next()
            reader.match('BY')
            order_by = []
            while reader.peek() not in ('LIMIT', 'SEMI', 'eof'):
                # 处理带表名前缀的列名
                if reader.peek() == 'IDENTIFIER' and reader.peek(1) == 'DOT':
                    table_name = reader.next()[1]  # 表名
                    reader.match('DOT')  # 吃掉点
                    column_name = reader.match('IDENTIFIER')[1]  # 列名
                    col = f"{table_name}.{column_name}"
                else:
                    col = reader.match('IDENTIFIER')[1]

                direction = 'ASC'
                if reader.peek() in ('ASC', 'DESC'):
                    direction = reader.next()[0]
                order_by.append({'column': col, 'direction': direction})
                if reader.peek() == 'COMMA':
                    reader.next()

        # 解析LIMIT子句
        limit = None
        if reader.peek() == 'LIMIT':
            reader.next()
            limit = int(reader.match('NUMBER')[1])

        return {
            'type': 'select',
            'select': select_clause,
            'tables': tables,  # 多表信息
            'where': where_clause,
            'group_by': group_by,
            'order_by': order_by,
            'limit': limit
        }

    def parse_where_expression():
        """解析WHERE子句的复合条件"""
        # left = reader.match('IDENTIFIER')[1]
        # op = reader.match('OPERATOR')[0]
        # right = None
        # if reader.peek() in ('NUMBER', 'STRING'):
        #     right = reader.next()[1]
        # elif reader.peek() == 'IDENTIFIER':
        #     right = reader.next()[1]
        # else:
        #     _error(f"期望值，得到 {reader.peek()}")
        # return [left, op, right]
        return parse_logical_expression()

    def parse_logical_expression():
        """解析由AND/OR连接的逻辑表达式"""
        left = parse_primary_condition()
        while reader.peek() in ('AND', 'OR'):
            op = reader.next()[0]  # 获取逻辑运算符
            right = parse_primary_condition()
            left = {'logical_op': op, 'left': left, 'right': right}
        return left

    def parse_primary_condition():
        """解析基础条件或括号内的表达式（支持带表别名的列名）"""
        if reader.peek() == 'LPAREN':
            reader.next()  # 吃掉 '('
            expr = parse_logical_expression()
            reader.match('RPAREN')  # 吃掉 ')'
            return expr
        else:
            # 解析左值（支持带表别名的列名）
            left_parts = []
            while True:
                if reader.peek() == 'IDENTIFIER':
                    left_parts.append(reader.next()[1])
                else:
                    break

                if reader.peek() == 'DOT':
                    reader.next()  # 吃掉点号
                else:
                    break

            left = '.'.join(left_parts)

            # 读取操作符
            op_token = reader.current_val
            op = None
            if op_token[1] == 'OPERATOR':
                op = op_token[0]
                reader.next()  # 吃掉操作符
            else:
                _error(f"期望操作符，得到 {op_token[0]}")

            # 解析右值（支持带表别名的列名）
            # 根据token类型分别处理
            if reader.peek() == 'NUMBER':
                # 数字字面量 - 保留原始数值
                token = reader.next()
                right = token[1]  # 直接使用数字值（int或float）
            elif reader.peek() == 'STRING':
                # 字符串字面量 - 保留原始字符串
                token = reader.next()
                right = token[1]
            elif reader.peek() == 'IDENTIFIER':
                # 标识符，可能是带表别名的列名
                right_parts = []
                while True:
                    if reader.peek() == 'IDENTIFIER':
                        right_parts.append(reader.next()[1])
                    else:
                        break

                    if reader.peek() == 'DOT':
                        reader.next()  # 吃掉点号
                    else:
                        break

                right = '.'.join(right_parts)
            else:
                _error(f"期望值或列名，得到 {reader.peek()}")

            return {'left': left, 'op': op, 'right': right}

    def parse_aggregate_function():
        """聚合函数解析"""
        func_name = reader.next()[0]
        reader.match('LPAREN')  # 吃掉 (

        # 处理可能存在的DISTINCT关键字
        distinct = False
        if reader.peek() == 'DISTINCT':
            distinct = True
            reader.next()  # 吃掉DISTINCT

        # 解析参数（列名或*）
        if reader.peek() == 'ASTERISK':
            arg = '*'
            reader.next()
        else:
            arg = reader.match('IDENTIFIER')[1]

        reader.match('RPAREN')  # 吃掉 )

        # 处理AS子句
        alias = None
        if reader.peek() == 'AS':
            reader.next()
            alias = reader.match('IDENTIFIER')[1]

        return {
            'name': func_name,
            'arg': arg,
            'alias': alias,
            'distinct': distinct  # 保留在聚合函数中的distinct字段
        }

    def parse_delete():
        """解析DELETE FROM语句"""
        reader.match('FROM')  # 吃掉 FROM
        table_name = reader.match('IDENTIFIER')[1]
        # 解析WHERE条件
        where_clause = None
        if reader.peek() == 'WHERE':
            reader.next()  # 吃掉 WHERE
            where_clause = parse_where_expression()
            #where_clause = parse_expression()
        return {'type': 'delete', 'table': table_name, 'where': where_clause}

    def parse_update():
        """UPDATE语句"""
        table_name = reader.match('IDENTIFIER')[1]
        reader.match('SET')

        # 解析赋值列表
        assignments = []
        while reader.peek() not in ('WHERE', 'SEMI', 'eof'):
            column = reader.match('IDENTIFIER')[1]
            reader.match('EQ')
            expr = parse_expression()  # 解析表达式
            assignments.append({'column': column, 'expr': expr})
            if reader.peek() == 'COMMA':
                reader.next()  # 跳过逗号
            else:
                break  # 无逗号则结束

        # 解析WHERE子句
        where_clause = None
        if reader.peek() == 'WHERE':
            reader.next()
            where_clause = parse_where_expression()

        return {
            'type': 'update',
            'table': table_name,
            'assignments': assignments,
            'where': where_clause
        }

    def parse_drop():
        """解析DROP TABLE语句"""
        reader.match('TABLE')  # 吃掉 TABLE
        table_name = reader.match('IDENTIFIER')[1]
        return {'type': 'drop_table', 'name': table_name}

    return parser()  # 开始执行



# ===== SQL解释器 语义分析+解释执行 =====

class SQLInterpreter:
    def __init__(self):
        self.tables = {}  # 表结构存储
        self.current_db = "main"  # 支持多数据库扩展

    def execute(self, ast):
        # 解释器执行入口
        results = []
        for statement in ast:  # 支持批量执行多个SQL语句
            try:
                # 根据AST类型分发处理
                if statement['type'] == 'create_table':
                    self._create_table(statement)
                    results.append("表创建成功")
                elif statement['type'] == 'insert':
                    self._insert(statement)
                    results.append("插入成功")
                elif statement['type'] == 'select':
                    result = self._select(statement)
                    results.append(('select', result))
                elif statement['type'] == 'delete':
                    self._delete(statement)
                    results.append("删除成功")
                elif statement['type'] == 'update':
                    self._update(statement)
                    results.append("更新成功")
                elif statement['type'] == 'drop_table':
                    self._drop_table(statement)
                    results.append("表删除成功")
                else:
                    raise Exception(f"不支持的语句类型: {statement['type']}")
            except Exception as e:
                results.append(('error', str(e)))
        return results

    def _create_table(self, statement):
        """
        表创建实现
        支持INT/VARCHAR数据类型
        处理PRIMARY KEY/NOT NULL/UNIQUE约束
        列级数据校验规则存储
        :param statement: 语句create_table的语法树节点
        """
        table_name = statement['name']
        # 确保表名唯一
        if table_name in self.tables:
            raise Exception(f"表 '{table_name}' 已存在")

        # 初始化表的数据结构，包含列定义、主键信息和数据存储
        table = {
            'columns': {},
            'primary_key': None,
            'data': []
        }
        # 遍历语句中的每个列，提取列名、数据类型和约束
        for column in statement['columns']:
            col_name = column['name']
            col_type = column['type']
            constraints = column['constraints']  # 约束：如 PRIMARY KEY、NOT NULL、UNIQUE，存储在列表中。

            table['columns'][col_name] = {
                'type': col_type,
                'constraints': constraints
            }
            # 处理主键约束
            if 'PRIMARY KEY' in constraints:
                if table['primary_key'] is not None:
                    raise Exception(f"表 '{table_name}' 只能有一个主键")
                table['primary_key'] = col_name  # 记录此表的主键

        self.tables[table_name] = table  # 保存表

    def _insert(self, statement):
        """
        处理 INSERT 语句，将数据插入数据库表中，包含以下关键步骤
        """
        # 从 AST 中提取表名和插入值列表
        table_name = statement['table']
        values = statement['values']

        if table_name not in self.tables:
            raise Exception(f"表 '{table_name}' 不存在")


        table = self.tables[table_name]  # 获取对应表信息
        columns = list(table['columns'].keys())  # 获取表中各列名称(关键字)
        if len(values) != len(columns):  # 确保插入值的数量与表的列数严格一致
            raise Exception(f"插入的值数量({len(values)})与表 '{table_name}' 的列数({len(columns)})不匹配")

        # 按列顺序构建数据行
        row = {}
        for i, value in enumerate(values):
            col_name = columns[i]  # 列名
            col_def = table['columns'][col_name]  # 此列的数据类型, 约束

            # 类型检查
            if 'INT' in col_def['type'] and not isinstance(value, int):
                try:
                    value = int(value)
                except:
                    raise Exception(f"列 '{col_name}' 要求整数类型，得到 '{type(value).__name__}'")

            # 非空检查
            if 'NOT NULL' in col_def['constraints'] and value is None or value == '':
                raise Exception(f"列 '{col_name}' 不能为NULL")

            # 主键唯一性检查
            if col_name == table['primary_key'] and value in [r[col_name] for r in table['data']]:
                raise Exception(f"主键 '{col_name}' 的值必须唯一")

            # UNIQUE约束检查
            if 'UNIQUE' in col_def['constraints'] and value in [r[col_name] for r in table['data']]:
                raise Exception(f"列 '{col_name}' 的值必须唯一")

            row[col_name] = value

        table['data'].append(row)

    def _select(self, statement):
        """
        SELECT 查找语句实现（多表支持）
        """

        # 辅助函数：解析列名，返回带表别名前缀的列名
        def resolve_col_name(col_name, tables_info, row):
            # 如果列名已经包含点（即带有表别名），则直接返回
            if '.' in col_name:
                return col_name
            # 否则，尝试在所有表的别名中查找
            for table_info in tables_info:
                alias = table_info['alias'] or table_info['name']
                prefixed = f"{alias}.{col_name}"
                if prefixed in row:
                    return prefixed
            # 如果找不到，返回原始列名
            return col_name


        # 从statement中获取tables列表
        tables_info = statement['tables']
        select_clause = statement['select']
        where_clause = statement['where']
        group_by = statement.get('group_by', []) or []
        order_by = statement.get('order_by', None)
        limit = statement.get('limit', None)

        # 验证所有表都存在
        for table_info in tables_info:
            table_name = table_info['name']
            if table_name not in self.tables:
                raise Exception(f"表 '{table_name}' 不存在")

        # 创建笛卡尔积
        cartesian_product = [{}]  # 起始空行

        # 为每个表添加前缀
        for table_info in tables_info:
            table_name = table_info['name']
            alias = table_info['alias'] or table_name
            table_data = self.tables[table_name]['data']
            new_product = []

            for row in table_data:
                # 创建带表前缀的行
                prefixed_row = {}
                for col_name, value in row.items():
                    prefixed_row[f"{alias}.{col_name}"] = value

                # 添加到笛卡尔积
                for existing in cartesian_product:
                    new_row = existing.copy()
                    new_row.update(prefixed_row)
                    new_product.append(new_row)

            cartesian_product = new_product

        # WHERE 条件过滤
        if where_clause:
            filtered_rows = self._filter_rows(tables_info, cartesian_product, where_clause)
        else:
            filtered_rows = cartesian_product

        # 分组处理
        # 解析 group_by 中的列名为带表名前缀的列名
        resolved_group_by = []
        if group_by and filtered_rows:  # 确保有数据行可用
            first_row = filtered_rows[0]  # 使用第一行来解析列名
            for col in group_by:
                resolved_col = resolve_col_name(col, tables_info, first_row)
                resolved_group_by.append(resolved_col)
        else:
            resolved_group_by = group_by  # 如果没有分组列，保持原样

        grouped_data = {}
        has_aggregate = self._contains_aggregate(select_clause)

        if resolved_group_by:  # 使用解析后的分组列
            # 处理带表前缀的分组键
            for row in filtered_rows:
                key = tuple(row[col] for col in resolved_group_by)
                if key not in grouped_data:
                    grouped_data[key] = []
                grouped_data[key].append(row)
        elif has_aggregate:
            # 聚合查询但没有GROUP BY，视为一个分组
            grouped_data[()] = filtered_rows
        else:
            # 没有分组也没有聚合，每行单独处理
            for i, row in enumerate(filtered_rows):
                grouped_data[(i,)] = [row]

        # 处理SELECT列
        result = []
        for group_key, group_rows in grouped_data.items():
            # 处理聚合函数
            agg_results = self._apply_aggregate_functions(
                tables_info,
                group_rows,
                [col for col in select_clause['columns']
                 if isinstance(col, dict) and col['name'] in ('COUNT', 'SUM', 'AVG', 'MIN', 'MAX')]
            )

            # 构建结果行
            result_row = {}

            # 添加分组列
            if group_by:
                for i, col in enumerate(group_by):
                    # 解析分组列名
                    full_col_name = resolve_col_name(col, tables_info, group_rows[0])
                    result_row[col] = group_rows[0].get(full_col_name)

                    # 添加聚合结果
            if agg_results:
                result_row.update(agg_results[0])

            # 添加普通列
            for col in select_clause['columns']:
                if col == '*':  # 处理通配符
                    for table_info in tables_info:
                        alias = table_info['alias'] or table_info['name']
                        table_cols = self.tables[table_info['name']]['columns'].keys()
                        for col_name in table_cols:
                            prefixed = f"{alias}.{col_name}"
                            result_row[prefixed] = group_rows[0].get(prefixed)
                elif isinstance(col, dict):  # 聚合函数或带别名的列
                    if col['name'] not in ('COUNT', 'SUM', 'AVG', 'MIN', 'MAX'):  # 普通列
                        # 解析列名
                        full_col_name = resolve_col_name(col['name'], tables_info, group_rows[0])
                        alias = col.get('alias')
                        if alias:
                            result_row[alias] = group_rows[0].get(full_col_name)
                        else:
                            result_row[col['name']] = group_rows[0].get(full_col_name)
                else:  # 简单列名
                    # 解析列名
                    full_col_name = resolve_col_name(col, tables_info, group_rows[0])
                    result_row[col] = group_rows[0].get(full_col_name)

            result.append(result_row)

        # 处理DISTINCT
        if select_clause.get('distinct', False):
            seen = set()
            distinct_result = []
            for row in result:
                # 使用所有列创建元组
                row_tuple = tuple(row.items())
                if row_tuple not in seen:
                    seen.add(row_tuple)
                    distinct_result.append(row)
            result = distinct_result

        # ORDER BY排序
        if order_by:
            def get_sort_key(row):
                keys = []
                for order in order_by:
                    col = order['column']
                    # 尝试查找带前缀的列
                    if '.' not in col:
                        found = False
                        for table_info in tables_info:
                            alias = table_info['alias'] or table_info['name']
                            prefixed = f"{alias}.{col}"
                            if prefixed in row:
                                keys.append(row[prefixed])
                                found = True
                                break
                        if not found:
                            keys.append(row.get(col))
                    else:
                        keys.append(row.get(col))
                return keys

            reverse_flag = any(order['direction'] == 'DESC' for order in order_by)
            result = sorted(result, key=get_sort_key, reverse=reverse_flag)

        # LIMIT限制
        if limit is not None:
            result = result[:limit]

        return result
    def _contains_aggregate(self, select_clause):
        """检查SELECT子句是否包含聚合函数"""
        return any(
            isinstance(col, dict) and
            col.get('name') in ('COUNT', 'SUM', 'AVG', 'MIN', 'MAX')
            for col in select_clause['columns']
        )

    def _apply_aggregate_functions(self, tables_info, rows, columns):
        """处理聚合函数（多表支持）"""

        # 获取所有表的别名
        table_aliases = [table_info['alias'] for table_info in tables_info]

        def resolve_column_name(col_name):
            """解析列名，添加表别名前缀"""
            if '.' in col_name:
                return col_name

            for alias in table_aliases:
                prefixed_name = f"{alias}.{col_name}"
                if any(prefixed_name in row for row in rows):
                    return prefixed_name

            return col_name

        result = [{}]  # 初始化结果集

        for col in columns:
            if not isinstance(col, dict):
                continue

            func_name = col['name']
            arg = resolve_column_name(col['arg'])  # 解析聚合函数参数
            alias = col.get('alias', f"{func_name}({arg})")
            distinct = col.get('distinct', False)  # 获取DISTINCT标志

            # 查找带表前缀的列
            values = []
            for row in rows:
                # 优先查找带前缀的列
                if '.' in arg:
                    value = row.get(arg)
                else:
                    # 尝试所有可能的表前缀
                    for table_info in tables_info:
                        table_alias = table_info['alias'] or table_info['name']
                        prefixed = f"{table_alias}.{arg}"
                        if prefixed in row:
                            value = row[prefixed]
                            break
                    else:
                        value = row.get(arg)  # 最后尝试无前缀
                if value is not None:
                    values.append(value)

            # 如果指定了DISTINCT，则去重
            if distinct:
                # 使用集合去重（注意：值必须是可哈希的）
                try:
                    distinct_values = set(values)
                    values = list(distinct_values)
                except TypeError:
                    # 如果值不可哈希（如列表），则使用另一种方式去重
                    seen = set()
                    distinct_values = []
                    for v in values:
                        # 使用元组表示不可哈希的值
                        key = tuple(v) if isinstance(v, list) else v
                        if key not in seen:
                            seen.add(key)
                            distinct_values.append(v)
                    values = distinct_values

            # 处理COUNT函数
            if func_name == 'COUNT':
                if arg == '*':
                    result[0][alias] = len(rows)
                else:
                    result[0][alias] = len(values)  # 使用去重后的值

            # 处理其他聚合函数
            elif func_name in ('SUM', 'AVG', 'MIN', 'MAX'):
                if not values:
                    result[0][alias] = None
                    continue

                try:
                    numeric_values = [float(v) for v in values if v is not None]
                except ValueError:
                    result[0][alias] = None
                    continue

                if not numeric_values:
                    result[0][alias] = None
                elif func_name == 'SUM':
                    result[0][alias] = sum(numeric_values)
                elif func_name == 'AVG':
                    result[0][alias] = sum(numeric_values) / len(numeric_values)
                elif func_name == 'MIN':
                    result[0][alias] = min(numeric_values)
                elif func_name == 'MAX':
                    result[0][alias] = max(numeric_values)

        return result

    def _filter_rows(self, tables_info, rows, where_clause):

        # 获取所有表的别名
        table_aliases = [table_info['alias'] for table_info in tables_info]

        def resolve_column_name(col_name, tables_info, row):
            """解析列名，添加表别名前缀"""
            # 如果列名已经包含点（即带有表别名），则直接返回
            if '.' in col_name:
                return col_name
            # 否则，尝试在所有表的别名中查找
            for table_info in tables_info:
                alias = table_info['alias'] or table_info['name']
                prefixed = f"{alias}.{col_name}"
                if prefixed in row:
                    return prefixed
            # 如果找不到，返回原始列名
            return col_name

        def evaluate_condition(row, condition):
            # 解析左值（添加表别名前缀）
            left = resolve_column_name(condition['left'], tables_info, row)
            op = condition['op']
            right = condition['right']

            left_value = row.get(left)

            # 处理右值
            # 如果右值是字符串，并且不包含点号，尝试解析为列名
            if isinstance(right, str) and '.' not in right:
                # 尝试解析为列名
                resolved_right = resolve_column_name(right, tables_info, row)
                # 如果解析后的列名在行中存在，则使用列值
                if resolved_right in row:
                    right_value = row[resolved_right]
                else:
                    # 否则，视为字符串字面量
                    right_value = right
            elif isinstance(right, str) and '.' in right:
                # 如果右值包含点号，直接作为列名处理
                right_value = row.get(right)
            else:
                # 其他类型（数字等）直接使用
                right_value = right

            # 类型检查和转换
            if op in ['LT', 'LTE', 'GT', 'GTE']:
                # 确保比较的是数字类型
                try:
                    if left_value is not None:
                        left_value = float(left_value)
                    if right_value is not None:
                        right_value = float(right_value)
                except (TypeError, ValueError):
                    raise Exception(f"操作符 {op} 要求数字类型, 但得到 {type(left_value)} 和 {type(right_value)}")

            # 执行比较操作
            if op == 'EQ':
                return left_value == right_value
            elif op == 'NEQ':
                return left_value != right_value
            elif op == 'LT':
                return left_value < right_value
            elif op == 'LTE':
                return left_value <= right_value
            elif op == 'GT':
                return left_value > right_value
            elif op == 'GTE':
                return left_value >= right_value
            elif op == 'LIKE':
                import re
                # 将 SQL LIKE 模式转换为正则表达式
                pattern = re.escape(str(right_value)).replace('%', '.*').replace('_', '.')
                return re.match(f"^{pattern}$", str(left_value), re.IGNORECASE) is not None
            else:
                raise Exception(f"不支持的操作符: {op}")

        def evaluate_logical_expression(row, expr):
            if isinstance(expr, dict):
                if 'logical_op' in expr:
                    left_result = evaluate_logical_expression(row, expr['left'])
                    right_result = evaluate_logical_expression(row, expr['right'])
                    if expr['logical_op'] == 'AND':
                        return left_result and right_result
                    elif expr['logical_op'] == 'OR':
                        return left_result or right_result
                else:
                    return evaluate_condition(row, expr)
            return expr

        return [row for row in rows if evaluate_logical_expression(row, where_clause)]

    def _evaluate_condition(self, row, condition, tables):
        """递归评估条件表达式"""
        if 'logical_op' in condition:
            # 递归评估左侧表达式
            left = self._evaluate_condition(row, condition['left'], tables)
            # 递归评估右侧表达式
            right = self._evaluate_condition(row, condition['right'], tables)
            # 应用逻辑运算
            if condition['logical_op'] == 'AND':
                return left and right
            elif condition['logical_op'] == 'OR':
                return left or right
            else:
                raise Exception(f"未知逻辑运算符: {condition['logical_op']}")
        # 处理基本比较条件
        else:
            # 处理带表名前缀的列名
            left_val = self._get_column_value(row, condition['left'], tables)
            right_val = self._parse_condition_value(row, condition['right'], tables)
            op = condition['op']

            # 处理各操作符
            if op == 'EQ':
                return left_val == right_val
            elif op == 'NEQ':
                return left_val != right_val
            elif op == 'LT':
                return left_val < right_val
            elif op == 'LTE':
                return left_val <= right_val
            elif op == 'GT':
                return left_val > right_val
            elif op == 'GTE':
                return left_val >= right_val
            elif op == 'LIKE':
                import re
                pattern = re.escape(str(right_val)).replace('%', '.*').replace('_', '.')
                return re.match(pattern, str(left_val), re.IGNORECASE) is not None
            else:
                raise Exception(f"不支持的操作符: {op}")

    def _get_column_value(self, row, column_name, tables):
        """获取列值（支持带表名前缀的列名）"""
        # 如果有显式的表名前缀
        if '.' in column_name:
            return row.get(column_name)

        # 没有前缀时，尝试在所有表中查找
        values = []
        for table in tables:
            alias = table['alias']
            prefixed_name = f"{alias}.{column_name}"
            if prefixed_name in row:
                values.append(row[prefixed_name])

        if len(values) == 1:
            return values[0]
        elif len(values) > 1:
            raise Exception(f"列名 '{column_name}' 存在歧义，请使用表名前缀")
        else:
            return None

    def _parse_condition_value(self, row, value, table):
        """解析条件的右值（可能是列名或字面量）"""
        if isinstance(value, str) and value in table['columns']:
            return row.get(value)  # 引用其他列的值
        try:
            return int(value)  # 尝试转为整数
        except:
            try:
                return float(value)  # 尝试转为浮点数
            except:
                return str(value).strip("'")  # 字符串字面量


    def _delete(self, statement):
        """DELETE语句"""
        table_name = statement['table']
        where_clause = statement['where']

        if table_name not in self.tables:
            raise Exception(f"表 '{table_name}' 不存在")

        table = self.tables[table_name]
        old_len = len(table['data'])

        if where_clause:
            # 修复：创建正确的 tables_info 结构
            tables_info = [{
                'name': table_name,
                'alias': table_name  # 使用表名作为别名
            }]
            rows_to_delete = self._filter_rows(tables_info, table['data'], where_clause)
            table['data'] = [row for row in table['data'] if row not in rows_to_delete]
        else:
            table['data'] =  []

        if old_len == len(table['data']):
            raise Exception(f"删除失败, 未找到符合的记录 ")

    def _update(self, statement):
        table_name = statement['table']
        assignments = statement['assignments']
        where_clause = statement['where']

        if table_name not in self.tables:
            raise Exception(f"表 '{table_name}' 不存在")

        table = self.tables[table_name]
        columns = list(table['columns'].keys())

        # 验证所有要更新的列都存在
        for assignment in assignments:
            col_name = assignment['column']
            if col_name not in columns:
                raise Exception(f"列 '{col_name}' 不存在于表 '{table_name}' 中")

        # 确定要更新的行
        rows_to_update = table['data']
        if where_clause:
            # 修复：创建正确的 tables_info 结构
            tables_info = [{
                'name': table_name,
                'alias': table_name  # 使用表名作为别名
            }]
            rows_to_update = self._filter_rows(tables_info, rows_to_update, where_clause)
            if len(rows_to_update) == 0:
                raise Exception(f"更新失败, 未找到符合的记录 ")

        # 更新行
        for row in rows_to_update:
            for assignment in assignments:
                col_name = assignment['column']
                expr = assignment['expr']
                new_value = self.evaluate_expression(row, expr)
                col_def = table['columns'][col_name]

                # 类型检查
                if 'INT' in col_def['type'] and not isinstance(new_value, int):
                    try:
                        new_value = int(new_value)
                    except:
                        raise Exception(f"列 '{col_name}' 要求整数类型，得到 '{type(new_value).__name__}'")

                # 非空检查
                if 'NOT NULL' in col_def['constraints'] and new_value is None:
                    raise Exception(f"列 '{col_name}' 不能为NULL")

                # 主键唯一性检查（如果更新主键）
                if col_name == table['primary_key']:
                    if new_value in [r[col_name] for r in table['data'] if r is not row]:
                        raise Exception(f"更新后的主键值 '{new_value}' 已存在")

                # UNIQUE约束检查
                if 'UNIQUE' in col_def['constraints']:
                    if new_value in [r[col_name] for r in table['data'] if r is not row]:
                        raise Exception(f"更新后的列 '{col_name}' 值必须唯一")

                row[col_name] = new_value

    def evaluate_expression(self, row, expr):
        """计算表达式值，支持基本二元运算"""
        if len(expr) == 1:
            # 单个操作数（列名、数值或字符串）
            token = expr[0]
            if isinstance(token, (int, float)):
                return token
            elif isinstance(token, str):
                return row.get(token, token)  # 列名或字符串
            else:
                raise Exception(f"无效的表达式token: {token}")
        elif len(expr) == 3:
            # 二元运算（例如：age + 1）
            left, op, right = expr
            left_val = self._get_operand_value(row, left)
            right_val = self._get_operand_value(row, right)
            return self._apply_operator(op, left_val, right_val)
        else:
            raise Exception("暂不支持复杂表达式")

    def _get_operand_value(self, row, operand):
        """获取操作数值（列值或字面量）"""
        if isinstance(operand, (int, float)):
            return operand
        elif isinstance(operand, str):
            return row.get(operand, operand)  # 列名或字符串字面量
        else:
            raise Exception(f"无效的操作数: {operand}")

    def _apply_operator(self, op, a, b):
        """应用运算符"""
        if op == 'PLUS':
            return a + b
        elif op == 'MINUS':
            return a - b
        elif op == 'ASTERISK':
            return a * b
        elif op == 'SLASH':
            if b == 0:
                raise Exception("除数不能为零")
            return a / b
        else:
            raise Exception(f"不支持的运算符: {op}")


    def get_table_data(self, table_name, limit=100):
        """获取表中的数据"""
        if table_name not in self.tables:
            raise Exception(f"表 '{table_name}' 不存在")

        table = self.tables[table_name]
        return table['data'][:limit]

    def insert_row(self, table_name, values):
        """插入新行"""
        if table_name not in self.tables:
            raise Exception(f"表 '{table_name}' 不存在")

        table = self.tables[table_name]
        columns = list(table['columns'].keys())

        if len(values) != len(columns):
            raise Exception(f"插入的值数量({len(values)})与表 '{table_name}' 的列数({len(columns)})不匹配")

        row = {}
        for i, value in enumerate(values):
            col_name = columns[i]
            col_def = table['columns'][col_name]

            # 类型检查
            if 'INT' in col_def['type'] and value != '':
                try:
                    value = int(value)
                except:
                    raise Exception(f"列 '{col_name}' 要求整数类型，得到 '{type(value).__name__}'")

            # 非空检查
            if 'NOT NULL' in col_def['constraints'] and (value is None or value == ''):
                raise Exception(f"列 '{col_name}' 不能为NULL")

            # 主键唯一性检查
            if col_name == table['primary_key'] and value in [r[col_name] for r in table['data']]:
                raise Exception(f"主键 '{col_name}' 的值必须唯一")

            # UNIQUE约束检查
            if 'UNIQUE' in col_def['constraints'] and value in [r[col_name] for r in table['data']]:
                raise Exception(f"列 '{col_name}' 的值必须唯一")

            row[col_name] = value if value != '' else None

        table['data'].append(row)
        return row

    def update_row(self, table_name, primary_key_value, updates):
        """更新行"""
        if table_name not in self.tables:
            raise Exception(f"表 '{table_name}' 不存在")

        table = self.tables[table_name]
        primary_key = table['primary_key']

        if not primary_key:
            raise Exception(f"表 '{table_name}' 没有主键，无法更新")

        # 获取主键列的数据类型
        col_def = table['columns'][primary_key]
        data_type = col_def['type']
        # 根据数据类型转换主键值
        try:
            if 'INT' in data_type:
                primary_key_value = int(primary_key_value)
            elif 'VARCHAR' in data_type:
                primary_key_value = str(primary_key_value)
            # 可根据需要添加其他数据类型转换
        except ValueError:
            raise Exception(f"主键值 '{primary_key_value}' 无法转换为列 '{primary_key}' 的类型 {data_type}")

        for row in table['data']:
            if row[primary_key] == primary_key_value:
                for col_name, value in updates.items():
                    if col_name not in table['columns']:
                        raise Exception(f"列 '{col_name}' 不存在于表 '{table_name}' 中")

                    col_def = table['columns'][col_name]

                    # 类型检查
                    if 'INT' in col_def['type'] and value != '':
                        try:
                            value = int(value)
                        except:
                            raise Exception(f"列 '{col_name}' 要求整数类型，得到 '{type(value).__name__}'")

                    # 非空检查
                    if 'NOT NULL' in col_def['constraints'] and (value is None or value == ''):
                        raise Exception(f"列 '{col_name}' 不能为NULL")

                    # 主键唯一性检查
                    if col_name == primary_key and value != primary_key_value:
                        if value in [r[primary_key] for r in table['data'] if r[primary_key] != primary_key_value]:
                            raise Exception(f"更新后的主键值 '{value}' 已存在")

                    # UNIQUE约束检查
                    if 'UNIQUE' in col_def['constraints'] and value != row[col_name]:
                        if value in [r[col_name] for r in table['data'] if r[primary_key] != primary_key_value]:
                            raise Exception(f"更新后的列 '{col_name}' 值必须唯一")

                    row[col_name] = value if value != '' else None
                return True

        raise Exception(f"找不到主键值为 '{primary_key_value}' 的行")

    def delete_row(self, table_name, primary_key_value):
        """删除行"""
        if table_name not in self.tables:
            raise Exception(f"表 '{table_name}' 不存在")


        table = self.tables[table_name]
        primary_key = table['primary_key']

        if not primary_key:
            raise Exception(f"表 '{table_name}' 没有主键，无法删除")

        # 获取主键列的数据类型
        col_def = table['columns'][primary_key]
        data_type = col_def['type']

        # 根据数据类型转换主键值
        try:
            if 'INT' in data_type:
                primary_key_value = int(primary_key_value)
            elif 'VARCHAR' in data_type:
                primary_key_value = str(primary_key_value)
            # 可根据需要添加其他数据类型转换
        except ValueError:
            raise Exception(f"主键值 '{primary_key_value}' 无法转换为列 '{primary_key}' 的类型 {data_type}")

        original_len = len(table['data'])
        # 过滤掉主键等于指定值的行
        table['data'] = [row for row in table['data'] if row[primary_key] != primary_key_value]

        if len(table['data']) == original_len:
            raise Exception(f"找不到主键值为 '{primary_key_value}' 的行")

        return True

    def _drop_table(self, statement):
        """表删除实现"""
        table_name = statement['name']
        if table_name not in self.tables:
            raise Exception(f"表 '{table_name}' 不存在")
        del self.tables[table_name]


"""测试"""

sql = """
    SELECT * 
    FROM users 
    WHERE age > 25 AND (name LIKE 'A%' OR email LIKE '%example.com');
"""

test_tokens = sql_lexer(sql)
print(f"Token列表:\n{test_tokens}")

test_ast = sql_parser(test_tokens)
print("")
print(f"AST:\n{test_ast}")


"""

age | id | name     | email                 |     
28  | 1  | Alice    | alice@example.com     |   
30  | 2  | Bob      | bob@example.com       |   
35  | 3  | Charlie  | charlie@example.com   |   


id |name  |age | email                 |     
1  |Alice |28  | alice@example.com     |  

"""




"""
def consume(tokens, expected_type, expected_value):
    if not tokens:
   	    raise SyntaxError("Unexpected end of statement")
    token = tokens[0]
    if token.type != expected_type or token.value != expected_value:
   	    line, col = get_token_position(token)  # 获取Token位置
    raise SyntaxError(f"Line {line}, Column {col}: Expected {expected_value}, got {token.value}")
    tokens.pop(0)
    return token






"""