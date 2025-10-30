#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) 2021 Huawei Device Co., Ltd.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
import fnmatch


def _read_file(file):
    contents = []
    with open(file, 'r') as f:
        contents = f.readlines()

    for index in range(len(contents)):
        contents[index] = contents[index].strip('\n')
    return contents


def parse_import_class(java_file):
    imports = []
    with open(java_file) as f:
        for l in f:
            # Strip unindented comments.
            l = re.sub(r'^(?://.*|/?\*.*?(?:\*/\s*|$))', '', l)

            match = re.match(r'import\s+(static)*\s*(.*?);', l)
            if match:
                imports.append(match.group(2))
    return imports


def _get_java_source_files(java_sources_file_path):
    java_files = []
    for item in _read_file(java_sources_file_path):
        f = item.split(' ')
        java_files = java_files + f
    return java_files


def _check_file_suffix(java_files):
    for file in java_files:
        if not file.endswith(".java"):
            print("Warning: {} Is Not A Java File !".format(file))
            java_files.remove(file)
            java_files.remove('')


def _print_in_red(msg):
    print('\033[91m' + msg + '\033[0m')


def remove_ignored(names, ignored_patterns):
    removed = []
    if ignored_patterns == []:
        return names
    for n in names:
        found = False
        for p in ignored_patterns:
            if fnmatch.fnmatch(n, p):
                found = True
                break
        if not found:
            removed.append(n)
    return removed


def allowlist_check(allow_list_file_path,
                    java_sources_file_path,
                    all_aosp_imports_file):
    checklist = _read_file(allow_list_file_path)
    all_aosp_imports = _read_file(all_aosp_imports_file)

    java_files = _get_java_source_files(java_sources_file_path)
    _check_file_suffix(java_files)

    for java_file in java_files:
        imports = parse_import_class(java_file)
        aosp_imports = set(imports) & set(all_aosp_imports)
        mixed = set(aosp_imports) & set(checklist)

        # aosp_imports should be a subset of checklist
        if mixed != set(aosp_imports):
            diff = set(aosp_imports) - set(checklist)
            _print_in_red(
                "Error: {}: imported {}, which is not allowed in {}"
                .format(java_file, ' '.join(diff), allow_list_file_path))
            return "FAILURE"
    return "PASS"


def blocklist_check(block_list_file_path,
                    java_sources_file_path):
    checklist = _read_file(block_list_file_path)

    java_files = _get_java_source_files(java_sources_file_path)
    _check_file_suffix(java_files)

    for f in java_files:
        imports = parse_import_class(f)
        mixed = set(imports) & set(checklist)
        if mixed:
            _print_in_red(
                "Error: {}: imported {}, which is not allowed in {}"
                .format(f, ' '.join(mixed), block_list_file_path))
            return "FAILURE"
    return "PASS"
