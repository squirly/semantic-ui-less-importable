#!/usr/bin/env python3
from io import BytesIO
import json
import os
import re
from zipfile import ZipFile

import requests

ARCHIVE_PATH = "http://github.com/Semantic-Org/Semantic-UI/archive/"
ARCHIVE_EXTENSION = "zip"
SRC_DIR = "src"
DEFINITIONS_DIR = "definitions"
THEMES_DIR = "themes"
LESS_EXTENSION = "less"
VARIABLES_EXTENSION = "variables"
OVERRIDES_EXTENSION = "overrides"
DEFAULT_THEME = "default"
OUT_DIR = "dist"
GLOBALS_DIRECTORY = "globals"
BASE_IMPORTS_PATH = "semantic" + "." + LESS_EXTENSION
PACKAGE_PATH = "package.json"

variable_parser = re.compile(r'@([A-Za-z]+) *: ?(.+);', re.MULTILINE)
find_theme_comment = re.compile(r'/\*[* \r\n]+Theme[* \r\n]+\*/[\r\n ]+', re.MULTILINE)
find_type = re.compile(r'@type *:.+;[\r\n ]+', re.MULTILINE)
find_element = re.compile(r'@element *:.+;[\r\n ]+', re.MULTILINE)
find_theme_import = re.compile(r'@import \(multiple\) \'../../theme.config\';[\r\n ]+', re.MULTILINE)
find_load_overloads = re.compile(r'\.loadUIOverrides\(\);[\r\n ]*', re.MULTILINE)
find_load_fonts = re.compile(r'\.loadFonts\(\);[\r\n ]+', re.MULTILINE)


class Project:
    def __init__(self, version=None, out_dir=OUT_DIR):
        with open('package.json') as packageFile:
            self.package = json.load(packageFile)
        self.version = version or self.package['version']
        self.out_dir = out_dir
        archive = os.path.join(ARCHIVE_PATH, self.version) + "." + ARCHIVE_EXTENSION
        response = requests.get(archive)
        self.zipfile = ZipFile(BytesIO(response.content))
        self.infos = self.zipfile.infolist()
        self.basePath = self.infos[0].filename
        self.components = {}
        self.themes = {}
        self.load_components()
        self.load_themes()

    def load_components(self):
        def is_definition(i):
            return in_definitions_path(i.filename) and lessFile(i.filename)

        definitions_path = os.path.join(self.basePath, SRC_DIR, DEFINITIONS_DIR)
        in_definitions_path = in_path(definitions_path)
        for info in filter(is_definition, self.infos):
            definition_path = remove_extension(LESS_EXTENSION)(sub_path(definitions_path)(info.filename))
            name = definition_path.split("/")[1]
            self.components[name] = Component(name, definition_path, self.zipfile.read(info))

    def load_themes(self):
        def is_theme(i):
            return in_themes_dir(i.filename)

        themes_path = os.path.join(self.basePath, SRC_DIR, THEMES_DIR)
        themes_name = sub_path(themes_path)
        in_themes_dir = child_of(themes_path)
        for info in filter(is_theme, self.infos):
            name = themes_name(info.filename)
            self.themes[name] = self.load_theme(info.filename)

    def load_theme(self, theme_path):
        in_theme_path = in_path(theme_path)

        def in_theme(i):
            return in_theme_path(i.filename)

        def is_variable(i):
            return variablesFile(i.filename)

        def is_override(i):
            return overridesFile(i.filename)

        file_name = sub_path(theme_path)
        component_infos = list(filter(in_theme, self.infos))
        theme = {
            "overrides": {},
            "variables": {}
        }

        for variables in filter(is_variable, component_infos):
            base_path = remove_extension(VARIABLES_EXTENSION)(file_name(variables.filename))
            name = base_path.split('/')[1]
            theme[VARIABLES_EXTENSION][name] = ThemeVariables(name, base_path, self.zipfile.read(variables))
        for overrides in filter(is_override, component_infos):
            base_path = remove_extension(OVERRIDES_EXTENSION)(file_name(overrides.filename))
            name = base_path.split('/')[1]
            theme[OVERRIDES_EXTENSION][name] = ThemeOverrides(name, base_path, self.zipfile.read(overrides))
        return theme

    def write_components(self):
        for component in self.components.values():
            self.write_component(component)

    def write_component(self, component):
        out_file = os.path.join(self.out_dir, component.file_path())
        write(out_file, component.compiled_content(self.get_variable_renames(component)))

    def write_base_import(self):
        file_path = os.path.join(self.basePath, SRC_DIR, BASE_IMPORTS_PATH)
        semantic_import = decode(self.zipfile.read(file_path)).split('\n')
        imports = "\n".join([
            *semantic_import[0:9],
            "  " + self.package["description"],
            "  Import this file, then import theme files, then override variables",
            *semantic_import[10:12],
            "/* Default Variables */",
            *self.build_variables_import(),
            "",
            *semantic_import[11:],
            "/* Default Overrides */",
            *self.build_overrides_import()
        ])
        write(os.path.join(self.out_dir, BASE_IMPORTS_PATH), imports)

    def build_variables_import(self):
        theme_variables = self.themes[DEFAULT_THEME][VARIABLES_EXTENSION].values()
        return ["@import \"" + component.file_path(DEFAULT_THEME) + "\";" for component in theme_variables]

    def build_overrides_import(self):
        theme_overrides = self.themes[DEFAULT_THEME][OVERRIDES_EXTENSION].values()
        return ["@import \"" + component.file_path(DEFAULT_THEME) + "\";" for component in theme_overrides]

    def write_themes(self):
        for (name, theme) in self.themes.items():
            for overrides in theme[OVERRIDES_EXTENSION].values():
                self.write_theme_component(name, overrides)
            for variables in theme[VARIABLES_EXTENSION].values():
                self.write_theme_component(name, variables)

    def write_theme_component(self, name, component):
        out_dir = os.path.join(self.out_dir, component.file_path(name))
        write(out_dir, component.compiled_content(self.get_variable_renames(component)))

    def get_variable_renames(self, component):
        return self.themes[DEFAULT_THEME][VARIABLES_EXTENSION][component.name].variable_renames

    def write_package(self):
        packagePublishKeys = ["name", "author", "title", "description", "license", "homepage", "repository", "bugs"]
        package = {key: self.package[key] for key in packagePublishKeys}
        package["version"] = self.version
        write(os.path.join(self.out_dir, PACKAGE_PATH), json.dumps(package))

    def copy_readme(self):
        copy('README.md', self.out_dir)

    def copy_license(self):
        copy('LICENSE.md', self.out_dir)


