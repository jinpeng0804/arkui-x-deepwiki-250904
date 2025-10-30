#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import distutils.spawn
import itertools
import optparse
import os
import shutil
import re
import sys
import tempfile

from util import build_utils
from util import md5_check
from util import jar_info_utils
import check_api

import jar

MANIFEST = """Manifest-Version: 1.0
Created-By: build_tools
"""

ERRORPRONE_WARNINGS_TO_TURN_OFF = [
    'DoubleBraceInitialization',
    'CatchAndPrintStackTrace',
    'SynchronizeOnNonFinalField',
    'TypeParameterUnusedInFormals',
    'CatchFail',
    'JUnitAmbiguousTestClass',
    # AOSP platform default is always UTF-8.
    'DefaultCharset',
    # Low priority since the alternatives still work.
    'JdkObsolete',
    # We don't use that many lambdas.
    'FunctionalInterfaceClash',
    # There are lots of times when we just want to post a task.
    'FutureReturnValueIgnored',
    # Nice to be explicit about operators, but not necessary.
    'OperatorPrecedence',
    # Just false positives in our code.
    'ThreadJoinLoop',
    # Low priority corner cases with String.split.
    # Linking Guava and using Splitter was rejected
    # in the https://chromium-review.googlesource.com/c/chromium/src/+/871630.
    'StringSplitter',
    # Preferred to use another method since it propagates exceptions better.
    'ClassNewInstance',
    # Nice to have static inner classes but not necessary.
    'ClassCanBeStatic',
    # Explicit is better than implicit.
    'FloatCast',
    # Results in false positives.
    'ThreadLocalUsage',
    # Also just false positives.
    'Finally',
    # False positives for Chromium.
    'FragmentNotInstantiable',
    # Low priority to fix.
    'HidingField',
    # Low priority.
    'IntLongMath',
    # Low priority.
    'BadComparable',
    # Low priority.
    'EqualsHashCode',
    # Nice to fix but low priority.
    'TypeParameterShadowing',
    # Good to have immutable enums, also low priority.
    'ImmutableEnumChecker',
    # False positives for testing.
    'InputStreamSlowMultibyteRead',
    # Nice to have better primitives.
    'BoxedPrimitiveConstructor',
    # Not necessary for tests.
    'OverrideThrowableToString',
    # Nice to have better type safety.
    'CollectionToArraySafeParameter',
    'ObjectToString',
]

ERRORPRONE_WARNINGS_TO_ERROR = [
    # Add warnings to this after fixing/suppressing all instances in our codebase.
    'ArgumentSelectionDefectChecker',
    'AssertionFailureIgnored',
    'FloatingPointLiteralPrecision',
    'JavaLangClash',
    'MissingFail',
    'MissingOverride',
    'NarrowingCompoundAssignment',
    'OrphanedFormatString',
    'ParameterName',
    'ParcelableCreator',
    'ReferenceEquality',
    'StaticGuardedByInstance',
    'StaticQualifiedUsingExpression',
    'UseCorrectAssertInTests',
]


def ProcessJavacOutput(output):
    # These warnings cannot be suppressed even for third party code. Deprecation
    # warnings especially do not help since we must support older aosp version.
    deprecated_re = re.compile(
        r'(Note: .* uses? or overrides? a deprecated API.)$')
    unchecked_re = re.compile(
        r'(Note: .* uses? unchecked or unsafe operations.)$')
    recompile_re = re.compile(r'(Note: Recompile with -Xlint:.* for details.)$')

    def ApplyFilters(line):
        return not (deprecated_re.match(line)
                    or unchecked_re.match(line)
                    or recompile_re.match(line))

    def ApplyColors(line):
        return line

    return '\n'.join(map(ApplyColors,
                         list(filter(ApplyFilters,
                                     output.decode().split('\n')))))


