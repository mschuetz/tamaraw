#!/usr/bin/env python
# http://tech.yipit.com/2011/11/16/183772396/

import os
import re
import subprocess
import sys

modified = re.compile('^(?:M|A)(\s+)(?P<name>.*)')

CHECKS = [
    {
        'output': 'Checking for pdbs...',
        'command': 'grep -n "import pdb" %s',
        'ignore_files': ['.*pre_commit\.py'],
        'print_filename': True,
    },
    {
        'output': 'Checking for ipdbs...',
        'command': 'grep -n "import ipdb" %s',
        'ignore_files': ['.*pre_commit\.py'],
        'print_filename': True,
    },
    {
        'output': 'Checking for forbidden words...',
        'command': 'grep -n "\(print\|foo\|bar\|baz\|quux\)" %s',
        'match_files': ['.*\.py$'],
        'ignore_files': ['.*/test_src/.*', '.*/bin/.*', '.*pre_commit\.py'],
        'print_filename': True,
    },
    {
        'output': 'Running Pyflakes...',
        'command': 'pyflakes %s',
        'match_files': ['.*\.py$'],
        'print_filename': False,
    }
]


def matches_file(file_name, match_files):
    return any(re.compile(match_file).match(file_name) for match_file in match_files)


def check_files(files, check):
    result = 0
    print check['output']
    for file_name in files:
        if not 'match_files' in check or matches_file(file_name, check['match_files']):
            if not 'ignore_files' in check or not matches_file(file_name, check['ignore_files']):
                process = subprocess.Popen(check['command'] % file_name, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
                out, err = process.communicate()
                if out or err:
                    if check['print_filename']:
                        prefix = '\t%s:' % file_name
                    else:
                        prefix = '\t'
                    output_lines = ['%s%s' % (prefix, line) for line in out.splitlines()]
                    print '\n'.join(output_lines)
                    if err:
                        print err
                    result = 1
    return result


def main(all_files):
    # Stash any changes to the working tree that are not going to be committed
    subprocess.call(['git', 'stash', '--keep-index'], stdout=subprocess.PIPE)
    try:
        files = []
        if all_files:
            for root, dirs, file_names in os.walk('.'):
                for file_name in file_names:
                    files.append(os.path.join(root, file_name))
        else:
            p = subprocess.Popen(['git', 'status', '--porcelain'], stdout=subprocess.PIPE)
            out, err = p.communicate()
            for line in out.splitlines():
                match = modified.match(line)
                if match:
                    files.append(match.group('name'))
        
        result = 0
        
        print 'Running tests...'
        return_code = subprocess.call('nosetests', shell=True)
        result = return_code or result
        
        for check in CHECKS:
            result = check_files(files, check) or result
    finally:
        # Unstash changes to the working tree that we had stashed
        subprocess.call(['git', 'reset', '--hard'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.call(['git', 'stash', 'pop', '--quiet', '--index'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    sys.exit(result)


if __name__ == '__main__':
    all_files = False
    if len(sys.argv) > 1 and sys.argv[1] == '--all-files':
        all_files = True
    main(all_files)
