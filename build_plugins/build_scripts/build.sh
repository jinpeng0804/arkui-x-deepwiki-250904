#!/bin/bash
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

set -e
set +e
echo "++++++++++++++++++++++++++++++++++++++++"
function check_shell_environment() {
  case $(uname -s) in 
    Linux)
          shell_result=$(/bin/sh -c 'echo ${BASH_VERSION}')
          if [ -n "${shell_result}" ]; then
            echo "The system shell is bash ${shell_result}"
          else
            echo -e "\033[33m Your system shell isn't bash, we recommend you to use bash, because some commands may not be supported in other shells, such as pushd and shopt are not supported in dash. \n You can follow these tips to modify the system shell to bash on Ubuntu: \033[0m"
            echo -e "\033[33m [1]:Open the Terminal tool and execute the following command: sudo dpkg-reconfigure dash \n [2]:Enter the password and select <no>  \033[0m"
          fi
          ;;
    Darwin)
          echo "Darwin system is not supported yet"
          ;;
    *)
          echo "Unsupported this system: $(uname -s)"
          exit 1
  esac
}

check_shell_environment 

echo "++++++++++++++++++++++++++++++++++++++++"
date +%F' '%H:%M:%S
echo $@

export SOURCE_ROOT_DIR=$(cd $(dirname $0);pwd)

while [[ ! -f "${SOURCE_ROOT_DIR}/.gn" ]]; do
    SOURCE_ROOT_DIR="$(dirname "${SOURCE_ROOT_DIR}")"
    if [[ "${SOURCE_ROOT_DIR}" == "/" ]]; then
        echo "Cannot find source tree containing $(pwd)"
        exit 1
    fi
done

if [[ "${SOURCE_ROOT_DIR}x" == "x" ]]; then
  echo "Error: SOURCE_ROOT_DIR cannot be empty."
  exit 1
fi

host_cpu_prefix=""

case $(uname -m) in
    *x86_64)
        host_cpu_prefix="x86"
        ;;
    *arm*)
        host_cpu_prefix="arm64"
        ;;
    *)
        echo "\033[31m[OHOS ERROR] Unsupported host arch: $(uname -m)\033[0m"
        RET=1
        exit $RET
esac

case $(uname -s) in
    Darwin)
        HOST_DIR="darwin-$host_cpu_prefix"
        HOST_OS="darwin"
        ;;
    Linux)
        HOST_DIR="linux-$host_cpu_prefix"
        HOST_OS="linux"
        ;;
    *)
        echo "Unsupported host platform: $(uname -s)"
        RET=1
        exit $RET
esac

# set python3
PYTHON3_DIR=${SOURCE_ROOT_DIR}/prebuilts/python/${HOST_DIR}/current/
PYTHON3=${PYTHON3_DIR}/bin/python3
PYTHON=${PYTHON3_DIR}/bin/python
if [[ ! -f "${PYTHON3}" ]]; then
  echo -e "\033[33m Please execute the build/prebuilts_download.sh \033[0m"
  exit 1
else
  if [[ ! -f "${PYTHON}" ]]; then
    ln -sf "${PYTHON3}" "${PYTHON}"
  fi
fi

export PATH=${SOURCE_ROOT_DIR}/prebuilts/build-tools/${HOST_DIR}/bin:${PYTHON3_DIR}/bin:$PATH

# set nodejs and ohpm
export PATH=${SOURCE_ROOT_DIR}/prebuilts/build-tools/common/nodejs/node-v14.21.1-${HOST_OS}-x64/bin:$PATH
export NODE_HOME=${SOURCE_ROOT_DIR}/prebuilts/build-tools/common/nodejs/node-v14.21.1-${HOST_OS}-x64
export PATH=${SOURCE_ROOT_DIR}/prebuilts/build-tools/common/oh-command-line-tools/ohpm/bin:$PATH
echo "node version is $(node -v)"
echo "npm version is $(npm -v)"
npm config set registry https://repo.huaweicloud.com/repository/npm/
npm config set @ohos:registry https://repo.harmonyos.com/npm/
npm config set strict-ssl false

