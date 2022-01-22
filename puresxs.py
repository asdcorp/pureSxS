#!/usr/bin/env python3
#
# pureSxS
# Copyright (C) 2022 Gamers Against Weed
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import re
import sys
import ctypes
import shutil
import logging
import havesxs
import xml.etree.ElementTree as ET

def unpack_dcm(file, destination):
    """
    Unpacks packed manifest
    """

    logging.debug(f'Unpacking {file}')

    with open(file, 'rb') as f:
        if f.read(4) != b'DCM\1':
            logging.critical('Specified file is not Delta Copium Manifest!')
            return False

        dcm = f.read()

    with open(destination, 'wb') as f:
        f.write(dcm)

    base_manifest = os.path.dirname(os.path.realpath(__file__)) + '/base.manifest'

    result = ctypes.windll.msdelta.ApplyDeltaW(
        ctypes.c_longlong(0),
        ctypes.c_wchar_p(base_manifest),
        ctypes.c_wchar_p(destination),
        ctypes.c_wchar_p(destination)
    )

    if result:
        return True

    logging.error(f'Failed to unpack {file}')
    return False

def get_namespace(xml_root):
    """
    Returns namespace of provided XML root
    """

    ns = re.match(r'\{(.*)\}', xml_root.tag)
    return ns.group(1) if ns.group(1) else ''

def package_name(package):
    """
    Generates package name from its identity
    """

    name = package.get('name')
    public_key = package.get('publicKeyToken')
    arch = package.get('processorArchitecture')
    lang = package.get('language')
    version = package.get('version')

    arch = '' if arch == 'neutral' else arch
    lang = '' if lang == 'neutral' else lang

    return '{}~{}~{}~{}~{}'.format(name, public_key, arch, lang, version)

def assembly_name(assembly):
    """
    Generates assembly name from its identity
    """

    keys = [
        ['name', 'name'],
        ['culture', 'language'],
        ['version', 'version'],
        ['publicKeyToken', 'publicKeyToken'],
        ['processorArchitecture', 'processorArchitecture'],
        ['versionScope', 'versionScope'],
        ['type', 'type']
    ]

    data = {}
    for x in keys:
        value = assembly.get(x[1])

        if value == None and x[0] == 'version':
            return None

        if value == '*' and x[0] == 'culture':
            return None

        if value is None and x[0] != 'culture':
            continue

        if value in ['neutral', '', None] and x[0] in ['culture', 'processorArchitecture']:
            value = 'none'

        data[x[0]] = value

    return havesxs.generate_sxs_name(data)

def verify_assembly(expect, xml_root, ns, is_package):
    """
    Verifies if package/assembly has expected identity
    """

    if expect == None:
        return True

    keys = [
        'name',
        'language',
        'version',
        'publicKeyToken',
        'processorArchitecture'
    ]

    if not is_package:
        keys.append('versionScope')
        keys.append('type')

    identity = xml_root.find('./xmlns:assemblyIdentity', ns)

    for x in keys:
        exp_val = expect.get(x)
        got_val = identity.get(x)

        exp_val = exp_val.lower() if isinstance(exp_val, str) else exp_val
        got_val = got_val.lower() if isinstance(got_val, str) else got_val

        if x in ['language', 'processorArchitecture']:
            exp_val = None if exp_val in ['', 'neutral'] else exp_val
            got_val = None if got_val in ['', 'neutral'] else got_val

        if exp_val != got_val:
            logging.critical(f'Assembly identity mismatch! Key {x} expected {exp_val}, got {got_val}!')
            return False

    return True

def process_package(package, source, destination):
    """
    Copies over package if not present in destination directory and executes
    its processing
    """

    pkg_name = package_name(package)
    logging.info('Package: ' + pkg_name)

    mum = pkg_name + '.mum'
    cat = pkg_name + '.cat'

    mum_path = source + '/' + mum
    cat_path = source + '/' + cat

    mum_new_path = destination + '/' + mum
    cat_new_path = destination + '/' + cat

    if os.path.exists(mum_new_path) and os.path.exists(cat_new_path):
        return True

    if os.path.exists(mum_path):
        shutil.copy(mum_path, mum_new_path)
        if os.path.exists(cat_path):
            shutil.copy(cat_path, cat_new_path)
        else:
            logging.warning(f'Catalog {cat} does not exist')
    else:
        logging.warning(f'Package {mum} does not exist')
        return True

    if not parse_package(mum_path, destination, verify=package):
        logging.critical(f'Parsing package {pkg_name} failed')
        return False

    return True

def process_component(component, source, destination):
    """
    Copies over component/deployment if not present in destination directory
    and executes its processing
    """

    dep_name = assembly_name(component)
    if dep_name == None:
        return True

    logging.info('Deployment: ' + dep_name)

    deployment = dep_name + '.manifest'

    dep_path = source + '/' + deployment
    dep_new_path = destination + '/' + deployment

    if os.path.exists(dep_new_path):
        return True

    if os.path.exists(dep_path):
        shutil.copy(dep_path, dep_new_path)
    else:
        logging.warning(f'Deployment {deployment} does not exist')
        return True

    if not parse_assembly(dep_new_path, source, destination, verify=component):
        logging.critical(f'Parsing deployment {deployment} failed')
        return False

    return True

