#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013 The Flutter Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import subprocess

import argparse
import platform
import re
import sys
import os

def GetClangVersion(bitcode, hostcpu) :
  clang_executable = str(os.path.join("..", "..", "prebuilts", "clang","ohos", "darwin-" + hostcpu, "llvm", "bin", "clang++"))
  if bitcode:
    clang_executable = "clang++"
  version = subprocess.check_output([clang_executable, "--version"])
  return version.splitlines()[0]

def GetAceEngineVersion() :
  with open(os.path.join("..", "..", ".repo", "manifests","openharmony.xml"), 'r') as file:
    xml_content = file.read()
  target_path = "foundation/arkui/ace_engine"
  pattern = f'<project path="{target_path}"[^>]*revision="([^"]+)"'
  match = re.search(pattern, xml_content)
  return match.group(1)

def main():

  parser = argparse.ArgumentParser(
      description='Copies the Info.plist and adds extra fields to it like the git hash of the engine')

  parser.add_argument('--source', help='Path to Info.plist source template', type=str, required=True)
  parser.add_argument('--destination', help='Path to destination Info.plist', type=str, required=True)
  parser.add_argument('--bitcode', help='Built with bitcode', action='store_true')
  parser.add_argument('--minversion', help='Minimum device OS version like "9.0"', type=str)
  parser.add_argument('--name', help='Name of the framework', type=str)
  parser.add_argument('--identifier', help='Bundle identifier', type=str)
  parser.add_argument('--sdkversion', help='SDK Version', type=str)
  parser.add_argument('--hostcpu', help='Host CPU', type=str)

  args = parser.parse_args()

  text = open(args.source).read()
  current_cpu = args.hostcpu
  if args.hostcpu == "x64" :
    current_cpu = "x86_64"
  clang_version = GetClangVersion(args.bitcode, current_cpu)
  ace_engine = GetAceEngineVersion()
  split_string = args.sdkversion.split(".")
  short_version = ".".join(split_string[:-1])
  bundle_version = split_string[-1]
  text = text.format(framework_name = args.name, identifier_name = args.identifier, revision = "1.0.0",
                     clang_version = clang_version, min_version = args.minversion, short_version = short_version,
                     bundle_version = bundle_version, ace_engine = ace_engine)

  with open(args.destination, "w") as outfile:
    outfile.write(text)

if __name__ == "__main__":
  main()
