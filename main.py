STR_READER = 0  # 读取器 字符流模式
TOKEN_READER = 1  # 读取器 Token列表模式

# SQL关键字集合（部分）
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


class BaseReader:
    """SQL命令 字符串/token列表 读取器"""

    def __init__(self, s, err, mod=0):
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
        if self.peek() != t:
            self.err(f'期望 "{t}" , 实际为 "{self.current_val}"')
        return self.next()


def sql_lexer(input_str):
    """SQL命令词法解析器"""

    def _error(msg):
        # 专用报错
        error('cilly lexer', msg)

    reader = BaseReader(input_str, _error, 0)  # 初始化字符流读取器
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
            tokens.append(('KEYWORD', upper_value))
        else:
            tokens.append(('IDENTIFIER', value))

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
        tokens.append(('NUMBER', float(value) if has_dot else int(value)))

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
        tokens.append(('STRING', value))
        reader.next()  # 跳过结束引号

    def _read_operator():
        """读取操作符，处理组合操作符如>=, <=等"""
        c = reader.next()
        next_c = reader.peek()

        # 优先处理双字符操作符
        if next_c and (op := c + next_c) in OPERATORS:
            reader.next()
            tokens.append(('OPERATOR', OPERATORS[op]))
        elif c in OPERATORS:
            tokens.append(('OPERATOR', OPERATORS[c]))
        else:
            _error(f"无法识别的操作符: {c}")

    return tokenize()  # 开始执行词法解析器程序, 最终返回SQL命令对应Token列表


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

tokens = sql_lexer(sql)

for token in tokens:
    print(f"{token[0]:<12} | {token[1]}")