class Component:
    def __init__(self, name, file_path, content):
        self.name = name
        self.path = file_path
        self.content = decode(content)

    def __repr__(self):
        return "Component (\"" + self.name + "\", \"" + self.path + "\")"

    def compiled_content(self, variable_renames):
        content = rename_variables_in_less_file(variable_renames, self.content)

        content = find_theme_comment.sub('', content)
        content = find_type.sub('', content)
        content = find_element.sub('', content)
        content = find_theme_import.sub('', content)
        content = find_load_overloads.sub('', content)
        content = find_load_fonts.sub('', content)

        return content

    def file_path(self):
        return os.path.join(DEFINITIONS_DIR, self.path) + '.' + LESS_EXTENSION


class ThemeVariables:
    def __init__(self, name, file_path, content):
        self.name = name
        self.path = file_path
        self.content = decode(content)

        self.variables = dict(variable_parser.findall(self.content))
        if file_path.startswith(GLOBALS_DIRECTORY):
            variable_rename = identity
        else:
            variable_rename = variable_with_name(name)

        variables = sorted(self.variables.keys())

        self.variable_renames = [(v, variable_rename(v)) for v in variables]

    def compiled_content(self, variable_renames):
        renamed_content = rename_variables_in_less_file(variable_renames, self.content)
        for (_, new_name) in variable_renames:
            renamed_content = re.sub(r'@' + new_name + r': @' + new_name + r';\n',  '', renamed_content)
        return renamed_content

    def file_path(self, theme_name):
        return os.path.join(THEMES_DIR, theme_name, self.path + '.' + VARIABLES_EXTENSION + '.' + LESS_EXTENSION)


class ThemeOverrides:
    def __init__(self, name, file_path, content):
        self.name = name
        self.path = file_path
        self.content = decode(content)

    def compiled_content(self, variable_renames):
        return rename_variables_in_less_file(variable_renames, self.content)

    def file_path(self, theme_name):
        return os.path.join(THEMES_DIR, theme_name, self.path + '.' + OVERRIDES_EXTENSION + '.' + LESS_EXTENSION)


def identity(x): return x


def rename_variables_in_less_file(variable_renames, content):
    for (name, new_name) in variable_renames:
        content = re.sub(r'@' + name + r'([^A-Za-z])',  '@' + new_name + '\\1', content)
    return content


def variable_with_name(name):
    return lambda variable: name + variable[0].upper() + variable[1:]


def in_path(parent):
    return lambda filename:\
        filename.startswith(parent) and filename.rstrip('/') != parent.rstrip('/')


def is_type(extension):
    return lambda filename:\
        filename.endswith("." + extension)

lessFile = is_type(LESS_EXTENSION)
overridesFile = is_type(OVERRIDES_EXTENSION)
variablesFile = is_type(VARIABLES_EXTENSION)


def child_of(parent):
    is_ancestor = in_path(parent)
    sub_name = sub_path(parent)
    return lambda filename: is_ancestor(filename) and '/' not in sub_name(filename)


def sub_path(parent):
    length = len(parent)
    return lambda filename: filename[length:].strip('/')


def remove_extension(extension):
    length = len(extension) + 1
    return lambda filename: filename[:-length]


def decode(b):
    return b.decode("utf-8")


def write(filename, content):
    d = os.path.dirname(filename)
    if not os.path.exists(d):
        os.makedirs(d)
    with open(filename, 'w') as file:
        file.write(content)


def copy(filename, out_dir):
    with open(filename, "r") as file:
        write(os.path.join(out_dir, filename), file.read())

if __name__ == "__main__":
    p = Project()
    p.write_components()
    p.write_themes()
    p.write_base_import()
    p.write_package()
    p.copy_readme()
    p.copy_license()
