#!/usr/bin/env python3
"""
Generate CMakeLists.txt files from Visual Studio vcxproj files.
This is part of the FreeFalcon Linux porting effort.
"""

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

# Namespace for VS project files
NS = {'vs': 'http://schemas.microsoft.com/developer/msbuild/2003'}

def parse_vcxproj(vcxproj_path):
    """Parse a vcxproj file and extract source files and settings."""
    tree = ET.parse(vcxproj_path)
    root = tree.getroot()

    sources = []
    headers = []

    # Find ClCompile elements (source files)
    for compile in root.findall('.//vs:ClCompile', NS):
        include = compile.get('Include')
        if include:
            # Normalize path separators
            include = include.replace('\\', '/')
            sources.append(include)

    # Find ClInclude elements (header files)
    for include in root.findall('.//vs:ClInclude', NS):
        inc = include.get('Include')
        if inc:
            inc = inc.replace('\\', '/')
            headers.append(inc)

    # Get project name from PropertyGroup
    target_name = None
    for prop in root.findall('.//vs:TargetName', NS):
        if prop.text:
            target_name = prop.text
            break

    if not target_name:
        # Use filename as fallback
        target_name = Path(vcxproj_path).stem

    # Get additional include directories
    include_dirs = []
    for inc_dir in root.findall('.//vs:AdditionalIncludeDirectories', NS):
        if inc_dir.text:
            dirs = inc_dir.text.split(';')
            for d in dirs:
                d = d.strip()
                if d and not d.startswith('%') and not d.startswith('$('):
                    d = d.replace('\\', '/')
                    if d not in include_dirs:
                        include_dirs.append(d)
            break

    # Determine if library or executable
    config_type = 'StaticLibrary'
    for ct in root.findall('.//vs:ConfigurationType', NS):
        if ct.text:
            config_type = ct.text
            break

    return {
        'name': target_name,
        'sources': sources,
        'headers': headers,
        'include_dirs': include_dirs,
        'config_type': config_type
    }

def generate_cmake(project_info, output_dir, relative_to_src=''):
    """Generate CMakeLists.txt content for a project."""
    name = project_info['name']
    sources = project_info['sources']
    config_type = project_info['config_type']

    lines = [f"# {name} library", ""]

    if not sources:
        lines.append(f"# No source files found - creating interface library")
        lines.append(f"add_library({name} INTERFACE)")
        return '\n'.join(lines)

    # Add source files
    lines.append(f"set({name.upper()}_SOURCES")
    for src in sorted(sources):
        lines.append(f"    {src}")
    lines.append(")")
    lines.append("")

    # Add library/executable
    if config_type == 'Application':
        lines.append(f"add_executable({name} ${{{name.upper()}_SOURCES}})")
    else:
        lines.append(f"add_library({name} STATIC ${{{name.upper()}_SOURCES}})")

    lines.append("")

    # Add include directories if specified
    if project_info['include_dirs']:
        lines.append(f"target_include_directories({name} PRIVATE")
        lines.append("    ${CMAKE_CURRENT_SOURCE_DIR}")
        for inc in project_info['include_dirs']:
            # Skip paths that go up too many levels
            if inc.count('..') <= 4:
                lines.append(f"    {inc}")
        lines.append(")")

    return '\n'.join(lines)

def process_directory(src_dir):
    """Process all vcxproj files in a directory tree."""
    src_path = Path(src_dir)

    for vcxproj in src_path.rglob('*.vcxproj'):
        print(f"Processing: {vcxproj}")

        try:
            project_info = parse_vcxproj(vcxproj)
            cmake_content = generate_cmake(project_info, vcxproj.parent)

            cmake_path = vcxproj.parent / 'CMakeLists.txt'

            # Don't overwrite existing files
            if cmake_path.exists():
                print(f"  Skipping (exists): {cmake_path}")
                continue

            with open(cmake_path, 'w') as f:
                f.write(cmake_content)
            print(f"  Created: {cmake_path}")

        except Exception as e:
            print(f"  Error: {e}")

def create_parent_cmakelists(directory):
    """Create parent CMakeLists.txt that adds subdirectories."""
    dir_path = Path(directory)
    subdirs = []

    for item in sorted(dir_path.iterdir()):
        if item.is_dir() and (item / 'CMakeLists.txt').exists():
            subdirs.append(item.name)

    if subdirs:
        lines = [f"# {dir_path.name} subdirectories", ""]
        for subdir in subdirs:
            lines.append(f"add_subdirectory({subdir})")

        cmake_path = dir_path / 'CMakeLists.txt'
        if not cmake_path.exists():
            with open(cmake_path, 'w') as f:
                f.write('\n'.join(lines))
            print(f"Created parent: {cmake_path}")

if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        src_dir = sys.argv[1]
    else:
        src_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src')

    print(f"Processing: {src_dir}")
    process_directory(src_dir)

    # Create parent CMakeLists.txt files
    src_path = Path(src_dir)
    for subdir in src_path.iterdir():
        if subdir.is_dir():
            create_parent_cmakelists(subdir)
