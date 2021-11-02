import os
import re
import shutil

base_types = {"bool":"b", "string":"s", "int":"i",  "int8":"i",  "int16":"i",  "int32":"i",  "int64":"i",
"uint":"ui", "uint8":"ui", "uint16":"ui", "uint32":"ui", "uint64":"ui", "uintptr":"ui","byte":"bt", "rune":"r", 
"float32":"f", "float64":"f", "complex64":"c", "complex128":"c", "error":"err", "interface":"intfc"}

class Interface():
    def __init__(self, name, methods, imports, package):
        self.name = name
        self.methods = methods
        self.imports = list(imports)
        self.package = package

    def __repr__(self) -> str:
        s = self.get_import_statement()
        s += f"\n\ntype {self.name} interface {{\n"
        for method in self.methods:
            s += f"  {method.name}("
            for argument in method.args:
                s += f"{argument.name} {argument.type}, "
            if method.args:
                s = s[:-2]
            s += ")"
            if method.results:
                s += " ("
            for argument in method.results:
                s += f"{argument.name} {argument.type}, "
            if method.results:
                s = s[:-2]
                s += ")"
            s += "\n"
        s+= "}"
        return s

    def get_import_statement(self):
        s = ""
        if len(self.imports) == 1:
            s += f"import {self.imports[0]}\n\n"
        elif len(self.imports) > 1:
            s += "import (\n"
            for imp in self.imports:
                s += f"  {imp}\n"
            s += ")"
        return s

class Method():
    def __init__(self, name, args, results):
        self.name = name
        self.args = args
        self.results = results

class Argument():
    def __init__(self, type, name):
        self.type = type
        self.name = name

    def __repr__(self) -> str:
        return f"{self.name} {self.type}"

def main():
    go_mod, total_files = get_all_files()
    module = get_module(go_mod)
    interfaces = get_interfaces(total_files, module)
    generate_mocks(interfaces)

def generate_mocks(interfaces):
    try:
        os.mkdir("mocks")
    except:
        shutil.rmtree("mocks")
        os.mkdir("mocks")
        pass
    for interface in interfaces:
        generate_mock(interface)

def generate_mock(interface):
    file_name = get_new_file_name(interface)
    struct_name = get_struct_name(file_name.split('.go')[0])
    struct_properties = get_struct_properties(interface)
    struct_methods = get_struct_methods(interface, struct_name)
    nl = "\n"
    s = (f"package mocks{nl*2}" + 
        f"{interface.get_import_statement() + nl*2 if interface.get_import_statement() else ''}" + 
        f"type {struct_name} struct {{\n" +
        f"{struct_properties}" + 
        f"}}{nl*2}"
        f"{struct_methods}")
    

    with open(file_name, "w") as f:
        f.write(s)
    os.system(f"gofmt -s -w {os.path.join(os.getcwd(),file_name)}")

def get_struct_properties(interface):
    s = ""
    added_private = False
    for method in interface.methods:
        if method.name[0].islower() and not added_private:
            s+= f"   {interface.package}.{interface.name}\n"
            continue
        s += f"  {method.name}Mock func{get_signature(method)}\n"
    return s

def get_struct_methods(interface, struct_name):
    s = ""
    struct_short_name = ''.join([i.lower() for i in struct_name if i.isupper()])
    for method in interface.methods:
        if method.name[0].islower():
            continue
        arg_names = ", ".join([i.name for i in method.args])
        return_statement = f"return {struct_short_name}.{method.name}Mock({arg_names})" if method.results else ""
        s+=f"func ({struct_short_name} *{struct_name}) {method.name}{get_signature(method)} {{\n"
        s+=f"    {return_statement}\n}}\n\n"
    return s
    
def get_signature(method):
    args_str = [str(i) for i in method.args]
    result_str = [str(i) for i in method.results]
    return f"({', '.join(args_str)}) {'('+', '.join(result_str)+')' if method.args else ''}"
def get_struct_name(snake_str):
    components = snake_str.split('/')[-1].split('_')
    return ''.join(x.title() for x in components)


def get_new_file_name(interface):
    files = {"mocks/"+i for i in os.listdir("mocks") if i.endswith(".go")}
    file_name = f"mocks/{interface.package}_{interface.name}_mock.go".lower()
    fn = file_name
    counter = 1
    while fn in files:
        print("ALO")
        fn = file_name[:-3] + str(counter) + ".go"
        counter +=1
    return fn


def get_all_files(path = None):
    if path == None:
        path = os.getcwd()
    files = [os.path.join(path,i) for i in os.listdir(path) if i != "mocks"]
    total_files = []
    go_mod = None
    for file in files:
        if file.split("/")[-1][0] == ".":
            continue
        if os.path.isdir(file):
            go_mod_part, partial_files = get_all_files(file)
            if go_mod == None:
                go_mod = go_mod_part
            total_files += partial_files
        elif file.endswith(".go"):
            total_files.append(file)
        elif file.endswith("/go.mod"):
            go_mod = file
    return go_mod, total_files

def get_module(path):
    pattern = "module (.*)"
    with open(path) as f:
        text = f.read()
    match = re.match(pattern, text)
    return match.group(1)

def get_interfaces(files, module):
    interfaces = []
    for file in files:
        interfaces.extend(extract_interfaces(file, module))
    return interfaces