def _ExtractClassFiles(jar_path, dest_dir, java_files):
    """Extracts all .class files not corresponding to |java_files|."""

    # Two challenges exist here:
    # 1. |java_files| have prefixes that are not represented in the the jar paths.
    # 2. A single .java file results in multiple .class files when it contains
    #    nested classes.
    # Here's an example:
    #   source path: ../../base/java/src/org/chromium/Foo.java
    #   jar paths: org/chromium/Foo.class, org/chromium/Foo$Inner.class
    # To extract only .class files not related to the given .java files, we strip
    # off ".class" and "$*.class" and use a substring match against java_files.
    def extract_predicate(path):
        if not path.endswith('.class'):
            return False
        path_without_suffix = re.sub(r'(?:\$|\.)[^/]*class$', '', path)
        partial_java_path = path_without_suffix + '.java'
        return not any(p.endswith(partial_java_path) for p in java_files)

    build_utils.extract_all(jar_path, path=dest_dir, predicate=extract_predicate)
    for path in build_utils.find_in_directory(dest_dir, '*.class'):
        shutil.copystat(jar_path, path)


def _ConvertToJMakeArgs(javac_cmd, pdb_path):
    new_args = ['bin/jmake', '-pdb', pdb_path, '-jcexec', javac_cmd[0]]
    if md5_check.PRINT_EXPLANATIONS:
        new_args.append('-Xtiming')

    do_not_prefix = ('-classpath', '-bootclasspath')
    skip_next = False
    for arg in javac_cmd[1:]:
        if not skip_next and arg not in do_not_prefix:
            arg = '-C' + arg
        new_args.append(arg)
        skip_next = arg in do_not_prefix

    return new_args


def _ParsePackageAndClassNames(java_file):
    package_name = ''
    class_names = []
    with open(java_file) as f:
        for l in f:
            # Strip unindented comments.
            # Considers a leading * as a continuation of a multi-line comment (our
            # linter doesn't enforce a space before it like there should be).
            l = re.sub(r'^(?://.*|/?\*.*?(?:\*/\s*|$))', '', l)

            m = re.match(r'package\s+(.*?);', l)
            if m and not package_name:
                package_name = m.group(1)

            # Not exactly a proper parser, but works for sources that Chrome uses.
            # In order to not match nested classes, it just checks for lack of indent.
            m = re.match(r'(?:\S.*?)?(?:class|@?interface|enum)\s+(.+?)\b', l)
            if m:
                class_names.append(m.group(1))
    return package_name, class_names


def _CheckPathMatchesClassName(java_file, package_name, class_name):
    parts = package_name.split('.') + [class_name + '.java']
    expected_path_suffix = os.path.sep.join(parts)
    if not java_file.endswith(expected_path_suffix):
        raise Exception(('Java package+class name do not match its path.\n'
                         'Actual path: %s\nExpected path: %s') %
                        (java_file, expected_path_suffix))


def _CreateInfoFile(java_files, options, srcjar_files, javac_generated_sources):
    """Writes a .jar.info file.

    This maps fully qualified names for classes to either the java file that they
    are defined in or the path of the srcjar that they came from.

    For apks this also produces a coalesced .apk.jar.info file combining all the
    .jar.info files of its transitive dependencies.
    """
    info_data = dict()
    for java_file in itertools.chain(java_files, javac_generated_sources):
        package_name, class_names = _ParsePackageAndClassNames(java_file)
        for class_name in class_names:
            fully_qualified_name = '{}.{}'.format(package_name, class_name)
            info_data[fully_qualified_name] = java_file
        # Skip aidl srcjars since they don't indent code correctly.
        source = srcjar_files.get(java_file, java_file)
        if '_aidl.srcjar' in source:
            continue
        assert not options.chromium_code or len(class_names) == 1, (
            'Chromium java files must only have one class: {}'.format(source))
        if options.chromium_code:
            _CheckPathMatchesClassName(java_file, package_name, class_names[0])

    with build_utils.atomic_output(options.jar_path + '.info') as f:
        jar_info_utils.write_jar_info_file(f.name, info_data, srcjar_files)
    if options.test_target:
        with open(options.jar_path + '.info.test', 'w') as f:
            keys = list(info_data.keys())
            f.write('\n'.join(keys))


