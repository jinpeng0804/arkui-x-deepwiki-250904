# 编译构建

-   [简介](#section11660541593)
-   [目录](#section161941989596)
-   [约束与环境配置](#section2029921310472)
-   [说明](#section1312121216216)

## 简介

ArkUI-X项目编译构建提供了一个基于GN和Ninja的编译构建框架。基础构建流程Fork [OpenHarmony build](https://gitee.com/openharmony/build)仓，并在OpenHarmony构建基础上新增Android SDK/NDK和iOS SDK编译支持。

## 目录

```
/build_plugins                     # 编译构建主目录
├── app                            # 应用编译相关配置
├── build_scripts                  # 编译相关的shell脚本
├── config                         # 编译相关的配置项
│   ├── aosp
│   ├── ios
│   └── ...
├── prebuilts_download_config.json # 预编译工具链下载配置
├── scripts                        # 编译相关的python脚本
├── sdk                            # ArkUI-X SDK自动打包配置
├── templates                      # c/c++/java编译模板定义
├── toolchain                      # 编译工具链配置
└── version.gni                    # ArkUI-X版本信息
```

## 约束与环境配置

- 编译环境需要Ubuntu18.04及以上版本，macOS需要11.6.2及以上版本。

- 安装编译所需的程序包。

  [Linux]

  ```
  sudo apt-get install binutils git-core gnupg flex bison gperf build-essential zip curl zlib1g-dev gcc-multilib g++-multilib libc6-dev-i386 lib32ncurses5-dev x11proto-core-dev libx11-dev lib32z-dev ccache libgl1-mesa-dev libxml2-utils xsltproc unzip m4
  ```

  [Mac]

  ```
  brew install wget coreutils
  ```

### 配置Java环境
**说明：** 建议下载JDK11.0.2以上版本，下载请点击[此处](https://repo.huaweicloud.com/openjdk/)。

  [Linux]

  ```shell
  // 配置环境变量
  export JAVA_HOME=/home/usrername/path-to-java-sdk
  export PATH=${JAVA_HOME}/bin:${PATH}
  ```

  [Mac]

  ```shell
  // 配置环境变量
  export JAVA_HOME=/Users/usrername/path-to-java-sdk
  export PATH=$JAVA_HOME/bin:$PATH
  ```

### 配置Android SDK环境

  [Linux]

  通过[命令行工具](https://developer.android.google.cn/studio#command-line-tools-only)下载和管理Android SDK，命令行工具使用说明详见[sdkmanager](https://developer.android.google.cn/studio/command-line/sdkmanager)官方指导。SDK版本下载要求如下：

  ```shell
  ./sdkmanager --install "ndk;21.3.6528147" --sdk_root=/home/usrername/path-to-android-sdk
  ./sdkmanager --install "platforms;android-26" --sdk_root=/home/usrername/path-to-android-sdk
  ./sdkmanager --install "build-tools;28.0.3" --sdk_root=/home/usrername/path-to-android-sdk
  ```

  ```shell
  // 配置环境变量
  export ANDROID_HOME=/home/usrername/path-to-android-sdk
  export PATH=${ANDROID_HOME}/tools:${ANDROID_HOME}/tools/bin:${ANDROID_HOME}/build-tools/28.0.3:${ANDROID_HOME}/platform-tools:${PATH}
  ```

  [Mac]

  通过IDE [SDK管理器](https://developer.android.google.cn/studio/intro/update#sdk-manager)下载和管理Android SDK，NDK版本要求为：21.3.6528147，SDK Platform版本为：26。

  ```shell
  // 配置环境变量
  export ANDROID_HOME=/Users/usrername/path-to-android-sdk
  export PATH=$ANDROID_HOME/tools:$ANDROID_HOME/tools/bin:$ANDROID_HOME/build-tools/28.0.3:$ANDROID_HOME/platform-tools:$PATH
  ```

### 配置iOS SDK环境

  - Xcode和Command Line Tools for Xcode应用可前往苹果商店下载安装。
  - Command Line Tools也可使用命令方式安装:

    ```shell
    xcode-select --install
    ```

## 说明

1.  代码根目录下执行ArkUI的跨平台编译命令，示例：

    ```shell
    ./build.sh --product-name arkui-x --target-os android
    ```

2.  编译命令支持选项：

    ```
    --product-name    # 必须  编译的产品名称，如：arkui-x
    --target-os       # 必须  编译的跨平台目标，如：android或ios
    --build-target    # 可选  指定编译目标，可以指定多个
    --runtime-mode    # 可选  默认release，可选：debug或profile
    --gn-args         # 可选  gn参数，支持指定多个
    --help, -h        # 可选  命令行help辅助命令
    ```

3.  常用的gn参数：

    ```
    --gn-args gen_full_sdk=true      # 编译全版本sdk, 包含release版本、debug版本、profile版本
    ```

4.  支持模板类型

    ```
    ohos_executable
    ohos_shared_library
    ohos_static_library
    ohos_source_set
    ohos_combine_jars
    java_library
    
    # 预编译模板：
    ohos_prebuilt_executable
    ohos_prebuilt_shared_library
    aosp_system_java_prebuilt
    ```

    **例子1：**

    _ohos\_shared\_library示例：_

    ```
    import("//build/ohos.gni")
    ohos_shared_library("helloworld") {
      sources = []
      include_dirs = []
      cflags = []
      cflags_c = []
      cflags_cc = []
      ldflags = []
      configs = []
      deps =[]  # 部件内模块依赖
    
      output_name = "" # 可选，模块输出名
      output_extension = "" # 可选，模块名后缀
      part_name = "" # 必选，所属部件名称
    }
    ```

    **例子2：**

    _java\_library示例：_

    ```
    import("//build/ohos.gni")
    java_library("foo_java") {
      java_files = [
        "ohos/ace/adapter/Foo.java",
        "ohos/ace/adapter/FooInterface.java",
        "ohos/ace/adapter/FooService.java"
      ]
      deps = [
        ":bar_java"
      ]
    }
    ```
