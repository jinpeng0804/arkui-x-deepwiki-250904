#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

import sys
import os
import argparse
import json

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
from scripts.util.file_utils import read_json_file, \
    write_json_file  # noqa: E402


def get_lib_suffix(lib_type):
    if lib_type == 'shared_library':
        return '.so'
    elif lib_type == 'static_library':
        return '.a'
    else:
        return ''


def get_lable_name(lib_type, lib_name):
    if lib_type == 'static_library':
        return '{}_static'.format(lib_name)
    elif lib_type == 'jar':
        return '{}_java'.format(lib_name)
    elif lib_type == 'maple':
        return '{}_maple_java'.format(lib_name)
    else:
        return lib_name


def get_target_platform():
    return 'android_arm64'


def get_module_source_lib(libraries, lib_name):
    if libraries:
        lib_desc = libraries.get(lib_name)
        if lib_desc:
            source_libs = lib_desc.get('source')
            if source_libs:
                return source_libs.get(get_target_platform())
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--aosp-deps', nargs='+', required=True)
    parser.add_argument('--aosp-deps-temp-file', required=True)
    args = parser.parse_args()

    lib_type_list = ['shared_library', 'static_library', 'jar', 'maple']

    result = []
    android_sdk_dir = '//libs/android_libs/sdk'
    # examples:
    #   android_deps = [
    #     "shared_library:abc",
    #     "static_library:xxx",
    #     "jar:framework",
    #     "maple:framework"
    #   ]
    #module_info_file = '../../libs/android_libs/sdk/module_info.json'
    #if not os.path.exists(module_info_file):
    #    raise Exception(
    #        "android deps, module info file '{}/module_info.json' not exist.".
    #        format(android_sdk_dir))
    #module_info = read_json_file(module_info_file)
    #if module_info is None:
    #    raise Exception("android deps, read file failed.")

    for android_dep in args.aosp_deps:
        android_dep_desc = android_dep.split(':lib')
        if len(android_dep_desc) != 2:
            continue

        lib_type = android_dep_desc[0]
        if lib_type not in lib_type_list:
            raise Exception(
                "android dep '{}' config error, lib type not support.".format(
                    android_dep))

        lib_name = android_dep_desc[1]
        info_dict = {}
        #build_file_path = '{}/{}/android_arm64'.format(android_sdk_dir,
        #                                               lib_type)

        # cc library
        if lib_type in ['shared_library', 'static_library']:
            #source_lib = get_module_source_lib(module_info.get(lib_type),
            #                                   lib_name)
            #if source_lib:
            #    source_lib_path = os.path.relpath(source_lib, lib_type)
            #else:
            #    source_lib_path = os.path.join('{}{}'.format(
            #        lib_name, get_lib_suffix(lib_type)))

            info_dict['source'] = lib_name
        #elif lib_type in ['jar', 'maple']:
        #    build_file_path = '{}/java'.format(android_sdk_dir)

        info_dict['label'] = lib_name

        result.append(info_dict)
    write_json_file(args.aosp_deps_temp_file, result)
    return 0


if __name__ == '__main__':
    sys.exit(main())