def extract_srcjar(srcjar, generated_java_dir, incremental):
    jar_srcs = []
    with build_utils.temp_dir() as temp_dir:
        extracted_files = build_utils.extract_all(
            srcjar, no_clobber=not incremental, path=temp_dir, pattern='*.java')
        for f in extracted_files:
            package_name, _ = _ParsePackageAndClassNames(f)
            dest_dir = os.path.join(generated_java_dir,
                                    package_name.replace('.', '/'))
            os.makedirs(dest_dir, exist_ok=True)
            dest_file = os.path.join(dest_dir, os.path.basename(f))
            shutil.copy(f, dest_file)
            jar_srcs.append(dest_file)
        return jar_srcs


def search_for_allowlist_file(current_dir, top_dir, allowlist):
    if (not current_dir) or current_dir == top_dir:
        return None
    if not os.path.exists(current_dir):
        return None
    for file in os.listdir(current_dir):
        file_path = os.path.join(current_dir, file)
        if os.path.isfile(file_path):
            if os.path.basename(file_path) == allowlist:
                return '{}/{}'.format(current_dir, allowlist)
    return search_for_allowlist_file(os.path.dirname(current_dir),
                                     top_dir, allowlist)


def _OnStaleMd5(changes, options, javac_cmd, jar_path, java_files,
                classpath_inputs, classpath, allowlist):
    # Don't bother enabling incremental compilation for non-chromium code.
    incremental = options.incremental and options.chromium_code

    with build_utils.temp_dir() as temp_dir:
        srcjars = options.java_srcjars

        classes_dir = os.path.join(temp_dir, 'classes')
        os.makedirs(classes_dir)

        changed_paths = None
        # jmake can handle deleted files, but it's a rare case and it would
        # complicate this script's logic.
        if incremental and changes.added_or_modified_only():
            changed_paths = set(changes.iter_changed_paths())
            # Do a full compile if classpath has changed.
            # jmake doesn't seem to do this on its own... Might be that ijars mess up
            # its change-detection logic.
            if any(p in changed_paths for p in classpath_inputs):
                changed_paths = None

        if options.incremental:
            pdb_path = options.jar_path + '.pdb'

        if incremental:
            # jmake is a compiler wrapper that figures out the minimal set of .java
            # files that need to be rebuilt given a set of .java files that have
            # changed.
            # jmake determines what files are stale based on timestamps between .java
            # and .class files. Since we use .jars, .srcjars, and md5 checks,
            # timestamp info isn't accurate for this purpose. Rather than use jmake's
            # programmatic interface (like we eventually should), we ensure that all
            # .class files are newer than their .java files, and convey to jmake which
            # sources are stale by having their .class files be missing entirely
            # (by not extracting them).
            javac_cmd = _ConvertToJMakeArgs(javac_cmd, pdb_path)

        generated_java_dir = options.generated_dir
        # Incremental means not all files will be extracted, so don't bother
        # clearing out stale generated files.
        if not incremental:
            shutil.rmtree(generated_java_dir, True)

        srcjar_files = {}
        if srcjars:
            build_utils.make_directory(generated_java_dir)
            jar_srcs = []
            for srcjar in options.java_srcjars:
                if changed_paths:
                    changed_paths.update(os.path.join(generated_java_dir, f)
                                         for f in
                                         changes.iter_changed_subpaths(srcjar))
                extracted_files = extract_srcjar(srcjar, generated_java_dir,
                                                 incremental)
                for path in extracted_files:
                    # We want the path inside the srcjar so the viewer can have a tree
                    # structure.
                    srcjar_files[path] = '{}/{}'.format(
                        srcjar, os.path.relpath(path, generated_java_dir))
                jar_srcs.extend(extracted_files)
            java_files.extend(jar_srcs)
            if changed_paths:
                # Set the mtime of all sources to 0 since we use the absence of .class
                # files to tell jmake which files are stale.
                for path in jar_srcs:
                    os.utime(path, (0, 0))

        if java_files:
            if changed_paths:
                changed_java_files = [p for p in java_files if
                                      p in changed_paths]
                if os.path.exists(options.jar_path):
                    _ExtractClassFiles(options.jar_path, classes_dir,
                                       changed_java_files)
                # Add the extracted files to the classpath. This is required because
                # when compiling only a subset of files, classes that haven't changed
                # need to be findable.
                classpath.append(classes_dir)

            # Can happen when a target goes from having no sources, to having sources.
            # It's created by the call to build_utils.touch() below.
            if incremental:
                if os.path.exists(pdb_path) and not os.path.getsize(pdb_path):
                    os.unlink(pdb_path)

            # Don't include the output directory in the initial set of args since it
            # being in a temp dir makes it unstable (breaks md5 stamping).
            cmd = javac_cmd + ['-d', classes_dir]

            # Pass classpath and source paths as response files to avoid extremely
            # long command lines that are tedius to debug.
            if classpath:
                cmd += ['-classpath', ':'.join(classpath)]

            java_files_rsp_path = os.path.join(temp_dir, 'files_list.txt')
            with open(java_files_rsp_path, 'w') as f:
                f.write(' '.join(java_files))
            if options.ohos_code:
                # Check whether java files import classes that MCL not supported.
                if options.mcl_api_blocklist_file and (
                        check_api.blocklist_check(
                                options.mcl_api_blocklist_file,
                                java_files_rsp_path) == "FAILURE"):
                    exit(1)

                # Check whether java files import extra APIs beyond api allowlist
                if allowlist and check_api.allowlist_check(
                        allowlist, java_files_rsp_path,
                        options.all_aosp_imports_file) == "FAILURE":
                    exit(1)

            cmd += ['@' + java_files_rsp_path]

            # JMake prints out some diagnostic logs that we want to ignore.
            # This assumes that all compiler output goes through stderr.
            stdout_filter = lambda s: ''
            if md5_check.PRINT_EXPLANATIONS:
                stdout_filter = None

            attempt_build = lambda: build_utils.check_output(
                cmd,
                print_stdout=options.chromium_code,
                stdout_filter=stdout_filter,
                stderr_filter=ProcessJavacOutput)
            try:
                attempt_build()
            except build_utils.called_process_error as e:
                # Work-around for a bug in jmake (http://crbug.com/551449).
                if ('project database corrupted' not in e.output and
                        'jmake: internal Java exception' not in e.output):
                    raise
                print(
                    'Applying work-around for jmake project database corrupted '
                    '(http://crbug.com/551449).')
                os.unlink(pdb_path)
                attempt_build()
        if options.sources_file:
            with build_utils.atomic_output(options.sources_file,
                                          only_if_changed=True) as temp_f:
                temp_f.write('{}\n'.format('\n'.join(java_files)).encode())

        # Move any Annotation Processor-generated .java files into $out/gen
        # so that codesearch can find them.
        javac_generated_sources = []
        for src_path in build_utils.find_in_directory(classes_dir, '*.java'):
            dst_path = os.path.join(
                generated_java_dir, os.path.relpath(src_path, classes_dir))
            build_utils.make_directory(os.path.dirname(dst_path))
            shutil.move(src_path, dst_path)
            javac_generated_sources.append(dst_path)

        _CreateInfoFile(java_files, options, srcjar_files,
                        javac_generated_sources)

        if options.incremental and (not java_files or not incremental):
            # Make sure output exists.
            build_utils.touch(pdb_path)

        if options.manifest_file:
            manifest_file = options.manifest_file
        else:
            manifest_file = _CreateManifestFile(options.jar_path,
                                                options.main_class)
        with build_utils.atomic_output(options.jar_path) as f:
            jar.JarDirectory(classes_dir,
                             f.name,
                             jar_path,
                             manifest_file=manifest_file,
                             provider_configurations=options.provider_configurations,
                             additional_files=options.additional_jar_files)
            if options.manifest_file is None:
                os.unlink(manifest_file)


