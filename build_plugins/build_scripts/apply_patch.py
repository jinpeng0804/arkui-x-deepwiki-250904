#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2025 Huawei Device Co., Ltd.
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

import json
import subprocess
import os
import sys
import optparse

def is_patch_applied(patch, repo_path, source_root_dir):
    if patch["type"] == "commit":
        try:
            value = "'" + patch["commitMessage"] + "'"
            command = f"git log --oneline --no-abbrev-commit | grep {value}"
            result = subprocess.run(
                command,
                shell=True,
                check=True,
                cwd=repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            output = result.stdout.decode().strip()
            if output:
                print(f"Found matching commits:\n{output}")
                return True
        except subprocess.CalledProcessError:
            print("No matching commits found.")
            return False
    elif patch["type"] == "diff":
        try:
            diff_path = os.path.join(source_root_dir, patch["commit"])
            if not os.path.exists(diff_path):
                print(f'{diff_path} does not exist')
                return True
            subprocess.run(
                ["git", "apply", "--check", diff_path],
                cwd=repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            print(f"apply diff {diff_path}")
            return False
        except subprocess.CalledProcessError:
            print(f"skip {diff_path}")
            return True
    else:
        print(f"Invalid patch type: {patch['type']}")
        return True

def apply_patch(patch, repo_path, source_root_dir):
    if patch["type"] == "commit":
        print(f"Applying commit: {patch['commit']}")
        subprocess.run(
            ["git", "cherry-pick", patch["commit"]],
            check=True,
            cwd=repo_path,
        )
        print(f"Successfully applied commit: {patch['commit']}")
    elif patch["type"] == "diff":
        print(f"Applying diff file: {patch['commit']}")
        diff_path = os.path.join(source_root_dir, patch["commit"])
        subprocess.run(
            ["git", "apply", diff_path],
            check=True,
            cwd=repo_path,
        )
        print(f"Successfully applied diff file: {patch['commit']}")

def main():
    parser = optparse.OptionParser()
    parser.add_option('--source-root-dir')
    args, _ = parser.parse_args()
    if args.source_root_dir is None:
        print('Error: source_root_dir must be provided to apply_patch.py')
        return -1

    json_file = os.path.join(args.source_root_dir, 'build_plugins/build_scripts/patches.json')
    if not os.path.exists(json_file):
        print(f"Error: JSON file {json_file} not found.")
        sys.exit(1)

    with open(json_file, "r") as f:
        configs = json.load(f)

    for repo_config in configs:
        repo_path = repo_config.get("repo")
        patches = repo_config.get("patches", [])

        if not repo_path:
            print("Error: 'repo' field is missing in config.")
            continue

        code_path = os.path.join(args.source_root_dir, repo_path)
        if not os.path.exists(code_path):
            print(f"Error: Repository path '{code_path}' does not exist.")
            continue

        print(f"Processing repository: {code_path}")
        for patch in patches:
            try:
                if is_patch_applied(patch, code_path, args.source_root_dir):
                    print(f"skip {patch} success")
                    continue
                apply_patch(patch, code_path, args.source_root_dir)
            except Exception as e:
                print(f"Error applying patch : {e}")
                sys.exit(1)

    print("All patches applied successfully!")

if __name__ == "__main__":
    JSON_FILE = "patches.json"
    main()