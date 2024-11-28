import sys
import re
import subprocess
import os

KEYWORDS = {}
variables = {}
functions = {}

variables['argv'] = sys.argv[2:]

def register_keyword(keyword):
    def decorator(func):
        KEYWORDS[keyword] = func
        return func
    return decorator

def parse_line(line):
    parts = line.strip().split(maxsplit=1)
    if not parts:
        return None, []
    keyword = parts[0]
    args = parts[1] if len(parts) > 1 else ""
    return keyword, args

def log_error(msg, line_no=None):
    message = f"[ERROR] {msg}"
    if line_no:
        message += f" at line {line_no}"
    print(f"\033[91m{message}\033[0m")  

def log_warning(msg):
    print(f"\033[93m[WARN] {msg}\033[0m")  

def log_info(msg):
    print(f"\033[96m[INFO] {msg}\033[0m")  

def interpret_file(script_file):
    try:
        with open(script_file, "r") as file:
            for line_no, line in enumerate(file, start=1):
                keyword, args = parse_line(line)
                if keyword in KEYWORDS:
                    KEYWORDS[keyword](args)
                elif keyword:
                    log_error(f"Unknown keyword: '{keyword}'", line_no)
    except FileNotFoundError:
        log_error(f"File '{script_file}' not found", 0)
    except Exception as e:
        log_error(f"An error occurred: {e}", 0)

def main():
    if len(sys.argv) < 2:
        log_error("Usage: python pirat_interpreter.py <script_file>", 0)
        sys.exit(1)

    script_file = sys.argv[1]
    interpret_file(script_file)

@register_keyword("let")
def let_handler(args):
    match = re.match(r'(\w+)\s*=\s*(.*)', args)
    if match:
        var_name = match.group(1)
        var_value = match.group(2).strip()
        
        if var_value.startswith("[") and var_value.endswith("]"):
            var_value = parse_array(var_value)
        else:
            var_value = substitute_variables(var_value)
        variables[var_name] = var_value
    else:
        log_error(f"Invalid variable assignment: '{args}'", 0)

@register_keyword("invoke")
def invoke_handler(args):
    external_func = False
    if args.startswith('$'):
        external_func = True
        func_name = args[1:].split('(')[0]
        raw_args = re.search(r'\((.*?)\)', args)
        combined_args = raw_args.group(1) if raw_args else ""
        args_list = parse_arguments(combined_args)
    else:
        func_name = args.split('(')[0]
        raw_args = re.search(r'\((.*?)\)', args)
        combined_args = raw_args.group(1) if raw_args else ""
        args_list = parse_arguments(combined_args)

    args_list = [substitute_variables(arg) for arg in args_list]

    if external_func:
        exec_external(func_name, args_list)
    else:
        log_warning(f"Local function's not implemented")

def parse_arguments(arguments):
    args = re.findall(r'"([^"]*)"|([^, ]+)', arguments)
    return [arg[0] if arg[0] else arg[1] for arg in args]

def substitute_variables(text):
    text = re.sub(r'\{(\w+)\}', lambda match: str(variables.get(match.group(1), match.group(0))), text)
    text = re.sub(r'\{(\$[A-Za-z_][A-Za-z0-9_]*)\}', lambda match: os.getenv(match.group(1)[1:], match.group(0)), text)
    text = re.sub(r'\{(\w+)\[\]\}', lambda match: " ".join(variables.get(match.group(1), match.group(0))), text)
    text = re.sub(r'\{(\w+)\[(\d+)\]\}', lambda match: str(variables.get(match.group(1), [])[int(match.group(2))] if match.group(1) in variables and isinstance(variables.get(match.group(1)), list) else match.group(0)), text)
    return text

def parse_array(array_str):
    array_str = array_str.strip('[]')
    elements = [substitute_variables(e.strip()) for e in array_str.split(',')]
    return elements

def exec_external(cmd, args):
    try:
        command = ["/bin/env", cmd] + args
        subprocess.run(command, check=True, text=True, capture_output=False)
    except subprocess.CalledProcessError as e:
        log_error(f"External command failed with error: {e.stderr}", 0)
    except Exception as e:
        log_error(f"Failed to execute external command: {e}", 0)

if __name__ == "__main__":
    main()
