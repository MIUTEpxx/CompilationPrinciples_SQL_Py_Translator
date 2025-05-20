# 读取器模式标志
STR_READER = 0    # 字符流模式
TOKEN_READER = 1  # Token列表模式


# SQL常用关键字集合（部分）
KEYWORDS = {
    'SELECT', 'FROM', 'WHERE', 'CREATE', 'TABLE', 'INSERT', 'INTO',
    'VALUES', 'DELETE', 'UPDATE', 'SET', 'INT', 'VARCHAR', 'PRIMARY',
    'KEY', 'NOT', 'NULL', 'AND', 'OR', 'AS', 'DISTINCT', 'ORDER', 'BY',
    'ASC', 'DESC', 'LIKE', 'IN', 'BETWEEN'
}

# 操作符映射表
OPERATORS = {
    '=': 'EQ',
    '<>': 'NEQ',
    '!=': 'NEQ',
    '<': 'LT',
    '<=': 'LTE',
    '=<': 'LTE',
    '>': 'GT',
    '>=': 'GTE',
    '=>': 'GTE',
    '+': 'PLUS',
    '-': 'MINUS',
    '*': 'ASTERISK',
    '/': 'SLASH',
    ',': 'COMMA',
    '(': 'LPAREN',
    ')': 'RPAREN',
    ';': 'SEMI'
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

            # 跳过空白字符
            if c.isspace():
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
        """跳过空白字符"""
        while reader.peek() and reader.peek().isspace():
            reader.next()

    def _read_identifier():
        """读取标识符或关键字"""
        start_pos = reader.pos
        while (c := reader.peek()) and (c.isalnum() or c == '_'):
            reader.next()

        value = reader.current_str[start_pos:reader.pos]
        upper_value = value.upper()

        # 判断是否是关键字
        if upper_value in KEYWORDS:
            tokens.append(mk_tk(upper_value, 'KEYWORD'))  # !!!
            # tokens.append(('KEYWORD', upper_value))
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
        columns = []
        # 解析选择的列
        while reader.peek() not in ('FROM', 'WHERE'):
            if reader.peek() == 'ASTERISK':  # *号, 表示全都要 SLECTE * WHERE ...
                columns.append('*')
                reader.next()
            else:
                columns.append(reader.next()[1])  # 选择特定的列数据 SELECTE name, age WHERE ...
            if reader.peek() == 'COMMA':
                reader.next()  # 吃掉逗号
        reader.match('FROM')  # 吃掉 FROM
        table_name = reader.match('IDENTIFIER')[1]  # 获取表名
        # 解析WHERE条件
        where_clause = None
        if reader.peek() == 'WHERE':
            reader.next()  # 吃掉 WHERE
            where_clause = parse_expression()
        return {
            'type': 'select',
            'columns': columns,
            'table': table_name,
            'where': where_clause
        }

    def parse_delete():
        """解析DELETE FROM语句"""
        reader.match('FROM')  # 吃掉 FROM
        table_name = reader.match('IDENTIFIER')[1]
        # 解析WHERE条件
        where_clause = None
        if reader.peek() == 'WHERE':
            reader.next()  # 吃掉 WHERE
            where_clause = parse_expression()
        return {'type': 'delete', 'table': table_name, 'where': where_clause}

    return parser()  # 开始执行






"""测试"""

sql = """
    CREATE TABLE users (
        id INT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        age INT
    );

    INSERT INTO users VALUES (1, "'John'", 30);

    SELECT name, age FROM users WHERE age >= 25;
    """

test_tokens = sql_lexer(sql)
test_ast = sql_parser(test_tokens)

print(f"Token列表:\n{test_tokens}")
print("")
print(f"AST:\n{test_ast}")


# for token in test_tokens:
#     print(f"{token[0]:<12} | {token[1]}")