function init_ohpm() {
  TOOLS_INSTALL_DIR="${SOURCE_ROOT_DIR}/prebuilts/build-tools/common"
  cd ${TOOLS_INSTALL_DIR}
  commandlineVersion=2.0.1.0
  echo "download oh-command-line-tools"
  if [[ "$HOST_OS" == "linux" ]]; then
      wget https://contentcenter-vali-drcn.dbankcdn.cn/pvt_2/DeveloperAlliance_package_901_9/a6/v3/cXARnGbKTt-4sPEi3GcnJA/ohcommandline-tools-linux-2.0.0.1.zip\?HW-CC-KV\=V1\&HW-CC-Date\=20230512T075353Z\&HW-CC-Expire\=315360000\&HW-CC-Sign\=C82B51F3C9F107AB460EC26392E25B2E20EF1A6CAD10A26929769B21B8C8D5B6 -O ohcommandline-tools-linux.zip
      unzip ohcommandline-tools-linux.zip
  elif [[ "$HOST_OS" == "darwin" ]]; then
      wget https://contentcenter-vali-drcn.dbankcdn.cn/pvt_2/DeveloperAlliance_package_901_9/3c/v3/R0CXGn4UTvqN09KaTg72Bw/ohcommandline-tools-mac-2.0.0.1.zip\?HW-CC-KV\=V1\&HW-CC-Date\=20230512T073701Z\&HW-CC-Expire\=315360000\&HW-CC-Sign\=7E0D1CBD8ACB6D301E513813745EFA96D6763EF60BBD23455CE6BE797610F488 -O ohcommandline-tools-mac.zip
      unzip ohcommandline-tools-mac.zip
  fi
  OHPM_HOME=${TOOLS_INSTALL_DIR}/oh-command-line-tools/ohpm
  chmod +x ${OHPM_HOME}/bin/init
  echo "init ohpm"
  ${OHPM_HOME}/bin/init
  export PATH=${OHPM_HOME}/bin:$PATH
  echo "ohpm version is $(ohpm -v)"
  ohpm config set registry https://repo.harmonyos.com/ohpm/
  ohpm config set strict_ssl false
  cd ${SOURCE_ROOT_DIR}
}
if [[ ! -f "${SOURCE_ROOT_DIR}/prebuilts/build-tools/common/oh-command-line-tools/ohpm/bin/ohpm" ]]; then
  echo "start set ohpm"
  init_ohpm
  if [[ "$?" -ne 0 ]]; then
    echo "ohpm init failed!"
    exit 1
  fi
fi

BUILD_DIRECTORY=${SOURCE_ROOT_DIR}/build
BUILD_CXX_GNI=${BUILD_DIRECTORY}/templates/cxx/cxx.gni
BUILD_PATCH=${SOURCE_ROOT_DIR}/build_plugins/build_scripts/arkui-x-build.patch

if [ -f ${BUILD_CXX_GNI} ]; then
  rm -f ${BUILD_CXX_GNI}
fi
patch -p1 --fuzz=0 --no-backup-if-mismatch -i ${BUILD_PATCH} -d ${BUILD_DIRECTORY}

${PYTHON3} ${SOURCE_ROOT_DIR}/build_plugins/build_scripts/apply_patch.py --source-root-dir ${SOURCE_ROOT_DIR}
if [[ "$?" -ne 0 ]]; then
  exit 1
fi

${PYTHON3} ${SOURCE_ROOT_DIR}/build/scripts/tools_checker.py

flag=true
build_android=false
args_list=$@
for var in $@
do
  OPTIONS=${var%%=*}
  PARAM=${var#*=}
  if [[ "$OPTIONS" == "build_android" && "$PARAM" == "true" ]]; then
    build_android=true
  fi
  if [[ "$OPTIONS" == "using_hb_new" && "$PARAM" == "false" ]]; then
    flag=false
    ${PYTHON3} ${SOURCE_ROOT_DIR}/build/scripts/entry.py --source-root-dir ${SOURCE_ROOT_DIR} $args_list
    break
  fi
done

if [[ ${flag} == "true" && ${build_android} == "true" ]]; then
  android_args_list=${args_list/ios/android}
  ${PYTHON3} ${SOURCE_ROOT_DIR}/build/hb/main.py build $android_args_list
  android_build_result=$?
fi

if [[ ${flag} == "true" ]]; then
  ${PYTHON3} ${SOURCE_ROOT_DIR}/build/hb/main.py build $args_list
  build_result=$?
fi

if [[ $build_result -ne 0 || $android_build_result -ne 0 ]]; then
    echo -e "\033[31m=====build ${product_name} error=====\033[0m"
    exit 1
fi
echo -e "\033[32m=====build ${product_name} successful=====\033[0m"

date +%F' '%H:%M:%S
echo "++++++++++++++++++++++++++++++++++++++++"
