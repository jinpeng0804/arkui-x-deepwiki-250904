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

from util import build_utils


def _ParseAndFlattenGnLists(gn_lists):
    ret = []
    for arg in gn_lists:
        ret.extend(build_utils.parse_gn_list(arg))
    return ret


def _ParseArgs(args):
    args = build_utils.expand_file_args(args)
    parser = optparse.OptionParser()
    build_utils.add_depfile_option(parser)

    parser.add_option('--depjars',
                      action='append',
                      help='path to all dependent jars')
    parser.add_option('--inputjars',
                      action='append',
                      help='path to all input jars')
    parser.add_option('--strip_args',
                      action='append',
                      help='parameters for merge operation')
    parser.add_option('--output_jar', help='output combined jar path')

    options, _ = parser.parse_args(args)

    if options.depjars:
        options.depjars = _ParseAndFlattenGnLists(options.depjars)
        # remove 'u'(stands for unicode) from list
        options.depjars = [str(item) for item in options.depjars]
    options.inputjars = _ParseAndFlattenGnLists(options.inputjars)
    input_jars = options.inputjars
    input_jars = [str(item) for item in input_jars]

    return options, input_jars


def main(args):
    options, input_jars = _ParseArgs(args)
    added_jars = set()
    if options.depjars is None:
        options.depjars = []
    for jar in (input_jars + options.depjars):
        if jar not in added_jars:
            added_jars.add(jar)

    merge_args = ["--stripFile", "module-info.class"]
    if options.strip_args:
        for arg in options.strip_args:
            merge_args += ["--stripFile", arg]
    build_utils.call_and_write_depfile_if_stale(lambda: build_utils.merge_zips(
        options.output_jar, sorted(added_jars), merge_args=merge_args),
                                           options,
                                           depfile_deps=(options.depjars) +
                                           (input_jars),
                                           input_paths=(options.depjars) +
                                           (input_jars),
                                           output_paths=([options.output_jar]),
                                           force=False,
                                           add_pydeps=False)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
