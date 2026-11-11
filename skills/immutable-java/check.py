#!/usr/bin/env python3
# Checks the immutability rules that bytecode tests such as ArchUnit can't see. Run from the repo root:
#   python3 -I <skill-dir>/check.py [files...]
# Without files it checks every main source the config covers. Exits 1 on an error; warnings don't fail it.
#
# Optional config, .claude/skill-config/immutable-java.json, relative to the current directory:
#   {
#     "sources": ["**/src/main/java/**/*.java"],       glob patterns for a run without files
#     "exclude": ["jooq/generated"],                   skip paths containing any of these
#     "copyPatterns": ["List\\.copyOf\\("]             regexes that count as copying or wrapping a component
#   }
import json
import pathlib
import re
import sys

CONFIG_PATH = pathlib.Path('.claude/skill-config/immutable-java.json')
DEFAULTS = {
    'sources': ['**/src/main/java/**/*.java'],
    'exclude': [],
    'copyPatterns': [r'(?:List|Set|Map)\.copyOf\(', r'Collections\.unmodifiable\w+\('],
}
COLLECTION = re.compile(r'^(List|Set|Map|Collection)<')


def load_config():
    config = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        config.update(json.loads(CONFIG_PATH.read_text(encoding='utf-8')))
    return config


def is_excluded(path, config):
    return any(part in path for part in config['exclude'])


def main_sources(args, config):
    if args:
        checked = [a for a in args if a.endswith('.java') and '/src/main/' in a and not is_excluded(a, config)]
        for skipped in sorted(set(args) - set(checked)):
            print('skipped (not hand-written main Java):', skipped)
        return [pathlib.Path(a) for a in checked if pathlib.Path(a).exists()]
    found = {p for pattern in config['sources'] for p in pathlib.Path('.').glob(pattern)}
    return sorted(p for p in found if not is_excluded(p.as_posix(), config))


def split_top_level(text):
    parts, depth, current = [], 0, ''
    for ch in text:
        depth += ch in '<('
        depth -= ch in '>)'
        if ch == ',' and depth == 0:
            parts.append(current)
            current = ''
        else:
            current += ch
    return parts + [current]


def closing(text, start, opening, closing_char):
    depth = 1
    i = start
    while depth:
        depth += {opening: 1, closing_char: -1}.get(text[i], 0)
        i += 1
    return i


def record_errors(path, source, copies):
    errors = []
    for match in re.finditer(r'\brecord\s+(\w+)\s*(?:<[^>]*>)?\s*\(', source):
        name = match.group(1)
        end = closing(source, match.end(), '(', ')')
        header = re.sub(r'//[^\n]*', '', source[match.end():end - 1])
        header = re.sub(r'@\w+(\([^)]*\))?', '', header)
        components = []
        for part in split_top_level(header):
            part = part.strip()
            if part:
                type_, component = part.rsplit(None, 1)
                if COLLECTION.match(type_.strip()):
                    components.append(component)
        if not components:
            continue
        compact = re.search(r'\n\s*(?:(?:public|protected|private)\s+)?' + name + r'\s*\{', source[end:])
        if not compact:
            errors.append(f'{path}: record {name} has collection components {components} but no compact constructor')
            continue
        body_start = end + compact.end()
        body = source[body_start:closing(source, body_start, '{', '}') - 1]
        for component in components:
            if not re.search(r'\b' + component + r'\s*=\s*(?:' + copies + ')', body):
                errors.append(f'{path}: record {name} does not copy or wrap {component} in its compact constructor')
    return errors


def line_findings(path, source):
    errors, warnings = [], []
    for number, line in enumerate(source.splitlines(), 1):
        where = f'{path}:{number}'
        if re.search(r'@(Data|Setter|With)\b', line):
            errors.append(f'{where}: Lombok @Data/@Setter/@With makes a value mutable; use a record and toBuilder()')
        if re.search(r'Collectors\.(toList|toSet)\(\)', line):
            warnings.append(f'{where}: Collectors.toList()/toSet() are mutable; use .toList() or Collectors.toUnmodifiableSet()')
        if re.search(r'return new (ArrayList|LinkedList|HashMap|LinkedHashMap|HashSet|LinkedHashSet|TreeMap|TreeSet)\b', line):
            warnings.append(f'{where}: returns a mutable collection; return it unmodifiable')
    return errors, warnings


def main():
    config = load_config()
    copies = '|'.join(config['copyPatterns'])
    errors, warnings = [], []
    for path in main_sources(sys.argv[1:], config):
        source = path.read_text(encoding='utf-8')
        errors += record_errors(path, source, copies)
        line_errors, line_warnings = line_findings(path, source)
        errors += line_errors
        warnings += line_warnings
    for warning in warnings:
        print('warning:', warning)
    for error in errors:
        print('error:', error)
    print(f'{len(errors)} errors, {len(warnings)} warnings')
    sys.exit(1 if errors else 0)


main()
