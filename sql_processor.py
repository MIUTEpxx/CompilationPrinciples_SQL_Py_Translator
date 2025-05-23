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
    'AVG', 'MIN', 'MAX', 'GROUP', 'HAVING', 'UNIQUE'
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
        while (c := reader.peek()) and (c.isalnum() or c == '_'):
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
                    constraints.append(reader.next()[1])
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
            if reader.peek() == 'ASTERISK':
                select_clause['columns'].append('*')
                reader.next()
            elif reader.peek() in ('COUNT', 'SUM', 'AVG', 'MIN', 'MAX'):
                func = parse_aggregate_function()
                select_clause['columns'].append(func)
            else:
                # 处理列名和别名
                col = reader.match('IDENTIFIER')[1]
                if reader.peek() == 'AS':
                    reader.next()
                    alias = reader.match('IDENTIFIER')[1]
                    select_clause['columns'].append({'name': col, 'alias': alias})
                else:
                    select_clause['columns'].append(col)
            if reader.peek() == 'COMMA':
                reader.next()

        reader.match('FROM')
        table_name = reader.match('IDENTIFIER')[1]

        # 解析WHERE子句
        where_clause = None
        if reader.peek() == 'WHERE':
            reader.next()
            where_clause = parse_where_expression()

        # 解析GROUP BY子句（新增部分）
        group_by = None
        if reader.peek() == 'GROUP':
            reader.next()  # 吃掉GROUP
            reader.match('BY')  # 吃掉BY
            group_by = []
            while reader.peek() not in ('HAVING', 'ORDER', 'LIMIT', 'SEMI', 'eof'):
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
            'table': table_name,
            'where': where_clause,
            'group_by': group_by,  # 新增group_by字段
            'order_by': order_by,
            'limit': limit
        }

    def parse_where_expression():
        left = reader.match('IDENTIFIER')[1]
        op = reader.match('OPERATOR')[0]
        right = None
        if reader.peek() in ('NUMBER', 'STRING'):
            right = reader.next()[1]
        elif reader.peek() == 'IDENTIFIER':
            right = reader.next()[1]
        else:
            _error(f"期望值，得到 {reader.peek()}")
        return [left, op, right]

    def parse_aggregate_function():
        """聚合函数解析"""
        func_name = reader.next()[0]
        reader.match('LPAREN')   # 吃掉 (

        # 处理可能存在的DISTINCT关键字
        distinct = False
        if reader.peek() == 'DISTINCT':
            reader.next()  # 吃掉DISTINCT
            distinct = True

        # 解析参数（列名或*）
        if reader.peek() == 'ASTERISK':
            arg = '*'
            reader.next()
        else:
            arg = reader.match('IDENTIFIER')[1]
        reader.match('RPAREN')   # 吃掉 )

        # 处理AS子句
        alias = None
        if reader.peek() == 'AS':
            reader.next()
            alias = reader.match('IDENTIFIER')[1]

        return {
            'name': func_name,
            'arg': arg,
            'alias': alias,
            'distinct': distinct  # 添加distinct字段
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
        while reader.peek() != 'WHERE' and reader.peek() != 'SEMI':
            column = reader.match('IDENTIFIER')[1]
            reader.match('EQ')
            value = -1
            if reader.peek() in ('NUMBER', 'STRING'):
                value = reader.next()[1]
            else:
                _error(f"期望值，得到 {reader.peek()}")
            assignments.append({'column': column, 'value': value})
            if reader.peek() == 'COMMA':
                reader.next()

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

    return parser()  # 开始执行



# ===== 数据库解释器 =====
class Database:
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
            if 'NOT NULL' in col_def['constraints'] and value is None:
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
        SELECT 查找语句实现
        """
        # 参数提取
        table_name = statement['table']  # 要查找的表名
        select_clause = statement['select']   # SELECT子句
        where_clause = statement['where']  # WHERE条件
        order_by = statement['order_by']
        group_by = statement.get('group_by', []) or []  # 强制保证是列表类型
        limit = statement['limit']

        if table_name not in self.tables:
            raise Exception(f"表 '{table_name}' 不存在")

        # 获取表结构和列名 第一步：from语句，选择要操作的表
        table = self.tables[table_name]
        columns = list(table['columns'].keys())

        # WHERE 条件过滤数据行 第二步：where语句，在from后的表中设置筛选条件，筛选出符合条件的记录。
        filtered_rows = table['data']
        if where_clause:
            filtered_rows = self._filter_rows(table, filtered_rows, where_clause)

        # 分组处理逻辑  第三步：group by语句，把筛选出的记录进行分组 顺序不对
        grouped_data = {}
        if group_by:
            # 按分组键建立字典
            for row in filtered_rows:
                key = tuple(row[col] for col in group_by)
                if key not in grouped_data:
                    grouped_data[key] = []
                grouped_data[key].append(row)
        else:
            # 无分组时视为一个组
            grouped_data[()] = filtered_rows

        # 第四步：处理 SELECT 列（包含聚合函数）
        result = []
        for group_key, group_rows in grouped_data.items():
            result_row = {}

            # 添加分组列
            for i, col_name in enumerate(group_by):
                result_row[col_name] = group_key[i]

            # 处理SELECT中的每个列（包含聚合）
            for col in select_clause['columns']:
                if isinstance(col, dict) and 'name' in col and col['name'] in ('COUNT', 'SUM', 'AVG', 'MIN', 'MAX'):
                    # 处理聚合函数
                    agg_result = self._apply_aggregate_functions(table, group_rows, [col])
                    result_row.update(agg_result[0])
                else:
                    # 处理普通列（必须是分组列）
                    col_name = col['name'] if isinstance(col, dict) else col
                    if col_name == '*':
                        result_row.update(group_rows[0])
                    else:
                        result_row[col_name] = group_rows[0][col_name]

            result.append(result_row)

        # 第五步：处理DISTINCT
        if select_clause['distinct']:
            seen = set()
            unique_result = []
            for row in result:
                row_tuple = tuple(sorted((k, v) for k, v in row.items() if k in select_clause['columns']))
                if row_tuple not in seen:
                    seen.add(row_tuple)
                    unique_result.append(row)
            result = unique_result


        #  ORDER BY排序  第六步：order by语句：将select后的结果集按照顺序展示出来 顺序不对
        if order_by:
            # 判断是否有DESC排序（当前逻辑错误：只要有一个DESC就整体逆序）
            reverse_flag = any(order['direction'] == 'DESC' for order in order_by)
            # 排序键为所有排序字段的值
            result = sorted(result,
                            key=lambda x: [x[order['column']] for order in order_by],
                            reverse=reverse_flag)

            # 逻辑错误：只要有一个DESC就整体逆序
            # result = sorted(result, key=lambda x: [
            #     x[order['column']] for order in order_by
            # ], reverse=any(order['direction'] == 'DESC' for order in order_by))


        #  LIMIT限制结果数量  # 第七步：LIMIT 限制
        if limit is not None:
            result = result[:limit]

        return result

    def _apply_aggregate_functions(self, table, rows, columns):
        """处理聚合函数（如 COUNT、SUM、AVG DISTINCT等）"""
        result = [{}]  # 初始化结果集（每个聚合函数一个结果行）

        # 遍历所有选择列（可能是普通列或聚合函数）
        for col in columns:
            # 检查是否为聚合函数（COUNT/SUM/AVG/MIN/MAX）
            if isinstance(col, dict) and 'name' in col and col['name'] in ('COUNT', 'SUM', 'AVG', 'MIN', 'MAX'):
                func = col
                distinct = func.get('distinct', False)
                func_name = col['name']  # 获取函数名（如COUNT）
                arg = col['arg']    # 获取参数（如* 或列名）
                alias = col.get('alias', f"{func_name}({arg})")  # 获取或生成别名 AS xxx

                # 处理DISTINCT：对数据进行去重
                distinct_values = []
                if distinct:
                    seen = set()
                    for row in rows:
                        val = row.get(arg)
                        if val is None:
                            continue
                        if val not in seen:
                            seen.add(val)
                            distinct_values.append(val)
                    data_source = distinct_values
                else:
                    data_source = [row.get(arg) for row in rows if arg in row]

                # 处理COUNT函数
                if func_name == 'COUNT':
                    if arg == '*':   # COUNT(*)
                        result[0][alias] = len(rows) if not distinct else len(distinct_values) # 直接计算行数
                    else:  # COUNT(列名)
                        # 统计非空值的数量
                        count = sum(1 for v in data_source if v is not None)
                        result[0][alias] = count

                # 处理SUM/AVG/MIN/MAX函数
                elif func_name in ('SUM', 'AVG', 'MIN', 'MAX'):
                    # 验证列是否存在
                    values = []
                    for row in rows:
                        val = row.get(arg)
                        if isinstance(val, (int, float)):
                            values.append(val)

                    if not values:
                        result[0][alias] = None
                        continue

                    if func_name == 'SUM':
                        result[0][alias] = sum(values)
                    elif func_name == 'AVG':
                        result[0][alias] = sum(values) / len(values)
                    elif func_name == 'MIN':
                        result[0][alias] = min(values)
                    elif func_name == 'MAX':
                        result[0][alias] = max(values)

            # # 处理普通列（在存在聚合函数时简化处理，通常应为GROUP BY列）
            # else:
            #     # 处理普通列选择（注:在聚合查询中通常不允许，但本项目进行简化实现）
            #     if isinstance(col, dict) and 'name' in col:
            #         col_name = col['name']  # 原始列名
            #         alias = col.get('alias', col_name)  # 别名处理
            #         # 取第一行的值（假设已分组）
            #         result[0][alias] = rows[0][col_name] if rows else None
            #     else:
            #         # 直接取列值（可能不符合SQL标准）
            #         result[0][col] = rows[0][col] if rows else None

        return result

    def _filter_rows(self, table, rows, where_clause):
        if len(where_clause) != 3:
            raise Exception("WHERE子句格式不正确，只支持简单的比较表达式")

        left, op, right = where_clause

        def process_value(value):
            if isinstance(value, str):
                return value
            elif isinstance(value, int):
                return value
            elif isinstance(value, list) and value[0] == 'NUMBER':
                return int(value[1])
            elif isinstance(value, list) and value[0] == 'STRING':
                return value[1]
            else:
                return value

        right_val = process_value(right)

        filtered = []
        for row in rows:
            if left not in row:
                continue

            left_val = row[left]

            if op == 'EQ':
                match = left_val == right_val
            elif op == 'NEQ':
                match = left_val != right_val
            elif op == 'LT':
                match = left_val < right_val
            elif op == 'LTE':
                match = left_val <= right_val
            elif op == 'GT':
                match = left_val > right_val
            elif op == 'GTE':
                match = left_val >= right_val
            elif op == 'LIKE':
                import re
                # 将SQL的LIKE模式转换为正则表达式
                pattern = re.escape(str(right_val)).replace('%', '.*').replace('_', '.')
                regex = re.compile(f'^{pattern}$', re.IGNORECASE)
                match = regex.match(str(left_val)) is not None
            else:
                raise Exception(f"不支持的操作符: {op}")

            if match:
                filtered.append(row)

        return filtered

    def _delete(self, statement):
        table_name = statement['table']
        where_clause = statement['where']

        if table_name not in self.tables:
            raise Exception(f"表 '{table_name}' 不存在")

        table = self.tables[table_name]

        if not where_clause:
            table['data'] = []
            return

        rows_to_delete = self._filter_rows(table, table['data'], where_clause)
        table['data'] = [row for row in table['data'] if row not in rows_to_delete]

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
            rows_to_update = self._filter_rows(table, rows_to_update, where_clause)

        # 更新行
        for row in rows_to_update:
            for assignment in assignments:
                col_name = assignment['column']
                new_value = assignment['value']

                # 类型检查
                col_def = table['columns'][col_name]
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

        original_len = len(table['data'])
        table['data'] = [row for row in table['data'] if row[primary_key] != primary_key_value]

        if len(table['data']) == original_len:
            raise Exception(f"找不到主键值为 '{primary_key_value}' 的行")

        return True


"""测试"""

sql = """
    -- 测试所有语句类型
    CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR(255) NOT NULL);
    INSERT INTO users VALUES (1, 'Alice');
    SELECT DISTINCT name FROM users WHERE id > 0 ORDER BY name DESC LIMIT 10;
    UPDATE users SET name = 'Bob' WHERE id = 1;
    DELETE FROM users WHERE id = 1;
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


"""