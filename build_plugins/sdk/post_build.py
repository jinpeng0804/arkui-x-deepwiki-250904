#!/usr/bin/env python3
# coding=utf-8
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


import os
import sys
import argparse
import shutil
import subprocess

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.util.file_utils import read_json_file
from scripts.util.build_utils import extract_all, zip_dir


def build_xcframework(xcframework, framework, sim_framework):
    if os.path.exists(xcframework):
        shutil.rmtree(xcframework)
    proc = subprocess.Popen(['xcodebuild', '-create-xcframework', '-framework', framework,
                             '-framework', sim_framework, '-output', xcframework],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
    proc.communicate()
    if proc.returncode:
        raise Exception('create xcframework error: {}', proc.stderr)


def create_xcframework(sdk_zip_file, sdk_unzip_dir, sdk_install_config):
    cmd = ['unzip', sdk_zip_file]
    proc = subprocess.Popen(cmd, cwd=sdk_unzip_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
    proc.communicate()
    sdk_install_config = read_json_file(sdk_install_config)
    for sdk_install_info in sdk_install_config:
        label = sdk_install_info.get('label')
        install_dir = os.path.join(sdk_unzip_dir, sdk_install_info.get('install_dir'))
        if 'ios-arm64-simulator' in install_dir and install_dir.endswith('.framework'):
            framework_name = os.path.basename(install_dir)
            dylib_name = framework_name.replace('.framework', '')
            arm64_sim_fwk_dir = os.path.dirname(install_dir)
            framework_dir = os.path.dirname(arm64_sim_fwk_dir)
            x86_64_sim_fwk_dir = os.path.join(framework_dir, 'ios-x86_64-simulator')
            arm64_release_fwk_dir = os.path.join(framework_dir, 'ios-arm64-release')
            arm64_debug_fwk_dir = os.path.join(framework_dir, 'ios-arm64')
            arm64_profile_fwk_dir = os.path.join(framework_dir, 'ios-arm64-profile')
            arm64_x86_64_sim_fwk_dir = os.path.join(framework_dir, 'ios-arm64_x86_64-simulator')

            arm64_sim_fwk = os.path.join(arm64_sim_fwk_dir, framework_name)
            x86_64_sim_fwk = os.path.join(x86_64_sim_fwk_dir, framework_name)
            arm64_x86_64_sim_fwk = os.path.join(arm64_x86_64_sim_fwk_dir, framework_name)
            arm64_release_fwk = os.path.join(arm64_release_fwk_dir, framework_name)
            arm64_debug_fwk = os.path.join(arm64_debug_fwk_dir, framework_name)
            arm64_profile_fwk = os.path.join(arm64_profile_fwk_dir, framework_name)

            # replace framework which in file dir to xcframework
            arm64_release_xcfwk_dir = arm64_release_fwk_dir.replace('-arm64', '').replace('framework', 'xcframework')
            arm64_debug_xcfwk_dir = arm64_debug_fwk_dir.replace('-arm64', '').replace('framework', 'xcframework')
            arm64_profile_xcfwk_dir = arm64_profile_fwk_dir.replace('-arm64', '').replace('framework', 'xcframework')

            xcframework_name = dylib_name + '.xcframework'
            arm64_release_xcfwk = os.path.join(arm64_release_xcfwk_dir, xcframework_name)
            arm64_debug_xcfwk = os.path.join(arm64_debug_xcfwk_dir, xcframework_name)
            arm64_profile_xcfwk = os.path.join(arm64_profile_xcfwk_dir, xcframework_name)

            # merge x86_64 simulator and arm64 simulator
            shutil.copytree(arm64_sim_fwk, arm64_x86_64_sim_fwk, dirs_exist_ok=True)
            proc1 = subprocess.Popen(['lipo', '-create', '{}/{}'.format(arm64_sim_fwk, dylib_name),
                             '{}/{}'.format(x86_64_sim_fwk, dylib_name), '-output',
                             '{}/{}'.format(arm64_x86_64_sim_fwk, dylib_name)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
            proc1.communicate()
            if proc1.returncode:
                raise Exception('merge framework error: {}', proc1.stderr)

            # create arm64_x86_64 simulator for release version
            if os.path.exists(arm64_release_fwk):
                build_xcframework(arm64_release_xcfwk, arm64_release_fwk, arm64_x86_64_sim_fwk)

            # create arm64_x86_64 simulator for profile version
            if os.path.exists(arm64_profile_fwk):
                build_xcframework(arm64_profile_xcfwk, arm64_profile_fwk, arm64_x86_64_sim_fwk)

            # create arm64_x86_64 simulator for debug version
            if os.path.exists(arm64_debug_fwk):
                build_xcframework(arm64_debug_xcfwk, arm64_debug_fwk, arm64_x86_64_sim_fwk)

            if os.path.exists(arm64_x86_64_sim_fwk):
                shutil.rmtree(arm64_x86_64_sim_fwk)

    # package sdk
    if os.path.exists(sdk_zip_file):
        os.remove(sdk_zip_file)
    zip_dir(sdk_zip_file, sdk_unzip_dir)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-file', required=True)
    parser.add_argument('--host-os', required=True)
    parser.add_argument('--sdk-out-dir', required=True)
    parser.add_argument('--arch', required=True)
    parser.add_argument('--sdk-version', required=True)
    parser.add_argument('--release-type', required=True)
    args = parser.parse_args()

    current_dir = os.getcwd()
    sdk_zip_file = os.path.join(current_dir, args.sdk_out_dir, 'darwin/arkui-x-darwin-{}-{}-{}.zip'
                               .format(args.arch, args.sdk_version, args.release_type))
    sdk_unzip_dir = 'sdk_unzip_dir'
    os.makedirs(sdk_unzip_dir, exist_ok=True)

    if args.host_os == 'mac':
        create_xcframework(sdk_zip_file, sdk_unzip_dir, args.input_file)


if __name__ == '__main__':
    sys.exit(main())
