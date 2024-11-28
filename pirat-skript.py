import sys
import re
import subprocess
import os
import types
import builtins

KEYWORDS = {}
variables = {}
functions = {}

variables["argv"] = sys.argv[2:]
variables["_version"] = "pirat-skript v1.1.2-alpha"
variables[
    "_host"
] = f"{os.uname().sysname} {os.uname().nodename} {os.uname().release} {os.uname().version} {os.uname().machine}"

verbose = False


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
    log_trace(f"Parsed line into keyword: '{keyword}', arguments: '{args}'")
    return keyword, args


def log_error(msg, line_no=None):
    message = f"[ERROR] {msg}"
    if line_no:
        message += f" at line {line_no}"
    print(f"\033[91m{message}\033[0m")


def log_warning(msg):
    print(f"\033[93m[WARN] {msg}\033[0m")


def log_info(msg):
    if verbose:
        print(f"\033[96m[INFO] {msg}\033[0m")


def log_debug(msg):
    if verbose:
        print(f"\033[92m[DEBUG] {msg}\033[0m")


def log_trace(msg):
    if verbose:
        print(f"\033[94m[TRACE] {msg}\033[0m")


def interpret_file(script_file):
    try:
        with open(script_file, "r") as file:
            for line_no, line in enumerate(file, start=1):
                keyword, args = parse_line(line)
                log_trace(f"Processing line {line_no}: {line.strip()}")
                if keyword in KEYWORDS:
                    log_debug(
                        f"Executing handler for keyword '{keyword}' with arguments '{args}'"
                    )
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

    if verbose:
        log_info("Verbose mode enabled. Trace and debug logs are active.")

    script_file = sys.argv[1]
    interpret_file(script_file)


@register_keyword("let")
def let_handler(args):
    log_debug(f"Handling let statement: {args}")
    match = re.match(r"(\w+)\s*=\s*(.*)", args)
    if match:
        var_name = match.group(1)
        var_value = match.group(2).strip()

        if var_value.startswith("[") and var_value.endswith("]"):
            log_trace(f"Parsing array assignment: {var_value}")
            var_value = parse_array(var_value)
        else:
            log_trace(f"Substituting variables in value: {var_value}")
            var_value = substitute_variables(var_value)
        variables[var_name] = var_value
        log_info(f"Set variable '{var_name}' to {var_value}")
    else:
        log_error(f"Invalid variable assignment: '{args}'", 0)

@register_keyword("invoke")
def invoke_handler(args):
    log_debug(f"Handling invoke statement: {args}")

    external_func = False
    func_name = ""
    args_list = []

    if args.startswith("$"):
        external_func = True
        func_name = args[1:].split("(")[0]
        raw_args = re.search(r"\((.*?)\)", args)
        combined_args = raw_args.group(1) if raw_args else ""
        args_list = parse_arguments(combined_args)
    else:
        func_name = args.split("(")[0]
        raw_args = re.search(r"\((.*?)\)", args)
        combined_args = raw_args.group(1) if raw_args else ""
        args_list = parse_arguments(combined_args)

    args_list = [substitute_variables(arg) for arg in args_list]

    if external_func:
        exec_external(func_name, args_list)
    else:

        if "." in func_name:
            module_name, func_name = func_name.rsplit(".", 1)
            log_info(
                f"Invoking function '{func_name}' from module '{module_name}' with arguments: {args_list}"
            )

            try:
                module = __import__(module_name)
                func = getattr(module, func_name)
                result = func(*args_list)
                log_trace(f"Function '{func_name}' returned: {result}")
            except Exception as e:
                log_error(
                    f"Error invoking function '{func_name}' from module '{module_name}': {e}"
                )
        else:

            if func_name in globals() and callable(globals()[func_name]):
                log_info(
                    f"Invoking local Python function: {func_name} with arguments: {args_list}"
                )
                eval_function(func_name, args_list)

            elif func_name in dir(builtins):
                log_info(
                    f"Invoking built-in function: {func_name} with arguments: {args_list}"
                )
                func = getattr(builtins, func_name)
                result = func(*args_list)
                log_trace(f"Function '{func_name}' returned: {result}")
            else:
                log_warning(
                    f"Function '{func_name}' is not implemented locally or in builtins"
                )
                log_info(f"Globals: {globals()}")
                log_info(f"Builtins: {dir(builtins)}")


def eval_function(func_name, args_list):
    try:
        func = globals()[func_name]
        result = func(*args_list)
        log_trace(f"Function '{func_name}' returned: {result}")
    except Exception as e:
        log_error(f"Error invoking function '{func_name}': {e}")
    log_trace(f"Ran {func_name}")


def parse_arguments(arguments):
    log_trace(f"Parsing arguments: {arguments}")
    args = re.findall(r'"([^"]*)"|([^, ]+)', arguments)
    return [arg[0] if arg[0] else arg[1] for arg in args]


def substitute_variables(text):
    log_trace(f"Substituting variables in text: {text}")
    text = re.sub(
        r"\{(\w+)\}",
        lambda match: str(variables.get(match.group(1), match.group(0))),
        text,
    )
    text = re.sub(
        r"\{(\$[A-Za-z_][A-Za-z0-9_]*)\}",
        lambda match: os.getenv(match.group(1)[1:], match.group(0)),
        text,
    )
    text = re.sub(
        r"\{(\w+)\[\]\}",
        lambda match: " ".join(variables.get(match.group(1), match.group(0))),
        text,
    )
    text = re.sub(
        r"\{(\w+)\[(\d+)\]\}",
        lambda match: str(
            variables.get(match.group(1), [])[int(match.group(2))]
            if match.group(1) in variables
            and isinstance(variables.get(match.group(1)), list)
            else match.group(0)
        ),
        text,
    )
    text = re.sub(
        r"\{(\w+\.\w+)\((.*?)\)\}",
        lambda match: invoke_function(match.group(1), match.group(2)),
        text,
    )
    log_trace(f"Substitution result: {text}")
    return text


def parse_array(array_str):
    log_trace(f"Parsing array from string: {array_str}")
    array_str = array_str.strip("[]")
    elements = [substitute_variables(e.strip()) for e in array_str.split(",")]
    log_trace(f"Parsed array: {elements}")
    return elements


def exec_external(cmd, args):
    try:
        command = ["/bin/env", cmd] + args
        log_trace(f"Executing external command: {command}")
        subprocess.run(command, check=True, text=True, capture_output=False)
    except subprocess.CalledProcessError as e:
        pass
    except Exception as e:
        log_error(f"Failed to execute external command: {e}", 0)
    log_trace(f"Ran {cmd}")


@register_keyword("#")
def comment_handler(args):
    pass


if __name__ == "__main__":
    main()
