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
import shutil
import logging
import ctypes
import re
import sys
import xml.etree.ElementTree as ET

def hash_data(data):
    hashes = [0, 0, 0, 0]

    for i, x in enumerate(data.lower()):
        i = i % 4
        hashes[i] *= 0x1003F
        hashes[i] += ord(x)
        hashes[i] &= 0xFFFFFFFF

    hashed = hashes[0] * 0x1E5FFFFFD27
    hashed += hashes[1] * 0xFFFFFFDC00000051
    hashed += hashes[2] * 0x1FFFFFFF7
    hashed += hashes[3]

    return hashed & 0xFFFFFFFFFFFFFFFF

def generate_pseudo_key(pkg, *, winners = False):
    order = [
        'name',
        'culture',
        'type',
        'version',
        'publicKeyToken',
        'processorArchitecture',
        'versionScope'
    ]

    data = []
    for x in order:
        if x not in pkg:
            continue

        data.append([x, pkg[x]])

    key = 0
    for x in data:
        if winners == True and x[0] == "version":
            continue

        if x[1] == "none":
            continue

        hash_attr = hash_data(x[0])
        hash_val = hash_data(x[1])

        both_hashes = hash_val + 0x1FFFFFFF7 * hash_attr
        key = both_hashes + 0x1FFFFFFF7 * key

    key &= 0xFFFFFFFFFFFFFFFF
    return '{:016x}'.format(key)

def generate_sxs_name(pkg, *, winners = False):
    pseudo_key = generate_pseudo_key(pkg, winners=winners)
    sxs_name = []

    name = re.sub('[\\(\\)\\\\\\/ \+*!@#$%^&\\[\\]]', '', pkg['name'])

    if len(name) > 40:
        name = name[:19] + '..' + name[-19:]
    else:
        name = name

    if len(pkg['culture']) > 8:
        culture = pkg['culture'][:3] + '..' + pkg['culture'][-3:]
    else:
        culture = pkg['culture']

    sxs_name.append(pkg['processorArchitecture'])
    sxs_name.append(name)
    sxs_name.append(pkg['publicKeyToken'])

    if winners == False:
        sxs_name.append(pkg['version'])

    sxs_name.append(culture)
    sxs_name.append(pseudo_key)

    return '_'.join(sxs_name).lower()

def unpack_dcm(file, destination):
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

def package_name(package):
    name = package.get('name')
    public_key = package.get('publicKeyToken')
    arch = package.get('processorArchitecture')
    lang = package.get('language')
    version = package.get('version')

    arch = '' if arch == 'neutral' else arch
    lang = '' if lang == 'neutral' else lang

    return '{}~{}~{}~{}~{}'.format(name, public_key, arch, lang, version)

def assembly_name(assembly):
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

        if value == '*' and x[0] == 'culture':
            return None

        if value is None and x[0] != 'culture':
            continue

        if value in ['neutral', '', None] and x[0] in ['culture', 'processorArchitecture']:
            value = 'none'

        data[x[0]] = value

    return generate_sxs_name(data)

def parse_deployment(file, source, destination):
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

    if is_packed:
        os.unlink(xml_file)

    root = tree.getroot()
    assemblies = root.findall('./{urn:schemas-microsoft-com:asm.v3}dependency/{urn:schemas-microsoft-com:asm.v3}dependentAssembly/{urn:schemas-microsoft-com:asm.v3}assemblyIdentity')

    for assembly in assemblies:
        asm_name = assembly_name(assembly)
        if asm_name == None:
            continue

        logging.info('Assembly: ' + asm_name)

        assembly = asm_name + '.manifest'

        asm_path = source + '/' + assembly
        asm_dir_path = source + '/' + asm_name

        asm_new_path = destination + '/' + assembly
        asm_new_dir_path = destination + '/' + asm_name

        if os.path.exists(asm_new_path) and os.path.exists(asm_new_dir_path):
            continue

        if os.path.exists(asm_path):
            shutil.copy(asm_path, asm_new_path)
            if os.path.exists(asm_dir_path):
                shutil.copytree(asm_dir_path, asm_new_dir_path)
        else:
            logging.warning(f'Assembly {assembly} does not exist')
            continue

        if not parse_deployment(asm_new_path, source, destination):
            return False

    return True

def parse_package(file, destination):
    file_dir = os.path.dirname(os.path.realpath(file))

    tree = ET.parse(file)
    root = tree.getroot()

    updates = root.findall('./{urn:schemas-microsoft-com:asm.v3}package/{urn:schemas-microsoft-com:asm.v3}update')

    for update in updates:
        packages = update.findall('./{urn:schemas-microsoft-com:asm.v3}package/{urn:schemas-microsoft-com:asm.v3}assemblyIdentity')
        for package in packages:
            pkg_name = package_name(package)
            logging.info('Package: ' + pkg_name)

            mum = pkg_name + '.mum'
            cat = pkg_name + '.cat'

            mum_path = file_dir + '/' + mum
            cat_path = file_dir + '/' + cat

            mum_new_path = destination + '/' + mum
            cat_new_path = destination + '/' + cat

            if os.path.exists(mum_new_path) and os.path.exists(cat_new_path):
                continue

            if os.path.exists(mum_path):
                shutil.copy(mum_path, mum_new_path)
                if os.path.exists(cat_path):
                    shutil.copy(cat_path, cat_new_path)
                else:
                    logging.warning(f'Catalog {cat} does not exist')
            else:
                logging.warning(f'Package {mum} does not exist')
                continue

            if not parse_package(file_dir + '/' + mum, destination):
                return False

        components = update.findall('./{urn:schemas-microsoft-com:asm.v3}component/{urn:schemas-microsoft-com:asm.v3}assemblyIdentity')
        for component in components:
            dep_name = assembly_name(component)
            if dep_name == None:
                continue

            logging.info('Deployment: ' + dep_name)

            deployment = dep_name + '.manifest'

            dep_path = file_dir + '/' + deployment
            dep_new_path = destination + '/' + deployment

            if os.path.exists(dep_new_path):
                continue

            if os.path.exists(dep_path):
                shutil.copy(dep_path, dep_new_path)
            else:
                logging.warning(f'Deployment {deployment} does not exist')
                continue

            if not parse_deployment(dep_new_path, file_dir, destination):
                return False

        drivers = update.findall('./{urn:schemas-microsoft-com:asm.v3}driver/{urn:schemas-microsoft-com:asm.v3}assemblyIdentity')
        for driver in drivers:
            drv_name = assembly_name(driver)
            if drv_name == None:
                continue

            logging.info('Driver: ' + drv_name)

            driver = drv_name + '.manifest'

            drv_path = file_dir + '/' + driver
            drv_dir_path = file_dir + '/' + drv_name

            drv_new_path = destination + '/' + driver
            drv_new_dir_path = destination + '/' + drv_name

            if os.path.exists(drv_new_path) and os.path.exists(drv_new_dir_path):
                continue

            if os.path.exists(drv_path):
                shutil.copy(drv_path, drv_new_path)
                if os.path.exists(drv_dir_path):
                    shutil.copytree(drv_dir_path, drv_new_dir_path)
            else:
                logging.warning(f'Driver {driver} does not exist')
                continue

            if not parse_deployment(drv_new_path, file_dir, destination):
                return False

    return True

if __name__ == '__main__':
    version = '1.0'

    if sys.platform != 'win32':
        print('CBS packages can only be extracted on Windows')
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
