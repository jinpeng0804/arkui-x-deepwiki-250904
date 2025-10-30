#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2023 Huawei Device Co., Ltd.
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


import argparse
import os
import sys
import subprocess
import shutil


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root-dir', help='')
    parser.add_argument('--output-dir', help='')
    parser.add_argument('--app-name', help='')
    parser.add_argument('--host-os', help='')

    options = parser.parse_args()
    return options


def compile_apk(root_dir, output_dir, app_name):
    apk_dirs = [os.path.join(root_dir, 'android/app/build/outputs/apk/release'),
                os.path.join(root_dir, 'android/library/build/outputs/aar')]
    output_dir = os.path.join(output_dir, 'android', app_name)
    for src_dir in apk_dirs:
        if os.path.exists(src_dir):
            shutil.copytree(src_dir, output_dir, dirs_exist_ok=True)


def compile_app(root_dir, output_dir, app_name):
    app_dirs = [os.path.join(root_dir, 'ios/build/outputs/app'),
                os.path.join(root_dir, 'ios/build/outputs/framework')]
    output_dir = os.path.join(output_dir, 'ios', app_name)
    for src_dir in app_dirs:
        if os.path.exists(src_dir):
            shutil.copytree(src_dir, output_dir, dirs_exist_ok=True)


def main():
    options = parse_args()
    compile_apk(options.root_dir, options.output_dir, options.app_name)
    if options.host_os == 'mac':
        compile_app(options.root_dir, options.output_dir, options.app_name)


if __name__== '__main__':
    sys.exit(main())
