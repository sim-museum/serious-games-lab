#!/usr/bin/env python3
"""
Generate CMakeLists.txt files by scanning for actual source files.
This handles case sensitivity issues between Windows vcxproj and Linux filesystem.
"""

import os
from pathlib import Path
import xml.etree.ElementTree as ET

NS = {'vs': 'http://schemas.microsoft.com/developer/msbuild/2003'}

def find_source_files(directory):
    """Find all source files in a directory (and subdirectories)."""
    sources = []
    headers = []

    dir_path = Path(directory)
    if not dir_path.exists():
        return sources, headers

    for item in dir_path.rglob('*'):
        if item.is_file():
            ext = item.suffix.lower()
            rel_path = item.relative_to(dir_path)

            if ext in ['.cpp', '.c', '.cxx', '.cc']:
                sources.append(str(rel_path))
            elif ext in ['.h', '.hpp', '.hxx']:
                headers.append(str(rel_path))

    return sorted(sources), sorted(headers)

def get_target_name_from_vcxproj(vcxproj_path):
    """Extract target name from vcxproj file."""
    try:
        tree = ET.parse(vcxproj_path)
        root = tree.getroot()

        for prop in root.findall('.//vs:TargetName', NS):
            if prop.text:
                return prop.text
    except:
        pass

    return Path(vcxproj_path).stem

def generate_cmake_for_directory(directory, target_name=None):
    """Generate CMakeLists.txt for a directory by scanning for source files."""
    dir_path = Path(directory)

    # Look for vcxproj to get target name
    vcxproj_files = list(dir_path.glob('*.vcxproj'))
    if vcxproj_files and not target_name:
        target_name = get_target_name_from_vcxproj(vcxproj_files[0])

    if not target_name:
        target_name = dir_path.name

    # Find source files
    sources, headers = find_source_files(directory)

    if not sources:
        # Check for subdirectories with source files
        subdirs_with_sources = []
        for subdir in dir_path.iterdir():
            if subdir.is_dir():
                sub_sources, _ = find_source_files(subdir)
                if sub_sources:
                    subdirs_with_sources.append(subdir.name)

        if subdirs_with_sources:
            # This is a parent directory - create CMakeLists that adds subdirectories
            lines = [f"# {target_name} subdirectories", ""]
            for subdir in sorted(subdirs_with_sources):
                lines.append(f"add_subdirectory({subdir})")
            return '\n'.join(lines)

        # No sources - create interface library
        lines = [f"# {target_name} - no source files found", ""]
        lines.append(f"add_library({target_name} INTERFACE)")
        return '\n'.join(lines)

    # Generate CMakeLists.txt with actual source files
    lines = [f"# {target_name} library", ""]

    # Source files
    lines.append(f"set({target_name.upper()}_SOURCES")
    for src in sources:
        lines.append(f"    {src}")
    lines.append(")")
    lines.append("")

    # Create library
    lines.append(f"add_library({target_name} STATIC ${{{target_name.upper()}_SOURCES}})")
    lines.append("")

    # Include directories - common pattern
    lines.append(f"target_include_directories({target_name} PRIVATE")
    lines.append("    ${CMAKE_CURRENT_SOURCE_DIR}")
    lines.append("    ${FF_SRC_DIR}")
    lines.append("    ${FF_SRC_DIR}/include")
    lines.append("    ${FF_SRC_DIR}/falclib/include")
    lines.append("    ${FF_SRC_DIR}/codelib/include")
    lines.append("    ${FF_SRC_DIR}/vu2/include")
    lines.append("    ${FF_SRC_DIR}/sim/include")
    lines.append("    ${FF_SRC_DIR}/campaign/include")
    lines.append("    ${FF_SRC_DIR}/ui/include")
    lines.append("    ${FF_SRC_DIR}/graphics/include")
    lines.append(")")

    return '\n'.join(lines)

def process_all_directories(src_dir):
    """Process all directories with vcxproj files."""
    src_path = Path(src_dir)

    # Find all directories containing vcxproj files
    vcxproj_dirs = set()
    for vcxproj in src_path.rglob('*.vcxproj'):
        vcxproj_dirs.add(vcxproj.parent)

    for dir_path in sorted(vcxproj_dirs):
        cmake_path = dir_path / 'CMakeLists.txt'

        # Get target name from vcxproj
        vcxproj_files = list(dir_path.glob('*.vcxproj'))
        target_name = None
        if vcxproj_files:
            target_name = get_target_name_from_vcxproj(vcxproj_files[0])

        # Generate content
        content = generate_cmake_for_directory(dir_path, target_name)

        # Write file (overwrite existing)
        print(f"Writing: {cmake_path}")
        with open(cmake_path, 'w') as f:
            f.write(content)

if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        src_dir = sys.argv[1]
    else:
        src_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src')

    print(f"Processing: {src_dir}")
    process_all_directories(src_dir)