def process_assembly(assembly, source, destination):
    """
    Copies over assembly if not present in destination directory and executes
    its processing
    """

    asm_name = assembly_name(assembly)
    if asm_name == None:
        return True

    logging.info('Assembly: ' + asm_name)

    asm_man = asm_name + '.manifest'

    asm_path = source + '/' + asm_man
    asm_dir_path = source + '/' + asm_name

    asm_new_path = destination + '/' + asm_man
    asm_new_dir_path = destination + '/' + asm_name

    if os.path.exists(asm_new_path) and os.path.exists(asm_new_dir_path):
        return True

    if os.path.exists(asm_path):
        shutil.copy(asm_path, asm_new_path)
        if os.path.exists(asm_dir_path):
            shutil.copytree(asm_dir_path, asm_new_dir_path)
    else:
        logging.warning(f'Assembly {asm_man} does not exist')
        return True

    if not parse_assembly(asm_new_path, source, destination, verify=assembly):
        logging.critical(f'Parsing assembly {asm_man} failed')
        return False

    return True

def parse_assembly(file, source, destination, *, verify = None):
    """
    Parses contents of the assembly, verifies its identity and runs processing
    of its dependencies
    """

    xml_file = file
    is_packed = False

    with open(file, 'rb') as f:
        if f.read(4) == b'DCM\1':
            is_packed = True
            xml_file = destination + '/unpack_temp'

    if is_packed and not unpack_dcm(file, xml_file):
        logging.critical(f'Failed to unpack {file}!')
        return False

    tree = ET.parse(xml_file)
    root = tree.getroot()
    ns = {'xmlns' : get_namespace(root)}

    if not verify_assembly(verify, root, ns, False):
        return False

    if is_packed:
        os.unlink(xml_file)

    assemblies = root.findall('./xmlns:dependency/xmlns:dependentAssembly/xmlns:assemblyIdentity', ns)

    for assembly in assemblies:
        if not process_assembly(assembly, source, destination):
            logging.critical(f'Assembly processing failed')
            return False

    return True

def parse_package(file, destination, *, verify = None):
    """
    Parses contents of the package, verifies its identity and runs processing
    of its dependencies
    """

    file_dir = os.path.dirname(os.path.realpath(file))

    tree = ET.parse(file)
    root = tree.getroot()
    ns = {'xmlns' : get_namespace(root)}

    if not verify_assembly(verify, root, ns, True):
        return False

    updates = root.findall('./xmlns:package/xmlns:update', ns)

    for update in updates:
        packages = update.findall('./xmlns:package/xmlns:assemblyIdentity', ns)
        for package in packages:
            if not process_package(package, file_dir, destination):
                logging.critical(f'Package processing failed')
                return False

        components = update.findall('./xmlns:component/xmlns:assemblyIdentity', ns)
        for component in components:
            if not process_component(component, file_dir, destination):
                logging.critical(f'Component processing failed')
                return False

        drivers = update.findall('./xmlns:driver/xmlns:assemblyIdentity', ns)
        for driver in drivers:
            if not process_assembly(driver, file_dir, destination):
                logging.critical(f'Driver processing failed')
                return False

    return True

if __name__ == '__main__':
    version = '2.0'

    if sys.platform != 'win32':
        print('CBS packages can only be exported on Windows')
        exit(1)

    if len(sys.argv) != 3:
        print('Usage:')
        print('pureSxS.py <source_mum> <destination>')
        exit(1)

    print('============================================================')
    print(f'pureSxS {version}')
    print('https://github.com/Gamers-Against-Weed/pureSxS')
    print('============================================================')

    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

    source_mum = sys.argv[1]
    dest_dir = sys.argv[2]

    if not os.path.exists(source_mum):
        logging.critical(f'Provided {source_mum} does not exist')
        exit(1)

    dir = os.path.abspath(dest_dir).replace('\\', '/')
    source = os.path.realpath(source_mum).replace('\\', '/')

    if not os.path.exists(dir):
        os.mkdir(dir)

    source_dir = os.path.dirname(os.path.realpath(source))
    split = os.path.splitext(os.path.basename(source))

    package = split[0]

    if split[1] != '.mum':
        logging.critical(f'Provided {source_mum} has incorrect extension')
        exit(1)

    mum = package + '.mum'
    cat = package + '.cat'
    source_cat = source_dir + '/' + cat

    dest_mum = dir + '/' + mum
    dest_cat = dir + '/' + cat

    shutil.copy(source, dest_mum)
    if os.path.exists(source_cat):
        shutil.copy(source_cat, dest_cat)
    else:
        logging.critical('Main catalog does not exist')
        exit(1)

    if not parse_package(source, dir):
        exit(1)
