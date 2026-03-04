import re


def load_grammar(filename):
    """Загружает грамматику из файла"""
    grammar = {}
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            name, rules = line.split('=', 1)
            name = name.strip().strip('<>').strip()
            rules = rules.strip()
            variants = [v.strip() for v in rules.split('|')]
            grammar[name] = variants
    return grammar


def tokenize(text):
    """
    Разбивает текст на слова.
    4-значные числа разбиваются на отдельные цифры для соответствия грамматике.
    """
    matches = re.findall(r'[\wа-яА-ЯёЁ]+', text.lower())
    tokens = []
    for match in matches:
        # если это 4-значное число (год) - разбиваем на отдельные цифры
        if match.isdigit() and len(match) == 4:
            for digit in match:
                tokens.append(digit)
        else:
            tokens.append(match)
    return tokens


class Parser:
    """Парсер с рекурсивным спуском"""

    def __init__(self, grammar, tokens):
        self.grammar = grammar
        self.tokens = tokens
        self.pos = 0

    def current(self):
        """Получение текущего токена в запросе"""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def advance(self):
        """Переход к следующему токену"""
        self.pos += 1

    def match(self, word):
        """Проверка совпадения токена"""
        return self.current() == word.lower()

    def parse(self):
        """Запуск парсинга"""
        tree = self.parse_rule("Запрос")
        if self.current() is not None:
            raise SyntaxError(
                f"лишние слова: '{self.current()}'",
                self.current(),
                self.pos
            )
        return tree

    def parse_rule(self, rule_name):
        """Разбор правила"""
        # если правила нет в грамматике, то это терминал
        if rule_name not in self.grammar:
            if self.match(rule_name):
                token_value = self.current()
                self.advance()
                return {'type': 'terminal', 'name': token_value}
            else:
                # не совпало - ошибка
                raise SyntaxError(
                    f"ожидалось '{rule_name}'",
                    self.current(),
                    self.pos
                )
        # нетерминал
        best_error = None
        best_pos = -1
        for variant in self.grammar[rule_name]:
            saved_pos = self.pos  # сохраняем текущую позицию для возможного отката
            try:
                children = self.parse_variant(variant)
                return {'type': 'rule', 'name': rule_name, 'children': children}
            except SyntaxError as e:
                if self.pos > best_pos:
                    best_error = e
                    best_pos = self.pos
                self.pos = saved_pos  # если произошла ошибка при разборе варианта, мы откатываемся назад и пробуем следующее правило из грамматики
                continue
        # ни один вариант не подошел
        if best_error:
            raise best_error
        raise SyntaxError(
            f"не удалось разобрать <{rule_name}>",
            self.current(),
            self.pos
        )

    def parse_variant(self, variant):
        """Разбор одного варианта правила"""
        children = []
        parts = self.split_variant(variant)
        for part in parts:
            saved_pos = self.pos  # точка отката
            optional = part.get('optional', False)
            try:
                if part['type'] == 'non_terminal':
                    # нетерминал => рекурсивно вызываем функцию для разбора правила для нетерминала
                    child = self.parse_rule(part['value'])
                    children.append(child)
                elif part['type'] == 'terminal':
                    # терминал
                    if self.match(part['value']):
                        token_value = self.current()
                        self.advance()
                        children.append(
                            {'type': 'terminal', 'name': token_value})
                    else:
                        # не совпало - ошибка
                        raise SyntaxError(
                            f"ожидалось '{part['value']}'",
                            self.current(),
                            self.pos
                        )
            except SyntaxError:
                if optional:
                    # если ошибка при разборе, при этом optional => откат
                    self.pos = saved_pos
                else:
                    raise
        return children

    def split_variant(self, variant):
        """Разбивает вариант на части с учетом [] и <>"""
        parts = []
        i = 0
        n = len(variant)
        while i < n:
            # пропускаем пробелы
            while i < n and variant[i].isspace():
                i += 1
            if i >= n:
                break
            optional = False
            # проверка на []
            if variant[i] == '[':
                optional = True
                i += 1
                end = variant.find(']', i)
                if end == -1:
                    raise SyntaxError("незакрытая скобка '['", None, i)
                content = variant[i:end]
                i = end + 1
            # проверка на <>
            elif variant[i] == '<':
                end = variant.find('>', i)
                if end == -1:
                    raise SyntaxError("незакрытая скобка '<'", None, i)
                content = variant[i:end+1]
                i = end + 1
            else:
                # берем слово до пробела или следующей скобки
                start = i
                while i < n and not variant[i].isspace() and variant[i] not in '<[':
                    i += 1
                content = variant[start:i]
            if not content:
                continue
            if content.startswith('<') and content.endswith('>'):
                # нетерминал
                parts.append(
                    {'type': 'non_terminal', 'value': content[1:-1], 'optional': optional})
            else:
                # терминал
                parts.append(
                    {'type': 'terminal', 'value': content.lower(), 'optional': optional})
        return parts


