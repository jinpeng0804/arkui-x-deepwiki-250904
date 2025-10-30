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

import optparse
import sys
import zipfile
import fnmatch

from util import build_utils


def parse_args(args):
    args = build_utils.expand_file_args(args)
    parser = optparse.OptionParser()
    build_utils.add_depfile_option(parser)

    parser.add_option('--package-names', help='package names')
    parser.add_option('--output', help='target output, used for stamp')
    parser.add_option('--jar-path', help='input jar path')

    options, _ = parser.parse_args(args)
    options.package_names = build_utils.parse_gn_list(options.package_names)
    return options


def check_package_name(options):
    package_names = [p.replace('.', '/') for p in options.package_names]
    with zipfile.ZipFile(options.jar_path) as z:
        for name in z.namelist():
            if name.endswith('.class'):
                found = False
                for p in package_names:
                    if fnmatch.fnmatch(name, p):
                        found = True
                        break
                if found is not True:
                    print(
                      'Warning: class file %s doesn\'t belong to package [%s]'
                      % (name, ', '.join(package_names)))
    build_utils.touch(options.output)


def main(args):
    options = parse_args(args)
    build_utils.call_and_write_depfile_if_stale(lambda: check_package_name(options),
                                           options,
                                           depfile_deps=([options.jar_path]),
                                           input_paths=([options.jar_path]),
                                           output_paths=([options.output]),
                                           input_strings=options.package_names,
                                           force=False,
                                           add_pydeps=False)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
