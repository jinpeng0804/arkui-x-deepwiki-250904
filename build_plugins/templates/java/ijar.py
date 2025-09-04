#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import subprocess
import sys
import shutil

from util import build_utils


def main():
  # The point of this wrapper is to use atomic_output so that output timestamps
  # are not updated when outputs are unchanged.
  # here copy in_jar to out_jar
  in_jar, out_jar = sys.argv[1:]
  with build_utils.atomic_output(out_jar) as f:
      shutil.copyfile(in_jar, f.name)


if __name__ == '__main__':
  main()