def print_tree(node, indent=0):
    """Рекурсивный вывод дерева с терминалами и нетерминалами"""
    if node is None:
        return
    name = node.get('name', '')
    node_type = node.get('type', '')
    children = node.get('children', [])
    if node_type == 'rule':
        print("  " * indent + f"<{name}>")
        for child in children:
            print_tree(child, indent + 1)
    elif node_type == 'terminal':
        print("  " * indent + f"'{name}'")


class ParseError(Exception):
    """Исключение с информацией о токене"""

    def __init__(self, message, token=None, position=0):
        self.message = message
        self.token = token
        self.position = position
        super().__init__(message)

    def __str__(self):
        result = self.message
        if self.token:
            result += f" (слово '{self.token}' на позиции {self.position + 1})"
        return result


def parse_query(grammar, query):
    """Разбор одного предложения"""
    try:
        tokens = tokenize(query)
        parser = Parser(grammar, tokens)
        tree = parser.parse()
        return True, tree, None
    except SyntaxError as e:
        error_msg = str(e)
        if hasattr(e, 'token') and e.token:
            error_msg += f" (слово '{e.token}' на позиции {e.position + 1})"
        return False, None, error_msg


def print_query_result(query, success, tree, error_msg):
    """Вывод результата разбора предложения"""
    tokens = tokenize(query)
    print(f"Токены: {tokens}")
    if success:
        print("Успешно, дерево разбора:")
        print_tree(tree)
    else:
        print(f"Ошибка: {error_msg}")


def main():
    try:
        grammar = load_grammar("grammar.txt")
        print(f"Загружено {len(grammar)} правил грамматики")
    except FileNotFoundError:
        print("Файл grammar.txt не найден")
        return
    print("1. Обработать файл")
    print("2. Интерактивный режим")
    choice = input("Ваш выбор (1 или 2): ").strip()
    if choice == '1':
        filename = input("Имя файла (input.txt): ").strip() or "input.txt"
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                queries = [line.strip() for line in f if line.strip()
                           and not line.startswith('#')]
            print(f"Найдено запросов: {len(queries)}")
            success_count = 0
            for query in queries:
                success, tree, error_msg = parse_query(grammar, query)
                if success:
                    success_count += 1
                print_query_result(query, success, tree, error_msg)
            print(
                f"Успешных: {success_count}, с ошибками: {len(queries) - success_count}")
        except FileNotFoundError:
            print(f"Файл '{filename}' не найден")
    elif choice == '2':
        print("Вводите запросы (enter для выхода):")
        while True:
            try:
                query = input("> ").strip()
                if query:
                    success, tree, error_msg = parse_query(grammar, query)
                    print_query_result(query, success, tree, error_msg)
                else:
                    break
            except (EOFError, KeyboardInterrupt):
                print("Выход из программы")
                break
    else:
        print("Неверный выбор")


if __name__ == "__main__":
    main()