def _CreateManifestFile(jar_path, main_class=None):
    with tempfile.NamedTemporaryFile(
            delete=False,
            dir=os.path.dirname(jar_path)) as manifest_file:
        if main_class:
            contents = '{}Main-Class: {}\n'.format(MANIFEST, main_class)
        else:
            contents = MANIFEST
        manifest_file.write(contents.encode())
    return manifest_file.name


def _ParseAndFlattenGnLists(gn_lists):
    ret = []
    for arg in gn_lists:
        ret.extend(build_utils.parse_gn_list(arg))
    return ret


def _ParseOptions(argv):
    parser = optparse.OptionParser()
    build_utils.add_depfile_option(parser)

    parser.add_option(
        '--java-srcjars',
        action='append',
        default=[],
        help='List of srcjars to include in compilation.')
    parser.add_option(
        '--generated-dir',
        help='Subdirectory within target_gen_dir to place extracted srcjars and '
             'annotation processor output for codesearch to find.')
    parser.add_option(
        '--bootclasspath',
        action='append',
        default=[],
        help='Boot classpath for javac. If this is specified multiple times, '
             'they will all be appended to construct the classpath.')
    parser.add_option(
        '--java-version',
        help='Java language version to use in -source and -target args to javac.')
    parser.add_option(
        '--jdk-version',
        help='JDK version. JDK9 uses --release to replace -target and -source option')
    parser.add_option(
        '--full-classpath',
        action='append',
        default=[],
        help='Classpath to use when annotation processors are present.')
    parser.add_option(
        '--interface-classpath',
        action='append',
        default=[],
        help='Classpath to use when no annotation processors are present.')
    parser.add_option(
        '--incremental',
        action='store_true',
        help='Whether to re-use .class files rather than recompiling them '
             '(when possible).')
    parser.add_option(
        '--processors',
        action='append',
        default=[],
        help='GN list of annotation processor main classes.')
    parser.add_option(
        '--processorpath',
        action='append',
        default=[],
        help='GN list of jars that comprise the classpath used for Annotation '
             'Processors.')
    parser.add_option(
        '--processor-arg',
        dest='processor_args',
        action='append',
        help='key=value arguments for the annotation processors.')
    parser.add_option(
        '--provider-configuration',
        dest='provider_configurations',
        action='append',
        help='File to specify a service provider. Will be included '
             'in the jar under META-INF/services.')
    parser.add_option(
        '--additional-jar-file',
        dest='additional_jar_files',
        action='append',
        help='Additional files to package into jar. By default, only Java .class '
             'files are packaged into the jar. Files should be specified in '
             'format <filename>:<path to be placed in jar>.')
    parser.add_option(
        '--chromium-code',
        type='int',
        help='Whether code being compiled should be built with stricter '
             'warnings for chromium code.')
    parser.add_option(
        '--use-errorprone-path',
        help='Use the Errorprone compiler at this path.')
    parser.add_option('--jdkpath', help='path to prebuilts jdk, '
                                        'use jdk inside projects')
    parser.add_option('--jar-path', help='Jar output path.')
    parser.add_option(
        '--javac-arg',
        action='append',
        default=[],
        help='Additional arguments to pass to javac.')
    parser.add_option('--main_class', help='main_class of executable jar')
    parser.add_option('--ohos-code',
                      action='store_true',
                      help='whether java files are developed by ohos team')
    parser.add_option('--manifest_file',
                      help='path to manifest_file of executable jar')
    parser.add_option('--mcl-api-blocklist-file',
                      help='path to file of Maple Core Library API block list')
    parser.add_option('--is_host_library', action='store_true',
                      help='Whether this java library is used host')
    parser.add_option('--test-target', action='store_true',
                      help='Whether it is a test target')
    parser.add_option('--sources-file', help='path to sources_file')
    parser.add_option('--api-allowlist-search-dir',
                      help='path to search for aosp api allowlist')
    parser.add_option('--api-allowlist-filename',
                      help='file name of aosp api allowlist')
    parser.add_option('--api-allowlist-top-dir',
                      help='top directory to search for aosp api allowlist')
    parser.add_option('--ignored-api-patterns',
                      action='append',
                      help='ignored aosp apis.')
    parser.add_option('--all-aosp-imports-file',
                      help='path to all aosp import file.')
    parser.add_option('--jni-output-dir',
                      help='path to generated jni headers.')

    options, args = parser.parse_args(argv)
    build_utils.check_options(options, parser, required=('jar_path',))

    options.bootclasspath = _ParseAndFlattenGnLists(options.bootclasspath)
    options.full_classpath = _ParseAndFlattenGnLists(options.full_classpath)
    options.interface_classpath = _ParseAndFlattenGnLists(
        options.interface_classpath)
    options.processorpath = _ParseAndFlattenGnLists(options.processorpath)
    options.processors = _ParseAndFlattenGnLists(options.processors)
    options.java_srcjars = _ParseAndFlattenGnLists(options.java_srcjars)

    if options.jdk_version == '8' and options.bootclasspath and \
            options.is_host_library:
        # AOSP's boot jar doesn't contain all java 8 classes.
        # See: https://github.com/evant/gradle-retrolambda/issues/23.
        # Get the path of the jdk folder by searching for the 'jar' executable. We
        # cannot search for the 'javac' executable because goma provides a custom
        # version of 'javac'.
        jar_path = distutils.spawn.find_executable('jar', options.jdkpath)
        jdk_dir = os.path.dirname(os.path.dirname(jar_path))
        rt_jar = os.path.join(jdk_dir, 'jre', 'lib', 'rt.jar')
        options.bootclasspath.append(rt_jar)

    additional_jar_files = []
    for arg in options.additional_jar_files or []:
        filepath, jar_filepath = arg.split(':')
        additional_jar_files.append((filepath, jar_filepath))
    options.additional_jar_files = additional_jar_files

    java_files = []
    for arg in args:
        # Interpret a path prefixed with @ as a file containing a list of sources.
        if arg.startswith('@'):
            java_files.extend(build_utils.read_sources_list(arg[1:]))
        else:
            java_files.append(arg)

    return options, java_files


