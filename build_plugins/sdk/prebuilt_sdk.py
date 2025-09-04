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


import requests
import json
import datetime
import os
import sys
import tarfile
import subprocess
import argparse
import shutil

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from urllib.request import urlretrieve
from scripts.util.file_utils import read_json_file


def find_top():
    cur_dir = os.getcwd()
    while cur_dir != "/":
        build_scripts = os.path.join(
            cur_dir, 'build/config/BUILDCONFIG.gn')
        if os.path.exists(build_scripts):
            return cur_dir
        cur_dir = os.path.dirname(cur_dir)


def reporthook(data_download, data_size, total_size):
    '''
    display the progress of download
    :param data_download: data downloaded
    :param data_size: data size
    :param total_size: remote file size
    :return:None
    '''
    progress = int(0)
    if progress != int(data_download * data_size * 1000 / total_size):
        progress = int(data_download * data_size * 1000 / total_size)
        print("\rDownloading: %5.1f%%" %
              (data_download * data_size * 100.0 / total_size), end="")
        sys.stdout.flush()


def download(download_url, savepath):
    filename = os.path.basename(download_url)

    if not os.path.isfile(os.path.join(savepath, filename)):
        print('Downloading data form %s' % download_url)
        urlretrieve(download_url, os.path.join(
            savepath, filename), reporthook=reporthook)
        print('\nDownload finished!')
    else:
        print("\nFile exists!")

    filesize = os.path.getsize(os.path.join(savepath, filename))
    print('File size = %.2f Mb' % (filesize/1024/1024))


def extract_file(filename):

    target_dir = os.path.dirname(filename)

    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    with tarfile.open(filename, "r:gz") as tar:
        tar.extractall(target_dir)

    if os.path.exists(os.path.join(target_dir, "daily_build.log")):
        os.remove(os.path.join(target_dir, "daily_build.log"))
    if os.path.exists(os.path.join(target_dir, "manifest_tag.xml")):
        os.remove(os.path.join(target_dir, "manifest_tag.xml"))


def build_arkuix_sdk():
    src_root = find_top()
    build_android = ['{}/build.sh'.format(src_root), '--product-name', 'arkui-x',
                     '--target-os', 'android', '--gn-args', 'enable_auto_pack=true', 'runtime_mode=release']
    build_ios = ['{}/build.sh'.format(src_root), '--product-name', 'arkui-x',
                     '--target-os', 'ios', '--gn-args', 'enable_auto_pack=true']
    if sys.platform == 'linux':
        proc = subprocess.Popen(build_android)
        proc.communicate()
    elif sys.platform == 'darwin':
        proc1 = subprocess.Popen(build_android)
        proc1.communicate()
        proc2 = subprocess.Popen(build_ios)
        proc2.communicate()


def merge_sdk(sdk_home):
    host_os = sys.platform
    arkuix_sdk_save_path = os.path.join(sdk_home, 'arkuix-sdk')
    arkuix_sdk_path = os.path.join(find_top(), 'out/arkui-x/packages/arkui-x')
    if os.path.exists(arkuix_sdk_path):
        shutil.copytree(arkuix_sdk_path, arkuix_sdk_save_path, dirs_exist_ok=True)
    sdk_dirs = []
    if host_os == 'linux':
        sdk_dirs.append(os.path.join(sdk_home, "ohos-sdk/linux"))
        sdk_dirs.append(os.path.join(sdk_home, "arkuix-sdk/linux"))
    elif host_os == 'darwin':
        sdk_dirs.append(os.path.join(sdk_home, "sdk/packages/ohos-sdk/darwin"))
        sdk_dirs.append(os.path.join(sdk_home, "arkuix-sdk/darwin"))
    for sdk_path in sdk_dirs:
        os.chdir(sdk_path)
        os.system("ls -d */ | xargs rm -rf")
        for filename in os.listdir(sdk_path):
            if filename.endswith(".zip"):
                os.system(f"unzip {filename}")

        os.chdir(sdk_path)
        package_data = read_json_file('toolchains/oh-uni-package.json')
        if package_data:
            api_version = package_data.get('apiVersion')
        os.chdir(sdk_home)
        for dirname in os.listdir(sdk_path):
            dirpath = os.path.join(sdk_path, dirname)
            if os.path.isdir(dirpath):
                subprocess.run(['mkdir', '-p', api_version])
                subprocess.run(['mv', dirpath, api_version])


def npm_install(target_dir):
    package_dirs = []
    for root, dirs, files in os.walk(target_dir):
        if "npm-install.js" in files:
            package_dirs.append(root)
    for package_dir in package_dirs:
        if 'arkui-x' not in package_dir:
            os.chdir(package_dir)
            subprocess.run(["node", "npm-install.js"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--branch', default='master', help='OHOS branch name')
    parser.add_argument('--product-name', default='ohos-sdk', help='OHOS product name')
    parser.add_argument('--clean', action='store_true', help='delete SDK dir')
    args = parser.parse_args()
    sdk_home = os.path.join(find_top(), 'out/sdk')
    os.environ['PATH'] = '{}/{}:{}'.format(find_top(), 'prebuilts/build-tools/common/nodejs/node-v14.21.1-linux-x64/bin/', os.environ.get('PATH'))
    if args.clean:
        if os.path.exists(sdk_home):
            shutil.rmtree(sdk_home)
            print('Clean finished!')
        else:
            print('SDK does not exists, no need to clean.')
        return 0
    if not os.path.exists(sdk_home):
        os.makedirs(sdk_home)
    print(sdk_home)

    # Build ArkUI-X SDK
    build_arkuix_sdk()

    # Download OHOS SDK
    try:
        now_time = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        last_hour = (datetime.datetime.now() +
                     datetime.timedelta(hours=-72)).strftime('%Y%m%d%H%M%S')

        url = "http://ci.openharmony.cn/api/ci-backend/ci-portal/v1/dailybuilds"
        myobj = {"pageNum": 1,
                 "pageSize": 1000,
                 "startTime": "",
                 "endTime": "",
                 "projectName": "openharmony",
                 "branch": args.branch,
                 "component": "",
                 "deviceLevel": "",
                 "hardwareBoard": "",
                 "buildStatus": "success",
                 "buildFailReason": "",
                 "testResult": ""}
        myobj["startTime"] = str(last_hour)
        myobj["endTime"] = str(now_time)
        x = requests.post(url, data=myobj)
        data = json.loads(x.text)
    except BaseException:
        Exception("Unable to establish connection with ci.openharmony.cn")

    products_list = data['result']['dailyBuildVos']
    for product in products_list:
        product_name = product['component']
        if product_name == args.product_name:
            if os.path.exists(os.path.join(sdk_home, product_name)):
                print('{} already exists. Please backup or delete it first!'.format(
                    os.path.join(sdk_home, product_name)))
                print("Download canceled!")
                break

            if product['obsPath'] and os.path.exists(sdk_home):
                download_url = 'http://download.ci.openharmony.cn/' + \
                    product['obsPath']
                save_path2 = sdk_home

            try:
                download(download_url, savepath=save_path2)
                print(download_url, "done")
            except BaseException:

                # remove the incomplete downloaded files
                if os.path.exists(os.path.join(save_path2, os.path.basename(download_url))):
                    os.remove(os.path.join(
                        save_path2, os.path.basename(download_url)))
                Exception("Unable to download {}".format(download_url))

            extract_file(os.path.join(
                save_path2, os.path.basename(download_url)))
            merge_sdk(sdk_home)
            npm_install(save_path2)
            break


if __name__ == '__main__':
    sys.exit(main())