def extract_interfaces(file, module):
    interfaces = []
    with open(file) as f:
        content = f.read()
    if not content.startswith("package"):
        return interfaces
    package_name = re.match("package (.*)", content).group(1)
    import_file_name = get_import_from_file(file, package_name, module)
    
    interface_info = [[m.start(), m.group(1)] for m in re.finditer("type (.*?) interface", content)]
    if len(interface_info) == 0:
        return interfaces
    
    imports = extract_imports(content)
    for start_index, name in interface_info:
        curly_bracket_count = 0
        for ind, letter in enumerate(content[start_index:]):
            if letter == "{":
                curly_bracket_count += 1
            if letter == "}":
                curly_bracket_count -= 1
                if curly_bracket_count == 0:
                    break
        interface_string = content[start_index: start_index+ind+1]
        interface = extract_interface(interface_string, name, import_file_name, imports)
        interfaces.append(interface)
    return interfaces

def get_import_from_file(file_name, package, module):
    cwd = os.getcwd()
    file_append = file_name.split(cwd)[1]
    import_file = module + file_append
    import_file = import_file.split("/")[:-1]
    import_file[-1] = package
    return "/".join(import_file)

def extract_imports(file_string):
    imports = {}
    if [i.strip() for i in file_string.split() if i.strip()][2] != "import":
        return {}
    start_import = re.match("package (.|\s)*?import", file_string).end()
    if file_string[start_import:].lstrip()[0] == "(":
        for line in [i.strip() for i in file_string.split("(")[1].split(")")[0].split("\n") if i.strip()]:
            name, imp = extract_import(line)
            imports[name] = imp
    else:
        name, imp = extract_import(file_string[start_import:])
        imports[name] = imp
    return imports

def extract_import(line):
    imp = '"' + line.split('"')[1].split('"')[0] + '"'
    prefix = line.split('"')[0].strip()
    name = prefix if prefix else imp.split('/')[-1].replace('"','')
    return name, imp

def extract_interface(interface_string, name, import_file_name, imports):
    methods_start = interface_string.find("{") + 1
    methods_end = len(interface_string) - [m.start() for m in re.finditer("}", interface_string[::-1])][0]
    if methods_end > methods_start:
        methods_end -= 1
    methods_string = interface_string[methods_start:methods_end]
    methods_strings = [i.strip() for i in methods_string.split("\n") if i.strip()]
    methods = extract_methods(methods_strings)
    needed_imports = extract_needed_imports(methods, import_file_name, imports)
    return Interface(name, methods, needed_imports, import_file_name.split('/')[-1])

def extract_needed_imports(methods, import_file_name, imports):
    needed_imports = set()
    needs_literal = False
    for method in methods:
        args = [*method.args, *method.results]
        for arg in args:
            if "." not in arg.type:
                if extract_alpha(arg.type) not in base_types.keys():
                    needed_imports.add('"'+import_file_name+'"')
                    orig_package_name = import_file_name.split('/')[-1]
                    counter = 0
                    package_name = orig_package_name
                    while package_name in imports:
                        package_name = orig_package_name + str(counter)
                        counter += 1
                    arg.type = package_name + "." + arg.type
                    if "*" in arg.type:
                        arg.type = '*'+arg.type.replace('*','')
            else:
                package = arg.type.split(".")[0].replace("*","")
                import_to_add = imports[package] if package == imports[package].split('/')[-1].replace('"','') else f"{package} {imports[package]}"
                needed_imports.add(import_to_add)
    return needed_imports

def extract_alpha(s):
    return ''.join([i for i in s if i.isalpha()])

def extract_methods(methods_strings):
    methods = []
    for method_string in methods_strings:
        parenthesis_counter = 0
        for ind, ch in enumerate(method_string):
            if ch == "(":
                if parenthesis_counter == 0:
                    arguments_start = ind+1
                    method_name = method_string[:ind].strip()
                parenthesis_counter += 1
            if ch == ")":
                if parenthesis_counter == 1:
                    break
                parenthesis_counter -= 1
        method_arguments_string = method_string[arguments_start:ind].strip()
        args = extract_arguments(method_arguments_string)
        if ind +1 == len(method_string):
            results = []
        else:
            results_string = method_string[ind+1:].strip()
            if results_string and results_string[0] == "(":
                results_string = strip_parenthesis(results_string)
            results = extract_arguments(results_string)
        methods.append(Method(method_name, args, results))
    return methods

def strip_parenthesis(s):
    if len(s) < 3:
        return ""
    return s[1:-1]

def extract_arguments(argument_string):
    arguments = []
    argument_strings_split = [i.strip() for i in argument_string.split(",") if i.strip()]
    names = {}
    for argument_string in argument_strings_split:
        argument_info = [i.strip() for i in argument_string.split(" ")]
        if len(argument_info) == 1:
            name = argument_info[0].split(".")[-1]
            if name:
                first_letter = name[0].lower()
                if len(name) > 1:
                    name = first_letter + name[1:]
                else:
                    name = first_letter
                if name in base_types:
                    name = base_types[name]
            arg_type = argument_info[0]
        else:
            name, arg_type = argument_info
        if name in names:
            names[name] += 1
            name = name + str(names[name])
        else:
            names[name] = 0
        arguments.append(Argument(arg_type, name))
    return arguments

if __name__ == "__main__":
    main()