def main(argv):
    argv = build_utils.expand_file_args(argv)
    options, java_files = _ParseOptions(argv)

    if options.use_errorprone_path:
        javac_path = options.use_errorprone_path
    else:
        javac_path = distutils.spawn.find_executable('javac', options.jdkpath)
    jar_path = distutils.spawn.find_executable('jar', options.jdkpath)
    javac_cmd = [javac_path]

    javac_cmd.extend((
        '-g',
        # Enable all warnings in compilation.
        '-Xlint:all',
        # Set maximum heap size to 4096MB.
        '-J-Xmx4096M',
        '-J-XX:OnError="cat hs_err_pid%p.log"',
        '-J-XX:CICompilerCount=6',
        '-J-XX:+UseDynamicNumberOfGCThreads',
        # Chromium only allows UTF8 source files.  Being explicit avoids
        # javac pulling a default encoding from the user's environment.
        '-encoding', 'UTF-8',
        # Prevent compiler from compiling .java files not listed as inputs.
        # See: http://blog.ltgt.net/most-build-tools-misuse-javac/
        '-sourcepath', ':',
    ))

    if options.use_errorprone_path:
        for warning in ERRORPRONE_WARNINGS_TO_TURN_OFF:
            javac_cmd.append('-Xep:{}:OFF'.format(warning))
        for warning in ERRORPRONE_WARNINGS_TO_ERROR:
            javac_cmd.append('-Xep:{}:ERROR'.format(warning))

    if options.is_host_library and options.jdk_version == '9':
        javac_cmd.extend(['--release', options.java_version])
    elif options.java_version:
        javac_cmd.extend([
            '-source', options.java_version,
            '-target', options.java_version,
        ])

    if options.chromium_code:
        javac_cmd.extend(['-Xlint:unchecked', '-Werror'])
    else:
        # XDignore.symbol.file makes javac compile against rt.jar instead of
        # ct.sym. This means that using a java internal package/class will not
        # trigger a compile warning or error.
        javac_cmd.extend(['-XDignore.symbol.file'])

    if options.processors:
        javac_cmd.extend(['-processor', ','.join(options.processors)])

    if options.bootclasspath:
        javac_cmd.extend(['-bootclasspath', ':'.join(options.bootclasspath)])

    # Annotation processors crash when given interface jars.
    active_classpath = (
        options.full_classpath
        if options.processors else options.interface_classpath)
    classpath = []
    if active_classpath:
        classpath.extend(active_classpath)

    if options.processorpath:
        javac_cmd.extend(['-processorpath', ':'.join(options.processorpath)])
    if options.processor_args:
        for arg in options.processor_args:
            javac_cmd.extend(['-A%s' % arg])

    if options.javac_arg and options.ohos_code:
        user_args = options.javac_arg
        if '-nowarn' in user_args or '-Xlint:none' in user_args:
            raise Exception(
                'it is not allowed to build with -nowarn or -Xlint:none')
        compare_len = len('-Xlint:-')
        for arg in user_args:
            if arg[:compare_len] == '-Xlint:-':
                raise Exception('it is not allowed to build with ' + arg)

    javac_cmd.extend(options.javac_arg)

    classpath_inputs = (options.bootclasspath + options.processorpath +
                        classpath)
    # GN already knows of java_files, so listing them just make things worse when
    # they change.
    depfile_deps = ([javac_path] + classpath_inputs + options.java_srcjars)
    depfile_deps += ([jar_path])
    if options.additional_jar_files:
        for arg in options.additional_jar_files:
            depfile_deps.append(arg[0])
    if options.manifest_file:
        depfile_deps += ([options.manifest_file])
    input_paths = depfile_deps + java_files

    output_paths = [
        options.jar_path,
        options.jar_path + '.info',
    ]
    if options.jni_output_dir:
        output_paths += [options.jni_output_dir]
    if options.incremental:
        output_paths.append(options.jar_path + '.pdb')
    if options.test_target:
        output_paths.append(options.jar_path + '.info.test')
    if options.java_srcjars:
        output_paths.extend([options.generated_dir])
    if options.sources_file:
        output_paths.extend([options.sources_file])

    # An escape hatch to be able to check if incremental compiles are causing
    # problems.
    force = int(os.environ.get('DISABLE_INCREMENTAL_JAVAC', 0))

    allowlist = None
    if options.ohos_code:
        allowlist = search_for_allowlist_file(options.api_allowlist_search_dir,
                                              options.api_allowlist_top_dir,
                                              options.api_allowlist_filename)

        if allowlist:
            input_paths += ([allowlist])
            depfile_deps += ([allowlist])
    if options.mcl_api_blocklist_file:
        input_paths += ([options.mcl_api_blocklist_file])
        depfile_deps += ([options.mcl_api_blocklist_file])

    # List python deps in input_strings rather than input_paths since the contents
    # of them does not change what gets written to the depsfile.
    build_utils.call_and_write_depfile_if_stale(
        lambda changes: _OnStaleMd5(changes, options, javac_cmd, jar_path,
                                    java_files, classpath_inputs, classpath,
                                    allowlist),
        options,
        depfile_deps=depfile_deps,
        input_paths=input_paths,
        input_strings=javac_cmd + classpath,
        output_paths=output_paths,
        force=force,
        pass_changes=True,
        add_pydeps=False)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
